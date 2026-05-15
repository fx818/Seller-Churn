"""
Bulk API fetcher for churn analysis.
Calls all relevant APIs for each GLID in glids.txt.
Saves each API response as a separate JSON in data/<glid>/<api_name>.json
Uses 5 concurrent threads per GLID batch for speed.
"""
import json, os, sys, time, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ──────────────────────────────────────────────────────────────────
EMPID          = "990151691"
JWT            = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJFTVBMT1lFRSIsInN1YiI6Ijk5MDE1MTY5MSIsImV4cCI6MTc4MDg5NzYzMCwiaWF0IjoxNzc1NzEzNjMwfQ.PLtn5DhM04_FNfywZhYdLOOH_GTf-lvfCIOrl7uS6W0"
INGESTION_URL  = "https://ingestion-service-kntbneg73q-el.a.run.app"
INGESTION_KEY  = "1f082cadae2b715a37eec357d2c344d0e56b804c1933bb318ccb003f8c7e027b"
AS_OF          = "2026-05-15"
DWH_URL        = "https://imdwh.intermesh.net/api/go"
MERP_URL       = "https://merp.intermesh.net"

BASE_DIR  = os.path.dirname(__file__)
GLIDS_FILE = os.path.join(BASE_DIR, "..", "glids.txt")
DATA_DIR  = os.path.join(BASE_DIR, "data")
MAX_WORKERS = 5   # concurrent GLIDs
TIMEOUT     = 25

print_lock = threading.Lock()

def log(msg):
    with print_lock:
        print(msg, flush=True)

# ── API definitions factory (per GLID) ──────────────────────────────────────
def get_apis(glid):
    g = str(glid)
    return [
        {
            "name": "scorecard_summary",
            "method": "POST",
            "url": f"{DWH_URL}/cust_wh_summary_api",
            "headers": {"Content-Type": "text/plain"},
            "body": json.dumps({"in_glusr_usr_id": g, "in_rpt_type": "1"}),
        },
        {
            "name": "scorecard_6m",
            "method": "POST",
            "url": f"{DWH_URL}/cust_scorecard_api",
            "headers": {"Content-Type": "text/plain"},
            "body": json.dumps({"in_glusr_usr_id": g, "in_rpt_type": "1"}),
        },
        {
            "name": "scorecard_12m",
            "method": "POST",
            "url": f"{DWH_URL}/cust_wh_apiv2",
            "headers": {"Content-Type": "text/plain"},
            "body": json.dumps({"in_glusr_usr_id": g, "in_rpt_type": "1"}),
        },
        {
            "name": "competitors",
            "method": "POST",
            "url": f"{DWH_URL}/nsdprepplus?in_glusr_usr_id={g}&comp_flag=1",
            "headers": {"accept": "application/json", "Content-Type": "application/json"},
            "body": json.dumps({"in_glusr_usr_id": g, "comp_flag": "1"}),
        },
        {
            "name": "competitors_counts",
            "method": "POST",
            "url": f"{DWH_URL}/nsdprepplus?in_glusr_usr_id={g}&comp_flag=2",
            "headers": {"accept": "application/json", "Content-Type": "application/json"},
            "body": json.dumps({"in_glusr_usr_id": g, "comp_flag": "2"}),
        },
        {
            "name": "product_summary",
            "method": "GET",
            "url": f"{MERP_URL}/go/api/csd/v1/qualityScoreDetails?glid={g}&empid={EMPID}&flag=summary&AK={JWT}",
            "headers": {},
            "body": None,
        },
        {
            "name": "composite",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
        {
            "name": "hotleads",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/hotleads",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
        {
            "name": "metrics",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/metrics?as_of={AS_OF}",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
        {
            "name": "activity",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/activity",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
    ]

# ── HTTP caller ──────────────────────────────────────────────────────────────
def call_api(api):
    url     = api["url"]
    method  = api["method"]
    body    = api.get("body")
    headers = api.get("headers", {})
    body_b  = body.encode("utf-8") if body else None
    req     = urllib.request.Request(url, data=body_b, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            try:    parsed = json.loads(raw)
            except: parsed = {"_raw": raw.decode("utf-8", errors="replace")}
            return {"status": resp.status, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        try:
            body_err = e.read().decode("utf-8", errors="replace")
            try:    parsed_err = json.loads(body_err)
            except: parsed_err = {"_raw": body_err}
        except: parsed_err = {}
        return {"status": e.code, "data": parsed_err, "error": str(e)}
    except Exception as e:
        return {"status": None, "data": None, "error": str(e)}

# ── Per-GLID fetcher ─────────────────────────────────────────────────────────
def fetch_glid(glid):
    g = str(glid)
    out_dir = os.path.join(DATA_DIR, g)
    os.makedirs(out_dir, exist_ok=True)

    apis = get_apis(g)
    results = {}
    ok = 0
    for api in apis:
        name = api["name"]
        # skip if already fetched successfully
        out_path = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(out_path):
            try:
                existing = json.load(open(out_path, encoding="utf-8"))
                if existing.get("status") == 200:
                    results[name] = existing.get("status")
                    ok += 1
                    continue
            except: pass

        result = call_api(api)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        results[name] = result.get("status")
        if result.get("status") == 200:
            ok += 1
        time.sleep(0.15)

    log(f"  [GLID {g:>12}] {ok}/{len(apis)} OK — {results}")
    return glid, ok, len(apis)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    with open(GLIDS_FILE, encoding="utf-8") as f:
        glids = [line.strip() for line in f if line.strip()]

    print(f"Fetching {len(glids)} GLIDs x {len(get_apis('0'))} APIs = {len(glids)*len(get_apis('0'))} calls")
    print(f"Workers: {MAX_WORKERS} | Output: {DATA_DIR}")
    print("-" * 60)

    total_ok = 0
    total_calls = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_glid, g): g for g in glids}
        for future in as_completed(futures):
            glid, ok, total = future.result()
            total_ok    += ok
            total_calls += total

    elapsed = time.time() - start
    print("-" * 60)
    print(f"Done in {elapsed:.1f}s | {total_ok}/{total_calls} successful calls")

    # Write master summary
    summary = []
    for g in glids:
        entry = {"glid": g, "apis": {}}
        gdir = os.path.join(DATA_DIR, g)
        if os.path.isdir(gdir):
            for fname in os.listdir(gdir):
                if fname.endswith(".json") and fname != "summary.json":
                    try:
                        d = json.load(open(os.path.join(gdir, fname), encoding="utf-8"))
                        entry["apis"][fname.replace(".json","")] = d.get("status")
                    except: pass
        summary.append(entry)

    with open(os.path.join(BASE_DIR, "data", "_master_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Master summary -> data/_master_summary.json")

if __name__ == "__main__":
    main()
