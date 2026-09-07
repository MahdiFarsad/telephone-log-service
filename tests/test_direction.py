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


def test_type_field_is_authoritative_over_number_heuristic():
    # dst="66" is only 2 digits — the number heuristic alone would call
    # this external. type="local" (Simotel's documented enum) must win.
    assert derive_direction("992", "66", call_type="local") == "internal"


def test_type_incoming_maps_to_inbound_external():
    assert derive_direction("09123456789", "553", call_type="incoming") == "inbound_external"


def test_type_outgoing_maps_to_outbound_external():
    assert derive_direction("553", "09123456789", call_type="outgoing") == "outbound_external"


def test_type_feature_is_its_own_category():
    assert derive_direction("553", "*97", call_type="feature") == "feature"


def test_unrecognized_type_falls_back_to_heuristic():
    # e.g. Simotel's documented "no defined" value
    assert derive_direction("101", "102", call_type="no defined") == "internal"


def test_missing_type_falls_back_to_heuristic():
    assert derive_direction("101", "102", call_type=None) == "internal"


def test_unknown_when_neither_side_recognized_and_no_type():
    assert derive_direction("09121234567", "09359876543") == "unknown"
