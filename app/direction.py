"""
Derives call direction (internal / inbound_external / outbound_external)
from Simotel's CDR data.

PRIMARY signal: Simotel's own documented `type` field
(https://simotel.com/wiki/en/developers/simotelwebhooks/events/cdr/),
which has a defined enum: incoming / outgoing / local / feature / (undefined).
This is authoritative — confirmed against real examples, including one
that the number-length heuristic below got wrong (dst="66", type="local":
a 2-digit internal short-code, not an external number).

FALLBACK signal: number-length heuristic, used only when `call_type` is
missing or not one of the recognized values. Kept as a fallback rather
than removed entirely, in case `type` is ever absent from a delivery.
"""
from app.config import settings

_TYPE_TO_DIRECTION = {
    "local": "internal",
    "incoming": "inbound_external",
    "outgoing": "outbound_external",
    # "feature" calls (e.g. call parking retrieval, voicemail access)
    # aren't a call between two external parties in the usual sense —
    # kept as its own category rather than forced into one of the three,
    # so it's visible in the data instead of silently miscategorized.
    "feature": "feature",
}


def is_internal_number(number: str | None) -> bool:
    if not number:
        return False
    digits = number.strip()
    if not digits.isdigit():
        return False
    return settings.EXTENSION_MIN_LENGTH <= len(digits) <= settings.EXTENSION_MAX_LENGTH


def derive_direction(
    caller_number: str | None,
    callee_number: str | None,
    call_type: str | None = None,
) -> str:
    if call_type:
        mapped = _TYPE_TO_DIRECTION.get(call_type.strip().lower())
        if mapped:
            return mapped
        # call_type present but not a recognized value (e.g. Simotel's
        # documented "no defined") — fall through to the heuristic
        # rather than guessing at an unfamiliar value.

    caller_internal = is_internal_number(caller_number)
    callee_internal = is_internal_number(callee_number)

    if caller_internal and callee_internal:
        return "internal"
    if not caller_internal and callee_internal:
        return "inbound_external"
    if caller_internal and not callee_internal:
        return "outbound_external"

    return "unknown"
