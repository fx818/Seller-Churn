# Call Personalisation — API Endpoints Reference

Sources covered:
- `call_personalisation/agent/data_sources/api_client.py` — 11 MERP/DWH endpoints
- `call_personalisation/agent/data_sources/ingestion_client.py` — 6 ingestion endpoints
- `call_personalisation/agent/data_sources/context_client.py` — 2-step Context API flow

(`db_client.py` is direct DB access — no HTTP endpoints.)

**Auth (do not commit):**
- `IM_INTERNAL_JWT` → MERP `Authorization: Bearer <token>`; also sent as `ak` in the Context API body
- `IM_EMPID` → MERP `empid` query param; also sent in the Context API body
- `INGESTION_URL` + `INGESTION_API_KEY` → ingestion service base URL + `x-api-key` header
- `imdwh.intermesh.net` endpoints do **not** require auth headers

**Replace placeholders:**
- `{GLID}` → seller GLID (numeric)
- `{EMPID}` → your IM employee ID
- `{JWT}` → value of `IM_INTERNAL_JWT`
- `{C2CID}` → click-to-call ID from a DSR connect entry
- `{INGESTION_URL}` → base URL of the ingestion service (no trailing slash)
- `{INGESTION_API_KEY}` → ingestion service `x-api-key` value
- `{MAPPING_ID}` → UUID returned by `generateContextUID` (valid 15 min)

> A ready-to-import Postman collection lives next to this file: `api_endpoints_postman.json`. Import it once, set the collection variables `glid`, `empid`, `jwt`, `c2cid`, and every request is wired up.

---

## 1. DWH POST endpoints (imdwh.intermesh.net)

All four use the same shape:
- Method: `POST`
- Header: `Content-Type: text/plain`
- Body (raw):
  ```json
  {"in_glusr_usr_id": "{GLID}", "in_rpt_type": "1"}
  ```

| Name | URL |
|---|---|
| `mcat` | `https://imdwh.intermesh.net/api/go/mcatLocDtls` |
| `scorecard_summary` | `https://imdwh.intermesh.net/api/go/cust_wh_summary_api` |
| `scorecard_6m` | `https://imdwh.intermesh.net/api/go/cust_scorecard_api` |
| `scorecard_12m` | `https://imdwh.intermesh.net/api/go/cust_wh_apiv2` |

**curl — `mcat`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/mcatLocDtls" \
  -H "Content-Type: text/plain" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","in_rpt_type":"1"}'
```

**curl — `scorecard_summary`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/cust_wh_summary_api" \
  -H "Content-Type: text/plain" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","in_rpt_type":"1"}'
```

**curl — `scorecard_6m`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/cust_scorecard_api" \
  -H "Content-Type: text/plain" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","in_rpt_type":"1"}'
```

**curl — `scorecard_12m`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/cust_wh_apiv2" \
  -H "Content-Type: text/plain" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","in_rpt_type":"1"}'
```

---

## 2. Competitors (imdwh.intermesh.net)

- Method: `POST`
- Headers:
  - `accept: application/json`
  - `Content-Type: body/raw`
- Query string AND body both carry `in_glusr_usr_id` and `comp_flag`.

| Name | URL | Body |
|---|---|---|
| `competitors` | `https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=1` | `{"in_glusr_usr_id":"{GLID}","comp_flag":"1"}` |
| `competitors_counts` | `https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=2` | `{"in_glusr_usr_id":"{GLID}","comp_flag":"2"}` |

**curl — `competitors`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=1" \
  -H "accept: application/json" \
  -H "Content-Type: body/raw" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","comp_flag":"1"}'
```

**curl — `competitors_counts`**
```bash
curl -X POST "https://imdwh.intermesh.net/api/go/nsdprepplus?in_glusr_usr_id={GLID}&comp_flag=2" \
  -H "accept: application/json" \
  -H "Content-Type: body/raw" \
  --data-raw '{"in_glusr_usr_id":"{GLID}","comp_flag":"2"}'
```

---

## 3. MERP GET endpoints (merp.intermesh.net)

All require:
- Header: `Authorization: Bearer <IM_INTERNAL_JWT>`
- Header: `accept: application/json`

### `history`
```
GET https://merp.intermesh.net/index.php/Userlist/newHistory
    ?glid={GLID}
    &empid={EMPID}
    &tab=history
    &platform=VoiceEval
    &duration=7
```
Note: may return HTML instead of JSON.

**curl — `history`**
```bash
curl -X GET "https://merp.intermesh.net/index.php/Userlist/newHistory?glid={GLID}&empid={EMPID}&tab=history&platform=VoiceEval&duration=7" \
  -H "accept: application/json" \
  -H "Authorization: Bearer {JWT}"
```

### `dsr`
```
GET https://merp.intermesh.net/bi/reports/dsr/glusrDSR
    ?glid={GLID}
    &empid={EMPID}
    &modid=WEBERP
    &screen_name=DSR
```

**curl — `dsr`**
```bash
curl -X GET "https://merp.intermesh.net/bi/reports/dsr/glusrDSR?glid={GLID}&empid={EMPID}&modid=WEBERP&screen_name=DSR" \
  -H "accept: application/json" \
  -H "Authorization: Bearer {JWT}"
```

---

## 4. Product quality (merp.intermesh.net)

Both hit the same path with different query params.

### `product_summary`
```
GET https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails
    ?glid={GLID}
    &empid={EMPID}
    &flag=summary
```

**curl — `product_summary`**
```bash
curl -X GET "https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&flag=summary" \
  -H "Authorization: Bearer {JWT}"
```

### `product_details` (paginated)
```
GET https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails
    ?glid={GLID}
    &empid={EMPID}
    &limit=20
    &offset=0
```
Increment `offset` by `limit` until `data` is empty. Client caps at offset 2000.

**curl — `product_details` (first page)**
```bash
curl -X GET "https://merp.intermesh.net/go/api/csd/v1/qualityScoreDetails?glid={GLID}&empid={EMPID}&limit=20&offset=0" \
  -H "Authorization: Bearer {JWT}"
```

---

## 5. Transcripts (merp.intermesh.net)

Chained off `dsr`. For each `dsr_connects[*]` entry where `connect_dtls.Details.CALL_TRANSCRIPT_FLAG == "1"` and `pk_col_name` contains `"click_to_call_id"`, take `pk_col_value` as `{C2CID}` and call:

```
GET https://merp.intermesh.net/go/api/genericMod/v1/calltranscriptread
    ?empid={EMPID}
    &c2cid={C2CID}
    &modid=VoiceAI
    &screen_name=VoiceAI
```
Header: `Authorization: Bearer <IM_INTERNAL_JWT>`

**curl — `transcript`**
```bash
curl -X GET "https://merp.intermesh.net/go/api/genericMod/v1/calltranscriptread?empid={EMPID}&c2cid={C2CID}&modid=VoiceAI&screen_name=VoiceAI" \
  -H "Authorization: Bearer {JWT}"
```

---

## Timeouts used by the client (for reference)

- Standard request: 30s
- Product endpoints: 60s
- Session-level cap: 120s
- 0.3s pacing delay between transcript calls (avoid 429s)

---

# Ingestion Service (ingestion_client.py)

Base URL comes from env var `INGESTION_URL` (no trailing slash). Auth is `x-api-key: {INGESTION_API_KEY}` on every request. Soft-404 (returns `null`) is expected on `composite`, `calls`, `hotleads`, `activity` when a GLID is missing from `seller_profile`.

| Name | Method | Path |
|---|---|---|
| `composite` | GET | `/api/v1/sellers/{GLID}` |
| `calls` | GET | `/api/v1/sellers/{GLID}/calls` |
| `hotleads` | GET | `/api/v1/sellers/{GLID}/hotleads` |
| `blni` | GET | `/api/v1/sellers/{GLID}/blni` |
| `metrics` | GET | `/api/v1/sellers/{GLID}/metrics?as_of=YYYY-MM-DD` |
| `activity` | GET | `/api/v1/sellers/{GLID}/activity` |

**curl — `composite`**
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

**curl — `calls`**
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}/calls" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

**curl — `hotleads`**
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}/hotleads" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

**curl — `blni`**
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}/blni" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

**curl — `metrics`**
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}/metrics?as_of=2026-05-14" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

**curl — `activity`** (seller dashboard clickstream — 30d events)
```bash
curl -X GET "{INGESTION_URL}/api/v1/sellers/{GLID}/activity" \
  -H "accept: application/json" \
  -H "x-api-key: {INGESTION_API_KEY}"
```

---

# Context API (context_client.py)

Two-step UUID flow on `merp.intermesh.net`. Step 1 returns `data.mapping_id` (a UUID valid for ~15 min); step 2 trades it for the full context payload (which contains `kycdetails`, `activitydetails`, `connectdetails`, `BLdetails`, etc.).

### Step 1 — `generateContextUID`
```
POST https://merp.intermesh.net/go/api/globalcontext/v1/generateContextUID
```
Body (JSON):
```json
{
  "mapping_type": 1,
  "mapping_value": "{GLID}",
  "source_id": 1,
  "empid": {EMPID},
  "ak": "{JWT}",
  "data_segments": "all"
}
```

**curl**
```bash
curl -X POST "https://merp.intermesh.net/go/api/globalcontext/v1/generateContextUID" \
  -H "Content-Type: application/json" \
  --data-raw '{"mapping_type":1,"mapping_value":"{GLID}","source_id":1,"empid":{EMPID},"ak":"{JWT}","data_segments":"all"}'
```

### Step 2 — `getContext`
```
GET https://merp.intermesh.net/go/api/globalcontext/v1/x/getContext
    ?mapping_id={MAPPING_ID}
    &data_keys=all
```
No auth headers on this call — the UUID is the credential.

**curl**
```bash
curl -X GET "https://merp.intermesh.net/go/api/globalcontext/v1/x/getContext?mapping_id={MAPPING_ID}&data_keys=all"
```
