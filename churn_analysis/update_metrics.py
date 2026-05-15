"""
Re-fetches ONLY the metrics API for all GLIDs in glids.txt.
Uses as_of=2026-02-01 to avoid future-date rejection.
Overwrites existing metrics.json regardless of prior status.
"""
import json, os, time, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

INGESTION_URL = "https://ingestion-service-kntbneg73q-el.a.run.app"
INGESTION_KEY = "1f082cadae2b715a37eec357d2c344d0e56b804c1933bb318ccb003f8c7e027b"
AS_OF         = "2026-02-01"

BASE_DIR   = os.path.dirname(__file__)
GLIDS_FILE = os.path.join(BASE_DIR, "..", "glids.txt")
DATA_DIR   = os.path.join(BASE_DIR, "data")
MAX_WORKERS = 5
TIMEOUT     = 25

print_lock = threading.Lock()
def log(msg):
    with print_lock:
        print(msg, flush=True)

def fetch_metrics(glid):
    g = str(glid)
    url = f"{INGESTION_URL}/api/v1/sellers/{g}/metrics?as_of={AS_OF}"
    headers = {"accept": "application/json", "x-api-key": INGESTION_KEY}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            try:    parsed = json.loads(raw)
            except: parsed = {"_raw": raw.decode("utf-8", errors="replace")}
            result = {"status": resp.status, "data": parsed, "error": None}
    except urllib.error.HTTPError as e:
        try:
            body_err = e.read().decode("utf-8", errors="replace")
            try:    parsed_err = json.loads(body_err)
            except: parsed_err = {"_raw": body_err}
        except: parsed_err = {}
        result = {"status": e.code, "data": parsed_err, "error": str(e)}
    except Exception as e:
        result = {"status": None, "data": None, "error": str(e)}

    out_dir = os.path.join(DATA_DIR, g)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "metrics.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    status = result.get("status")
    log(f"  [GLID {g:>12}] metrics -> {status}")
    return glid, status

def main():
    with open(GLIDS_FILE, encoding="utf-8") as f:
        glids = [line.strip() for line in f if line.strip()]

    print(f"Updating metrics for {len(glids)} GLIDs | as_of={AS_OF}")
    print(f"Workers: {MAX_WORKERS} | Output: {DATA_DIR}")
    print("-" * 60)

    ok = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_metrics, g): g for g in glids}
        for future in as_completed(futures):
            glid, status = future.result()
            if status == 200:
                ok += 1

    elapsed = time.time() - start
    print("-" * 60)
    print(f"Done in {elapsed:.1f}s | {ok}/{len(glids)} successful (200 OK)")

if __name__ == "__main__":
    main()
