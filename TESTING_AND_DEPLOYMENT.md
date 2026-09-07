# Testing & Deployment Runbook — Telephone Call Log Service

One authoritative checklist, in order. Don't skip ahead — each stage exists because the next one depends on it.

---

## Stage 1 — Local test (no real Simotel, no real server)

Goal: prove the code itself is correct, using your own machine.

1. Extract the repo / `git clone https://github.com/MahdiFarsad/telephone-log-service`.
2. Run the automated test suite first — it needs nothing but Python:
   ```
   pip install -r requirements.txt httpx pytest pytest-asyncio mongomock-motor
   pytest tests/ -v
   ```
   All 9 should pass. If any fail, stop here — nothing below will work either.
3. Start a local MongoDB: `docker run -d -p 27017:27017 --name test-mongo mongo` (or a local install).
4. `cp .env.example .env`, then set `MONGO_URI=mongodb://localhost:27017` and any `SIMOTEL_API_TOKEN` value (e.g. `local-test-token`). Leave `SQLSERVER_CONN_STR` blank — not needed yet.
5. Run the real service: `uvicorn app.main:app --reload`.
6. Send a real request:
   ```
   curl "http://127.0.0.1:8000/SimotelLaugger/SimotelLogTabriz?event_name=Cdr&unique_id=test-001&src=101&dst=102&duration=34&billsec=31&disposition=ANSWERED&starttime=2026-01-01+10:00:00&endtime=2026-01-01+10:00:34&api_key=local-test-token"
   ```
   Expect HTTP 204. Then check Mongo:
   ```
   mongosh --eval "db.getSiblingDB('telephone_log_service').call_logs.find().pretty()"
   ```
   Confirm the record exists with `direction: "internal"`. Try a wrong `api_key` and confirm you get 401 instead.

**Do not proceed to Stage 2 until this stage is fully green.**

---

## Stage 2 — Capture one real Simotel payload (Phase 0)

Goal: confirm our field-name and token assumptions against the real PBX, before touching production data.

1. Get `capture.py` (already in the repo) onto a machine that can receive the webhook — ideally on `192.168.1.18` itself, on the exact registered path.
2. Run it: `uvicorn capture:app --host 0.0.0.0 --port 8000` (or swap it in temporarily on whatever port Simotel is configured to call).
3. Trigger three real test calls: one internal (extension→extension), one inbound external (an outside number calling in), one outbound external (an extension calling out).
4. Open `capture_log.jsonl` and check, specifically:
   - Do the query param names match `unique_id`, `src`, `dst`, `billsec`, `duration`, `disposition`, `starttime`, `endtime`, `queue`, `ringtime`, `answeredtime`, `record`? Note any differences.
   - Where does the token actually arrive — which query param name, or a header?
   - **What timezone are `starttime`/`endtime` in?** Compare the logged time against your wall-clock time when you made the test call. If they match your local time, it's local; if they're a few hours off, it's UTC (per Simotel's own default). Write this down — it affects how reports read later.
   - Which `event_name` value(s) actually appeared — `Cdr`, `CdrQueue`, or something else — for each of the three call types. This confirms whether one event type covers all three, or you need to enable more than one.

5. Send me (or write down) what you found. If anything differs from the assumptions above, these are the only files that need to change:
   - `app/models/call_log.py` — the `Field(alias=...)` values
   - `app/config.py` — `SIMOTEL_TOKEN_PARAM_NAME`
   - `app/main.py` — if timestamps need explicit UTC/local conversion before storage

**Do not point the real service at production until this stage confirms (or corrects) these assumptions.**

---

## Stage 3 — Provision the real infrastructure

1. On `192.168.1.18`: create a new MongoDB database, separate from the audit log service's own collection.
2. Create a new SQL Server database or schema, separate from `MEAS05` and the audit log's tables. Run `sql/create_table.sql` against it.
3. Confirm ODBC Driver 18 is installed there (needed for the ETL job, not the ingestion endpoint itself).
4. `cp .env.example .env` on the server, filled in with the **real** token, Mongo URI, and SQL Server connection string. Never commit this file.

---

## Stage 4 — Deploy

1. Decide: new route inside the audit log service's existing FastAPI app, or a sibling process on the same box. Either works; pick whichever matches how the audit log service is already run.
2. Set it up to start automatically on server restart (systemd unit on Linux, or a Windows Service — tell me which OS and I'll write the exact unit/service file).
3. Do **not** yet point Simotel's live webhook config at this — first verify it's actually running and reachable (`curl` its `/health` endpoint from another machine on the network).

---

## Stage 5 — Test again, in production, before going live

This is a repeat of Stage 1's test, but against the real server and real databases — don't skip it just because Stage 1 passed.

1. Send one manual test request (like the `curl` command above) directly at `http://192.168.1.18/SimotelLaugger/SimotelLogTabriz`, with the real token. Confirm 204, confirm it lands in the real MongoDB.
2. Confirm a wrong token still returns 401 and inserts nothing.
3. Wait for (or manually trigger) the ETL interval and confirm the record appears in `dbo.tblCallLog` in SQL Server.
4. Only now: ask the team to switch Simotel's webhook registration to this confirmed, tested path (if it isn't already), or leave it as-is if it was already pointed here throughout.
5. Trigger one real call of each type again — internal, inbound external, outbound external — and confirm all three are captured correctly with the right `direction`.

---

## Stage 6 — Go live and watch

Monitor logs for the first real production traffic. Specifically watch for:
- `400` responses — means a field showed up differently than expected; check against what Stage 2 captured.
- `401` responses — token mismatch; check `.env` on the server matches what's configured in Simotel's settings.
- ETL errors in the logs — SQL Server unreachable or a schema mismatch; the ingestion endpoint keeps working regardless, but the cold store falls behind until this is fixed.

If everything in Stage 5 passed, this stage should be uneventful — that's the point of not skipping the earlier ones.
