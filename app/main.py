import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response, status
from pydantic import ValidationError

from app.config import settings
from app.db.mongo import ensure_indexes, insert_call_log, close_client
from app.direction import derive_direction
from app.jobs.etl import start_scheduler
from app.models.call_log import SimotelCdrParams
from app.security import is_valid_token

logger = logging.getLogger("telephone_log_service")

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    global _scheduler
    _scheduler = start_scheduler()
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
    await close_client()


app = FastAPI(title="Telephone Call Log Service", lifespan=lifespan)


@app.get("/SimotelLaugger/SimotelLogTabriz")
async def receive_call_log(request: Request, response: Response):
    params = dict(request.query_params)

    # 1) Validate token first, before touching anything else. Never log
    #    or echo the token value (roadmap Phase 5).
    provided_token = params.pop(settings.SIMOTEL_TOKEN_PARAM_NAME, None)
    if not is_valid_token(provided_token):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"detail": "unauthorized"}

    # 2) Parse/validate the remaining params.
    try:
        cdr = SimotelCdrParams.model_validate(params)
    except ValidationError as exc:
        logger.warning("Rejected malformed Simotel payload: %s", exc.errors())
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "invalid payload"}

    # 3) Derive direction — primary signal is Simotel's documented
    #    `type` field (incoming/outgoing/local/feature), falling back
    #    to the number-length heuristic only if `type` is missing or
    #    unrecognized. Strip the recording filename (never persisted —
    #    metadata only, per requirement).
    direction = derive_direction(cdr.caller_number, cdr.callee_number, cdr.call_type)
    raw_payload = cdr.model_dump(exclude={"record"})

    document = {
        "call_id": cdr.call_id,
        "direction": direction,
        "caller_number": cdr.caller_number,
        "callee_number": cdr.callee_number,
        "call_type": cdr.call_type,
        "queue": cdr.queue,
        "start_time": cdr.start_time,
        "ring_time": cdr.ring_time,
        "answer_time": cdr.answer_time,
        "end_time": cdr.end_time,
        "duration": cdr.duration,
        "billsec": cdr.billsec,
        "wait": cdr.wait,
        "disposition": cdr.disposition,
        "entry_point": cdr.entry_point,
        "outgoing_point": cdr.outgoing_point,
        "received_at": datetime.now(timezone.utc),
        "synced_to_sql": False,
        "raw_payload": raw_payload,
    }

    # 4) Async insert. Duplicate call_id -> safe no-op, not an error
    #    (guards against a retried delivery).
    await insert_call_log(document)

    # 5) Immediate response. Confirmed with the team: Simotel expects
    #    HTTP 200 here (not 204) and does not parse the response body
    #    ("response is undefined") — an empty 200 satisfies both.
    response.status_code = status.HTTP_200_OK
    return {}


@app.get("/health")
async def health():
    return {"status": "ok"}
