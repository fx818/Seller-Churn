"""
Re-calls only the APIs that changed in collection2, updates response.json,
then regenerates dashboard.html for those folders only.
"""
import json, os, sys, time, importlib.util
import urllib.request, urllib.error

GLID = "488587"
EMPID = "990151691"
JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJFTVBMT1lFRSIsInN1YiI6Ijk5MDE1MTY5MSIsImV4cCI6MTc4MDg5NzYzMCwiaWF0IjoxNzc1NzEzNjMwfQ.PLtn5DhM04_FNfywZhYdLOOH_GTf-lvfCIOrl7uS6W0"
INGESTION_URL = "https://ingestion-service-kntbneg73q-el.a.run.app"
INGESTION_KEY = "1f082cadae2b715a37eec357d2c344d0e56b804c1933bb318ccb003f8c7e027b"
OUT_DIR = os.path.join(os.path.dirname(__file__), "api_outputs")

# Only the 5 changed APIs
CHANGED_APIS = [
    {
        "folder": "07_history",
        # Auth moved from Bearer header to AK query param
        "method": "GET",
        "url": f"https://merp.intermesh.net/index.php/Userlist/newHistory?glid={GLID}&empid={EMPID}&tab=history&platform=VoiceEval&duration=7&AK={JWT}",
        "headers": {"accept": "application/json"},
        "body": None,
    },
    {
        "folder": "08_dsr",
        # Entirely new URL — now calls newHistory with glid=236 + AK param
        "method": "GET",
        "url": f"https://merp.intermesh.net/index.php/Userlist/newHistory?empid={EMPID}&glid=236&tab=history&platform=VoiceEval&duration=7&AK={JWT}",
        "headers": {"accept": "application/json"},
        "body": None,
    },
    {
        "folder": "09_product_summary",
        # Auth moved from Bearer header to AK query param
        "method": "GET",
        "url": f"https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&flag=summary&AK={JWT}",
        "headers": {},
        "body": None,
    },
    {
        "folder": "10_product_details",
        # Auth moved from Bearer header to AK query param
        "method": "GET",
        "url": f"https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&limit=20&offset=0&AK={JWT}",
        "headers": {},
        "body": None,
    },
    {
        "folder": "16_ingestion_activity",
        # glid changed to 236 (hardcoded in collection2)
        "method": "GET",
        "url": f"{INGESTION_URL}/api/v1/sellers/236/activity",
        "headers": {"accept": "application/json", "x-api-key": INGESTION_KEY},
        "body": None,
    },
]


def call_api(api):
    url = api["url"]
    body = api.get("body")
    body_bytes = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=body_bytes, headers=api["headers"], method=api["method"])
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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
                parsed_err = json.loads(body_err)
            except Exception:
                parsed_err = {"_raw": body_err}
        except Exception:
            parsed_err = {}
        return {"status": e.code, "data": parsed_err, "error": str(e)}
    except Exception as e:
        return {"status": None, "data": None, "error": str(e)}


def save(folder, result):
    path = os.path.join(OUT_DIR, folder, "response.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return path


def main():
    changed_folders = []

    for api in CHANGED_APIS:
        folder = api["folder"]
        print(f"  [{folder}] {api['method']} {api['url'][:90]}...")
        result = call_api(api)
        save(folder, result)
        status = result["status"]
        err = result["error"]
        symbol = "OK" if status and 200 <= int(status) < 300 else "FAIL"
        print(f"  [{symbol}] status={status}" + (f" err={err}" if err else ""))
        changed_folders.append(folder)
        time.sleep(0.3)

    print(f"\nRe-calling done. Regenerating dashboards for: {changed_folders}")

    # Import generate_dashboards and regenerate only changed folders
    spec = importlib.util.spec_from_file_location(
        "generate_dashboards",
        os.path.join(os.path.dirname(__file__), "generate_dashboards.py")
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    for folder in changed_folders:
        gen.generate_for_folder(folder)

    print("\nDone. Only changed dashboards updated.")


if __name__ == "__main__":
    main()
