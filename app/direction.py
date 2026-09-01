"""
Derives call direction (internal / inbound_external / outbound_external)
from caller/callee numbers, since Simotel's CDR payload doesn't include
this directly.

Placeholder heuristic, pending the real numbering plan (see Open Items
in the roadmap): an "internal" number is purely numeric digits within
[EXTENSION_MIN_LENGTH, EXTENSION_MAX_LENGTH]. Anything else (longer
numbers, numbers starting with 0/+ typical of external dialing, etc.)
is treated as external.

This is intentionally isolated from the endpoint so it can be swapped
or refined after Phase 0's real test calls without touching request
handling.
"""
from app.config import settings


def is_internal_number(number: str | None) -> bool:
    if not number:
        return False
    digits = number.strip()
    if not digits.isdigit():
        return False
    return settings.EXTENSION_MIN_LENGTH <= len(digits) <= settings.EXTENSION_MAX_LENGTH


def derive_direction(caller_number: str | None, callee_number: str | None) -> str:
    caller_internal = is_internal_number(caller_number)
    callee_internal = is_internal_number(callee_number)

    if caller_internal and callee_internal:
        return "internal"
    if not caller_internal and callee_internal:
        return "inbound_external"
    if caller_internal and not callee_internal:
        return "outbound_external"

    # Neither side looks like a known extension — can't confidently
    # classify. Surface this rather than silently guessing, so it's
    # visible in the data instead of hidden inside a wrong label.
    return "unknown"
