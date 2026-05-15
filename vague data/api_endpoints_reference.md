# Call Personalisation — API Endpoints Reference

Source: `call_personalisation/agent/data_sources/api_client.py`

All 11 endpoints used by the deep agent to fetch per-GLID data. Use these in Postman.

**Auth (do not commit):**
- `IM_INTERNAL_JWT` → sent as `Authorization: Bearer <token>` on every `merp.intermesh.net` request
- `IM_EMPID` → sent as the `empid` query param on every `merp.intermesh.net` request
- `imdwh.intermesh.net` endpoints do **not** require auth headers

**Replace placeholders:**
- `{GLID}` → seller GLID (numeric)
- `{EMPID}` → your IM employee ID
- `{JWT}` → value of `IM_INTERNAL_JWT`
- `{C2CID}` → click-to-call ID from a DSR connect entry

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
