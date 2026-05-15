"""
IndiaMART API Caller — calls all collection endpoints, saves responses to api_outputs/<name>/response.json
"""
import json, os, sys, time
import urllib.request, urllib.error

GLID = "488587"
EMPID = "990151691"
JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJFTVBMT1lFRSIsInN1YiI6Ijk5MDE1MTY5MSIsImV4cCI6MTc4MDg5NzYzMCwiaWF0IjoxNzc1NzEzNjMwfQ.PLtn5DhM04_FNfywZhYdLOOH_GTf-lvfCIOrl7uS6W0"
INGESTION_URL = "https://ingestion-service-kntbneg73q-el.a.run.app"
INGESTION_KEY = "1f082cadae2b715a37eec357d2c344d0e56b804c1933bb318ccb003f8c7e027b"
AS_OF = "2026-05-14"
OUT_DIR = os.path.join(os.path.dirname(__file__), "api_outputs")

APIS = [
    {
        "folder": "01_mcat",
        "method": "POST",
        "url": "https://imdwh.intermesh.net/api/go/mcatLocDtls",
        "headers": {"Content-Type": "text/plain"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "in_rpt_type": "1"}),
    },
    {
        "folder": "02_scorecard_summary",
        "method": "POST",
        "url": "https://imdwh.intermesh.net/api/go/cust_wh_summary_api",
        "headers": {"Content-Type": "text/plain"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "in_rpt_type": "1"}),
    },
    {
        "folder": "03_scorecard_6m",
        "method": "POST",
        "url": "https://imdwh.intermesh.net/api/go/cust_scorecard_api",
        "headers": {"Content-Type": "text/plain"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "in_rpt_type": "1"}),
    },
    {
        "folder": "04_scorecard_12m",
        "method": "POST",
        "url": "https://imdwh.intermesh.net/api/go/cust_wh_apiv2",
        "headers": {"Content-Type": "text/plain"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "in_rpt_type": "1"}),
    },
    {
        "folder": "05_competitors",
        "method": "POST",
        "url": f"https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=1",
        "headers": {"accept": "application/json", "Content-Type": "application/json"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "comp_flag": "1"}),
    },
    {
        "folder": "06_competitors_counts",
        "method": "POST",
        "url": f"https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=2",
        "headers": {"accept": "application/json", "Content-Type": "application/json"},
        "body": json.dumps({"in_glusr_usr_id": GLID, "comp_flag": "2"}),
    },
    {
        "folder": "07_history",
        "method": "GET",
        "url": f"https://merp.intermesh.net/index.php/Userlist/newHistory?glid={GLID}&empid={EMPID}&tab=history&platform=VoiceEval&duration=7",
        "headers": {"accept": "application/json", "Authorization": f"Bearer {JWT}"},
        "body": None,
    },
    {
        "folder": "08_dsr",
        "method": "GET",
        "url": f"https://merp.intermesh.net/bi/reports/dsr/glusrDSR?glid={GLID}&empid={EMPID}&modid=WEBERP&screen_name=DSR",
        "headers": {"accept": "application/json", "Authorization": f"Bearer {JWT}"},
        "body": None,
    },
    {
        "folder": "09_product_summary",
        "method": "GET",
        "url": f"https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&flag=summary",
        "headers": {"Authorization": f"Bearer {JWT}"},
        "body": None,
    },
    {
        "folder": "10_product_details",
        "method": "GET",
        "url": f"https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&limit=20&offset=0",
        "headers": {"Authorization": f"Bearer {JWT}"},
        "body": None,
    },
    {
        "folder": "11_ingestion_composite",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
    {
        "folder": "12_ingestion_calls",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}/calls",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
    {
        "folder": "13_ingestion_hotleads",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}/hotleads",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
    {
        "folder": "14_ingestion_blni",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}/blni",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
    {
        "folder": "15_ingestion_metrics",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}/metrics?as_of={AS_OF}",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
    {
        "folder": "16_ingestion_activity",
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/{GLID}/activity",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
]

def call_api(api):
    url = api["url"]
    method = api["method"]
    headers = api["headers"]
    body = api["body"]

    body_bytes = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = resp.status
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"_raw": raw.decode("utf-8", errors="replace")}
            return {"status": status, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        try:
            body_err = e.read().decode("utf-8", errors="replace")
            try:
                parsed_err = json.loads(body_err)
            except Exception:
                parsed_err = {"_raw": body_err}
        except Exception:
            parsed_err = {}
        return {"status": e.code, "data": parsed_err, "error": str(e)}
    except Exception as e:
        return {"status": None, "data": None, "error": str(e)}


def call_context_api():
    # Step 1 — generateContextUID
    step1_url = "https://merp.intermesh.net/go/api/globalcontext/v1/generateContextUID"
    step1_body = json.dumps({
        "mapping_type": 1,
        "mapping_value": GLID,
        "source_id": 1,
        "empid": int(EMPID),
        "ak": JWT,
        "data_segments": "all"
    })
    step1_req = urllib.request.Request(
        step1_url,
        data=step1_body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    print("  [context] Step 1 — generateContextUID ...")
    try:
        with urllib.request.urlopen(step1_req, timeout=30) as resp:
            step1_data = json.loads(resp.read())
    except Exception as e:
        result = {"step1": {"error": str(e)}, "step2": None}
        _save("17_context", result)
        print(f"  [context] Step 1 FAILED: {e}")
        return

    _save("17_context_uid", {"status": 200, "data": step1_data, "error": None})
    print(f"  [context] Step 1 OK — {json.dumps(step1_data)[:120]}")

    # Extract mapping_id
    mapping_id = None
    if isinstance(step1_data, dict):
        mapping_id = (step1_data.get("data") or {}).get("mapping_id") or step1_data.get("mapping_id")

    if not mapping_id:
        print("  [context] Could not extract mapping_id from Step 1 response")
        _save("17_context_uid", {"status": 200, "data": step1_data, "error": "mapping_id not found"})
        return

    time.sleep(1)

    # Step 2 — getContext
    step2_url = f"https://merp.intermesh.net/go/api/globalcontext/v1/x/getContext?mapping_id={mapping_id}&data_keys=all"
    print(f"  [context] Step 2 — getContext (mapping_id={mapping_id}) ...")
    step2_req = urllib.request.Request(step2_url, method="GET")
    try:
        with urllib.request.urlopen(step2_req, timeout=30) as resp:
            step2_data = json.loads(resp.read())
        _save("18_context_data", {"status": 200, "data": step2_data, "error": None})
        print(f"  [context] Step 2 OK")
    except Exception as e:
        _save("18_context_data", {"status": None, "data": None, "error": str(e)})
        print(f"  [context] Step 2 FAILED: {e}")


def _save(folder, result):
    path = os.path.join(OUT_DIR, folder)
    os.makedirs(path, exist_ok=True)
    out_file = os.path.join(path, "response.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return out_file


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    results_summary = []

    for api in APIS:
        folder = api["folder"]
        print(f"  [{folder}] {api['method']} {api['url'][:80]}...")
        result = call_api(api)
        out = _save(folder, result)
        status = result["status"]
        err = result["error"]
        symbol = "OK" if status and 200 <= status < 300 else "FAIL"
        print(f"  [{symbol}] status={status} saved={out}" + (f" err={err}" if err else ""))
        results_summary.append({"folder": folder, "status": status, "error": err})
        time.sleep(0.3)

    # Context API (2-step)
    call_context_api()

    # Write summary
    summary_path = os.path.join(OUT_DIR, "_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nDone. Summary → {summary_path}")


if __name__ == "__main__":
    main()
