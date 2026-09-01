# Telephone Call Log Service

Receives call-end (CDR) webhook deliveries from Simotel and stores them in
MongoDB (hot store) and SQL Server (cold store, via a scheduled ETL job).
Same pattern as the MEAS II audit log service — see the project roadmap
for full design rationale.

## Status

This is a working skeleton, tested against the **documented** Simotel
CDR field names (`unique_id`, `src`, `dst`, `queue`, `billsec`,
`duration`, `disposition`, `starttime`, `ringtime`, `answeredtime`,
`endtime`, `record`). It has **not** been tested against a real Simotel
delivery yet. Before pointing Simotel's webhook at this service:

1. **Run Phase 0** — capture one real webhook delivery (test call or
   throwaway logging endpoint) and confirm the actual query-param names
   and the token param/header name match `app/models/call_log.py` and
   `app/config.py`. Adjust the `Field(alias=...)` values and
   `SIMOTEL_TOKEN_PARAM_NAME` if they differ.
2. **Confirm the numbering plan** with the team and tune
   `EXTENSION_MIN_LENGTH` / `EXTENSION_MAX_LENGTH` in `.env` (or rework
   `app/direction.py` if the real format isn't just "digit length" —
   e.g. if extensions share a length with external numbers, a prefix or
   allow-list would be more reliable than length).
3. **Provision the databases**: create a new MongoDB database and a new
   SQL Server database/schema on `192.168.1.18`, separate from the audit
   log service's own `log_user_activity` collection and `MEAS05`. Run
   `sql/create_table.sql` against the SQL Server side.
4. **Install the ODBC driver** for `pyodbc` on the target server (not
   needed for local dev/testing, only for the ETL job to actually reach
   SQL Server).

## Local setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with real values
uvicorn app.main:app --reload
```

## Running tests

```bash
pip install httpx pytest pytest-asyncio mongomock-motor
pytest tests/ -v
```

Tests use `mongomock-motor` to simulate MongoDB — no real database
needed to validate token checking, payload validation, direction
derivation, or duplicate-delivery handling. They do **not** cover the
SQL Server ETL path, since that requires a real SQL Server instance and
the ODBC driver.

## Endpoints

- `GET /SimotelLaugger/SimotelLogTabriz` — the Simotel webhook receiver.
  Expects the token as a query param (name configurable via
  `SIMOTEL_TOKEN_PARAM_NAME`, default `api_key`).
- `GET /health` — basic liveness check.

## Deployment

Per the roadmap, this should run on `192.168.1.18` alongside the
existing audit log service — either as an additional route mounted
into that service's FastAPI app, or as a sibling Uvicorn/Gunicorn
process on the same box. `app/main.py` is a standalone `FastAPI()`
instance so it can be run either way; if merging into the audit log
app, import `app.main.app`'s router and `include_router()` it there
instead of running this file directly.
