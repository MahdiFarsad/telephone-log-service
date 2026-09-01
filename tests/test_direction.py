from app.direction import derive_direction, is_internal_number


def test_internal_number_detection():
    assert is_internal_number("101") is True
    assert is_internal_number("9921") is True
    assert is_internal_number("09121234567") is False  # too long
    assert is_internal_number("09") is False  # too short given range
    assert is_internal_number(None) is False
    assert is_internal_number("") is False


def test_internal_call():
    assert derive_direction("101", "102") == "internal"


def test_inbound_external_call():
    assert derive_direction("09121234567", "205") == "inbound_external"


def test_outbound_external_call():
    assert derive_direction("205", "09121234567") == "outbound_external"


def test_unknown_when_neither_side_recognized():
    assert derive_direction("09121234567", "09359876543") == "unknown"
