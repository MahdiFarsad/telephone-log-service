"""
Request/storage models for the telephone call log service.

Field names on SimotelCdrParams match Simotel's documented Cdr/CdrQueue
webhook schema (unique_id, src, dst, queue, billsec, duration,
disposition, starttime, ringtime, answeredtime, endtime, record).

OPEN ITEM: these are the *documented* names. Phase 0's real payload
capture may show slightly different names for this specific install —
if so, update the Field(alias=...) values below; nothing else in the
app needs to change since everything downstream reads the Python
attribute names, not the wire names.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class SimotelCdrParams(BaseModel):
    """
    Raw shape of one Simotel Cdr webhook delivery.

    Field set confirmed against Simotel's official documentation table
    (https://simotel.com/wiki/en/developers/simotelwebhooks/events/cdr/)
    AND real examples from the team — used together since the two
    disagree on a couple of points (noted inline).

    Confirmed quirks vs. a naive reading of the docs:
      - `billsec` is only present on ANSWERED calls; `duration` is only
        present on NO ANSWER calls in the real examples seen. Both are
        Optional — a payload has one or the other, never neither, but
        the model can't assume which.
      - `type` has a documented enum: incoming / outgoing / local /
        feature / "no defined". This is the PRIMARY signal for
        direction (see app/direction.py) — more reliable than
        inferring from number length.
      - The docs describe `billsec` as "wait time before answer" and
        `wait` as "call wait time" — this reads backwards from
        standard telephony convention and contradicts itself (two
        different "wait" concepts). Treated as a likely translation
        error, not fact, pending explicit confirmation. Both fields
        are stored as-is regardless of which interpretation is right.
      - `record` is only present when a recording exists (answered
        calls) — confirmed correct, and never persisted downstream
        regardless (metadata only, per requirement).
      - `entry_point`/`outgoing_point` (gateway names), `cuid` (the
        docs' name for what real deliveries call `unique_id`),
        `poll_point`/`poll_lable` (survey data), and
        `originated_call_id` (links both legs of a transferred call)
        are documented fields not seen in the two real examples yet —
        captured as optional so nothing is silently dropped if/when
        they do appear.
      - `event_name` arrives as "CDR" (uppercase) in real deliveries,
        not "Cdr" as in Simotel's own older documented sample. Not
        gated on exact casing, so this needs no code change.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    event_name: str = Field(alias="event_name")
    call_id: str = Field(alias="unique_id")
    caller_number: str = Field(alias="src")
    callee_number: str = Field(alias="dst")
    call_type: Optional[str] = Field(default=None, alias="type")
    queue: Optional[str] = Field(default=None, alias="queue")
    duration: Optional[int] = Field(default=None, alias="duration")
    billsec: Optional[int] = Field(default=None, alias="billsec")
    wait: Optional[int] = Field(default=None, alias="wait")
    disposition: str = Field(alias="disposition")
    start_time: str = Field(alias="starttime")
    ring_time: Optional[str] = Field(default=None, alias="ringtime")
    answer_time: Optional[str] = Field(default=None, alias="answeredtime")
    end_time: str = Field(alias="endtime")
    entry_point: Optional[str] = Field(default=None, alias="entry_point")
    outgoing_point: Optional[str] = Field(default=None, alias="outgoing_point")
    cuid: Optional[str] = Field(default=None, alias="cuid")
    poll_point: Optional[str] = Field(default=None, alias="poll_point")
    poll_label: Optional[str] = Field(default=None, alias="poll_lable")
    originated_call_id: Optional[str] = Field(default=None, alias="originated_call_id")
    # Received but intentionally never persisted downstream — see
    # strip_recording_field() in app/main.py.
    record: Optional[str] = Field(default=None, alias="record")


class CallLogRecord(BaseModel):
    """Normalized record as stored in MongoDB (collection: call_logs)."""

    call_id: str
    direction: str
    caller_number: str
    callee_number: str
    call_type: Optional[str] = None
    queue: Optional[str] = None
    start_time: str
    ring_time: Optional[str] = None
    answer_time: Optional[str] = None
    end_time: str
    duration: Optional[int] = None
    billsec: Optional[int] = None
    wait: Optional[int] = None
    disposition: str
    entry_point: Optional[str] = None
    outgoing_point: Optional[str] = None
    received_at: datetime
    synced_to_sql: bool = False
    raw_payload: dict
