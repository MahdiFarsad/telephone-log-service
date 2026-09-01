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
    """Raw shape of one Simotel Cdr/CdrQueue webhook delivery."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    event_name: str = Field(alias="event_name")
    call_id: str = Field(alias="unique_id")
    caller_number: str = Field(alias="src")
    callee_number: str = Field(alias="dst")
    queue: Optional[str] = Field(default=None, alias="queue")
    duration: int = Field(alias="duration")
    billsec: int = Field(alias="billsec")
    disposition: str = Field(alias="disposition")
    start_time: str = Field(alias="starttime")
    ring_time: Optional[str] = Field(default=None, alias="ringtime")
    answer_time: Optional[str] = Field(default=None, alias="answeredtime")
    end_time: str = Field(alias="endtime")
    # Received but intentionally never persisted downstream — see
    # strip_recording_field() in app/main.py.
    record: Optional[str] = Field(default=None, alias="record")


class CallLogRecord(BaseModel):
    """Normalized record as stored in MongoDB (collection: call_logs)."""

    call_id: str
    direction: str
    caller_number: str
    callee_number: str
    queue: Optional[str] = None
    start_time: str
    ring_time: Optional[str] = None
    answer_time: Optional[str] = None
    end_time: str
    duration: int
    billsec: int
    disposition: str
    received_at: datetime
    synced_to_sql: bool = False
    raw_payload: dict
