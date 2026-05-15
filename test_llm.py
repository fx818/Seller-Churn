import os, requests
from dotenv import load_dotenv
load_dotenv(override=True)

BASE  = os.getenv("LLM_BASE_URL", "").rstrip("/")
KEY   = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "")

print(f"BASE  : {BASE}")
print(f"MODEL : {MODEL}")
print(f"KEY   : {KEY[:20]}...")
print()

PATHS = [
    "/chat/completions",
    "/v1/chat/completions",
    "/v1/model/chat/completions",
    "/model/chat/completions",
    "/completions",
]

payload = {
    "model": MODEL,
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "Reply with: OK"}],
}
headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

for path in PATHS:
    url = BASE + path
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"[{r.status_code}] POST {url}")
        if r.status_code == 200:
            print(f"  SUCCESS: {r.text[:300]}")
            break
        else:
            print(f"  {r.text[:150]}")
    except Exception as e:
        print(f"[ERR] POST {url}  →  {e}")
    print()
