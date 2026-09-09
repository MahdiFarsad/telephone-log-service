# Telephone Call Log Service — Project Report

**Status:** Code complete and locally tested (17/17 automated tests passing). Not yet deployed to production. This report documents what the service does, why it's built this way, and what's confirmed vs. still open before go-live.

---

## 1. Purpose

Every phone call that touches the company's phone system — internal (staff-to-staff), inbound from outside, and outbound to outside — needs to be logged as metadata (no audio) into a durable record, in the same two-tier pattern already proven by the MEAS II audit log service: a fast "hot" store for quick lookups, and a permanent "cold" store for reporting and audits.

This service is the ingestion layer that makes that happen for telephone calls, sourced from the Simotel PBX (Asterisk-based).

---

## 2. How data arrives: Simotel Webhooks

This is **not** a polling/pull integration. Simotel's own documented **Webhooks** feature pushes one HTTP request to a URL you register, every time a call ends. Confirmed specifics for this install:

- **Method:** `GET`, API v4 ("G4") — with GET, Simotel sends the call data as URL query parameters rather than a JSON body (that's the POST/v4 behavior instead).
- **Event:** `CDR` (the plain, non-queue event) — confirmed as the event type in use here, not `CdrQueue`.
- **Path:** registered in Simotel's own API settings panel as `192.168.1.xx/SimotelLaugger/SimotelLogTabriz`, alongside the API token used to authenticate the request.
- **Expected response:** HTTP `200`, with a body Simotel doesn't parse ("undefined") — confirmed with the team, and implemented exactly as such (an empty `200 OK`, not `204`).
- **Retry behavior:** not documented and not confirmed. The service is built defensively regardless — see §5 on idempotency.

**Addressing, confirmed and finalized:** `192.168.1.18` is **this service's own server** — the same one that already runs the audit log service and its databases. Simotel's own PBX has a separate IP (not yet confirmed, needed only for firewall rules, not for anything in the code).

---

## 3. What actually gets sent (verified against real payloads)

Two real examples were provided directly from the Simotel panel, and cross-checked against Simotel's official documentation page for the `CDR` event. The two didn't fully agree with each other — where they conflicted, the real examples and team confirmation were treated as authoritative.

```json
{
  "event_name": "CDR",
  "starttime": "2021-01-16 06:30:37.471398",
  "endtime": "2021-01-16 06:30:37.471398",
  "src": "991",
  "dst": "993",
  "type": "local",
  "disposition": "ANSWERED",
  "billsec": 9,
  "wait": 11,
  "record": "20210116_1610778618.378.mp3",
  "unique_id": "1610778618.378"
}
```
```json
{
  "event_name": "CDR",
  "starttime": "2021-01-16 07:17:00.508368",
  "endtime": "2021-01-16 07:17:01.508368",
  "src": "992",
  "dst": "66",
  "type": "local",
  "disposition": "NO ANSWER",
  "duration": 1,
  "wait": 1,
  "unique_id": "1610781419.387"
}
```

Key things this confirmed or corrected from the initial design:

| Finding | Detail |
|---|---|
| `billsec` vs `duration` | **Mutually exclusive**, not both-required as first assumed. `billsec` appears on ANSWERED calls; `duration` appears on NO ANSWER calls. Both are now Optional in the model. |
| `record` | Only present when a recording exists (answered calls). Confirmed never persisted — metadata only, per the original requirement. |
| `type` | **The authoritative signal for call direction** — documented enum, confirmed complete by the team: `incoming`, `outgoing`, `local`, `feature`, `no defined`. See §4. |
| `event_name` | Arrives as `"CDR"` (uppercase) in real deliveries. Not gated on exact casing anywhere in the code. |
| `wait` / `billsec` semantics | Simotel's own doc table describes `billsec` as "wait time before answer" and `wait` as "call wait time" — this reads backwards from standard telephony convention (`billsec` normally = talk/billable time) and is internally inconsistent (two different "wait" concepts). **Not yet resolved.** The working assumption (talk time / ring time respectively) fits the real example data far better, but this needs one real test call with known timings to confirm outright. Both fields are stored as delivered regardless of which interpretation is correct, so nothing is lost either way. |
| Additional documented fields | `entry_point`, `outgoing_point` (gateway names), `cuid` (the docs' alternate name for `unique_id`), `poll_point`/`poll_lable` (survey data), `originated_call_id` (links both legs of a transferred call). Not seen in the two real examples, but captured as optional fields so nothing is silently dropped if they do appear. |

---

## 4. Direction derivation

Simotel's `type` field has a small, confirmed-complete enum, and is used as the primary signal:

| `type` | Mapped `direction` |
|---|---|
| `local` | `internal` |
| `incoming` | `inbound_external` |
| `outgoing` | `outbound_external` |
| `feature` | `feature` (its own category — call-parking, voicemail access, etc. aren't a call between two external parties in the usual sense) |
| `no defined` / missing | Falls back to a number-length heuristic (is the number's digit length within a configured internal-extension range?) |

This caught a real bug during testing: the second real example (`dst="66"`, only 2 digits) would have been misclassified as `outbound_external` by the number-length heuristic alone. `type="local"` correctly identifies it as `internal`. This is exactly why the heuristic is now a fallback, not the primary logic.

---

## 5. Architecture

```
Simotel PBX (IP not yet confirmed with team)
   │  GET request + token, once per call, only when the call ends
   ▼
Your server — 192.168.1.18
   │
   ├── FastAPI ingestion endpoint at /SimotelLaugger/SimotelLogTabriz
   │     validate token → parse query params → derive direction →
   │     strip recording filename → async insert → immediate 200 OK
   │     (same server, same pattern as the existing audit log service)
   ▼
   ├── MongoDB "hot" store — collection call_logs
   │     (recent window, indexed on call_id, numbers, extension, time range)
   │
   │  periodic ETL job (batch copy, insert-only, every N minutes)
   ▼
   └── SQL Server "cold" store — table dbo.tblCallLog
         (full history, for reporting/audits)
```

- **Idempotency**: a unique index on `call_id` in MongoDB turns an accidental duplicate delivery into a safe no-op, since Simotel's retry behavior on failure isn't documented or confirmed.
- **Failure isolation**: the ETL job's errors are caught independently — if SQL Server is unreachable, the ingestion endpoint keeps accepting and storing calls in MongoDB regardless.
- **No polling job**: this is a push-only integration; no reconciliation/pull job was built against an unconfirmed API, per the original design principle of not building against something the team hasn't confirmed exists.

---

## 6. Security

- The API token is validated with a constant-time comparison (`hmac.compare_digest`), never logged, never echoed in any response.
- The token's exact transport (query param, and which name) was confirmed via real payloads to be `api_key` as a query parameter.
- The service is intended for internal-network use only, not internet-facing.

---

## 7. Testing performed

17 automated tests, covering:
- Valid request → 200, correctly stored, direction derived correctly
- Both real example payloads, verified field-for-field (including the `billsec`/`duration` mutual-exclusivity case and the `type="local"` direction fix)
- Invalid/missing token → 401, nothing stored
- Malformed/incomplete payload → 400
- Duplicate `call_id` delivered twice → both acknowledged with 200, but only one record stored
- All four confirmed `type` values mapped correctly, plus the fallback behavior for `no defined`/missing `type`

Tests use `mongomock-motor` to simulate MongoDB, so they run without any real database. They do not cover the SQL Server ETL path end-to-end, since that requires a real SQL Server instance and the ODBC driver — that's part of the deployment-stage testing, not the local test suite.

Manual local testing (via a running `uvicorn` instance and `curl`) was also performed against both real example payloads and simulated `incoming`/`outgoing`/`feature` calls, confirming the running service — not just the test suite — behaves correctly end-to-end against a local MongoDB.

---

## 8. What's confirmed vs. still open

**Confirmed:**
- Webhook mechanism, method, event type, path, and expected response code
- `192.168.1.18` is this service's own server, separate from the PBX
- Real field names and their quirks (§3)
- Complete `type` enum and its direction mapping (§4)

**Still open, none of which block continued development:**
1. **`billsec`/`wait` semantics** — needs one real test call with known ring/talk timing to confirm which is which. Doesn't block deployment; affects how reports are read later.
2. **Simotel PBX's actual IP** — needed for firewall rules only.
3. **Numbering-plan details** for the fallback heuristic — now lower-priority since `type` is the primary signal and covers the confirmed cases; the heuristic only matters if `type` is ever missing.
4. **Retry behavior on delivery failure** — not documented; the idempotency guard covers this defensively either way.
5. **Timezone of `starttime`/`endtime`** — Simotel's docs default to UTC, but this hasn't been explicitly confirmed for this install.

---

## 9. Repository

Code, tests, SQL DDL, and setup instructions: https://github.com/MahdiFarsad/telephone-log-service

See `README.md` for setup and usage, and `TESTING_AND_DEPLOYMENT.md` for the full stage-by-stage runbook from local testing through production go-live.
