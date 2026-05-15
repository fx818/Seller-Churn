"""
Slim loader — fetches only the APIs needed for Snapshot extraction.
All responses saved as JSON; reruns skip if status==200 cached.
Cache: seller_survival/data/loader_cache/<glid>/<api_name>.json
"""
import json, os, time, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMPID         = os.getenv("IM_EMPID", "990151691")
JWT           = os.getenv("IM_INTERNAL_JWT", "")
INGESTION_KEY = os.getenv("INGESTION_API_KEY", "")
INGESTION_URL = os.getenv("INGESTION_URL", "https://ingestion-service-kntbneg73q-el.a.run.app")
DWH_URL       = "https://imdwh.intermesh.net/api/go"
MERP_URL      = "https://merp.intermesh.net"
METRICS_AS_OF = os.getenv("METRICS_AS_OF", "2026-01-01")

TIMEOUT    = 25
SLEEP_BTW  = 0.15
MAX_WORKERS = 5

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "loader_cache")
_print_lock = threading.Lock()

def _log(msg):
    with _print_lock:
        print(msg, flush=True)


def _get_apis(g):
    g = str(g)
    return [
        {
            "name": "scorecard_summary",
            "method": "POST",
            "url": f"{DWH_URL}/cust_wh_summary_api",
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
            "name": "product_details",
            "method": "GET",
            "url": f"{MERP_URL}/go/api/csd/v1/qualityScoreDetails?glid={g}&empid={EMPID}&limit=50&offset=0",
            "headers": {"Authorization": f"Bearer {JWT}"},
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
            "name": "metrics",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/metrics?as_of={METRICS_AS_OF}",
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
        {
            "name": "hotleads",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/hotleads",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
        {
            "name": "blni",
            "method": "GET",
            "url": f"{INGESTION_URL}/api/v1/sellers/{g}/blni",
            "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
            "body": None,
        },
    ]


def _call_api(api):
    body_b = api["body"].encode() if api["body"] else None
    req = urllib.request.Request(
        api["url"], data=body_b, headers=api["headers"], method=api["method"]
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"_raw": raw.decode("utf-8", errors="replace")}
            return {"status": resp.status, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        try:
            body_err = e.read().decode("utf-8", errors="replace")
            try:
                pe = json.loads(body_err)
            except Exception:
                pe = {"_raw": body_err}
        except Exception:
            pe = {}
        return {"status": e.code, "data": pe, "error": str(e)}
    except Exception as e:
        return {"status": None, "data": None, "error": str(e)}


def fetch_for_glid(glid, verbose=True) -> dict:
    """Fetch all APIs for a GLID, cache-first. Returns dict of api_name→response."""
    g = str(glid)
    out_dir = os.path.join(_DATA_DIR, g)
    os.makedirs(out_dir, exist_ok=True)

    apis = _get_apis(g)
    results = {}
    ok = 0
    for api in apis:
        name = api["name"]
        path = os.path.join(out_dir, f"{name}.json")
        if os.path.exists(path):
            try:
                cached = json.load(open(path, encoding="utf-8"))
                if cached.get("status") == 200:
                    results[name] = cached
                    ok += 1
                    continue
            except Exception:
                pass
        result = _call_api(api)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        results[name] = result
        if result.get("status") == 200:
            ok += 1
        time.sleep(SLEEP_BTW)

    if verbose:
        _log(f"  [GLID {g:>12}] {ok}/{len(apis)} OK")
    return results


def fetch_batch(glids, verbose=True) -> dict:
    """Fetch all GLIDs concurrently. Returns {glid: {api_name: response}}."""
    out = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_for_glid, g, verbose): g for g in glids}
        for fut in as_completed(futures):
            g = futures[fut]
            try:
                out[str(g)] = fut.result()
            except Exception as e:
                _log(f"  [GLID {g}] ERROR: {e}")
                out[str(g)] = {}
    return out
