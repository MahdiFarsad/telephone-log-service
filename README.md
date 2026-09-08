# Telephone Call Log Service

Receives call-end (CDR) webhook events from a Simotel PBX and logs every call — internal, inbound external, and outbound external — as metadata (no audio) into a two-tier storage pattern: MongoDB for fast/quick-access lookups, SQL Server for the permanent record. Same architecture as the company's existing MEAS II audit log service.

For the full design rationale, confirmed findings from real Simotel data, and open items, see [`PROJECT_REPORT.md`](./PROJECT_REPORT.md). For a stage-by-stage guide from local testing through production deployment, see [`TESTING_AND_DEPLOYMENT.md`](./TESTING_AND_DEPLOYMENT.md).

## What it does

- Exposes one endpoint: `GET /SimotelLaugger/SimotelLogTabriz`
- Simotel calls it once per finished call, with call data as query parameters and an API token
- Validates the token, parses the payload, derives call direction, strips any recording filename (metadata only — no audio is ever stored), and inserts into MongoDB
- A scheduled job periodically copies new records into SQL Server for permanent reporting

## Call direction

Derived from Simotel's own `type` field (confirmed enum: `incoming`, `outgoing`, `local`, `feature`, `no defined`):

| `type` | Stored `direction` |
|---|---|
| `local` | `internal` |
| `incoming` | `inbound_external` |
| `outgoing` | `outbound_external` |
| `feature` | `feature` |
| missing / `no defined` | falls back to a number-length heuristic |

## Project structure

```
app/
  main.py           - FastAPI app and the webhook endpoint
  config.py         - all settings, loaded from .env
  direction.py      - call direction derivation logic
  security.py       - API token validation
  models/
    call_log.py     - Pydantic request model + stored record shape
  db/
    mongo.py        - MongoDB (hot store) access
    sql_server.py   - SQL Server (cold store) access
  jobs/
    etl.py          - scheduled Mongo -> SQL Server sync job
capture.py           - standalone tool to capture and log a real Simotel
                       payload for troubleshooting (not part of the app)
sql/
  create_table.sql  - SQL Server table DDL
tests/
  test_direction.py - unit tests for direction derivation
  test_main.py      - endpoint tests (token, parsing, idempotency, real
                       payload examples), using mongomock — no real DB needed
```

## Local setup

```bash
git clone https://github.com/MahdiFarsad/telephone-log-service
cd telephone-log-service
pip install -r requirements.txt
cp .env.example .env
# edit .env — set SIMOTEL_API_TOKEN and MONGO_URI at minimum
uvicorn app.main:app --reload
```

`pyodbc` (used for SQL Server) requires system ODBC libraries to build. If it fails to install locally, remove it from `requirements.txt` — it isn't needed to run or test the ingestion endpoint itself, only the SQL Server ETL step.

## Running tests

```bash
pip install httpx pytest pytest-asyncio mongomock-motor
pytest tests/ -v
```

17 tests, all running against a simulated MongoDB (`mongomock-motor`) — no real database required. Covers token validation, payload parsing, direction derivation (including all four confirmed `type` values), duplicate-delivery idempotency, and both real payload examples provided by the team.

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `SIMOTEL_API_TOKEN` | Must match the token configured in Simotel's webhook settings |
| `SIMOTEL_TOKEN_PARAM_NAME` | Query param name the token arrives in (confirmed: `api_key`) |
| `MONGO_URI`, `MONGO_DB_NAME`, `MONGO_COLLECTION` | Hot store connection |
| `SQLSERVER_CONN_STR`, `SQLSERVER_TABLE` | Cold store connection |
| `ETL_INTERVAL_MINUTES`, `ETL_BATCH_SIZE` | Sync job tuning |
| `EXTENSION_MIN_LENGTH`, `EXTENSION_MAX_LENGTH` | Fallback direction heuristic, used only when Simotel's `type` field is missing |
| `HOT_STORE_RETENTION_DAYS` | Suggested retention window for the hot store |

## Deployment

Intended to run on `192.168.1.18` — the same server already running the audit log service — either as an additional route in that existing FastAPI app, or as a sibling process on the same box:

1. Provision a new MongoDB database and a new SQL Server database/schema (separate from the audit log service's own data and from `MEAS05`). Run `sql/create_table.sql` against SQL Server.
2. Set the real `.env` values on the server. Never commit this file.
3. Run as a systemd service (Linux) or Windows Service, configured to start automatically on reboot.
4. Confirm Simotel's webhook settings point at the deployed, tested path before relying on it in production.

Full step-by-step: see `TESTING_AND_DEPLOYMENT.md`.

## Known open items

Tracked in detail in `PROJECT_REPORT.md` §8 — none block further development, but should be confirmed before/soon after go-live:
- Whether `billsec` represents talk time or ring time (the docs' own description is self-contradictory; real example data suggests talk time)
- Simotel PBX's actual IP address, for firewall rules
- Timezone of `starttime`/`endtime` (Simotel's default is UTC, not yet explicitly confirmed for this install)
