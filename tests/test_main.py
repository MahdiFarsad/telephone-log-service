import pytest
from httpx import AsyncClient, ASGITransport

from app import main  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def fake_mongo(monkeypatch):
    """Replace the real Mongo client with mongomock so no real DB is needed,
    and pin config values directly on the settings singleton (rather than
    via env vars, since it may already be imported by the time this runs)."""
    monkeypatch.setattr(settings, "SIMOTEL_API_TOKEN", "test-token-123")
    monkeypatch.setattr(settings, "SIMOTEL_TOKEN_PARAM_NAME", "api_key")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "test_db")

    from mongomock_motor import AsyncMongoMockClient

    client = AsyncMongoMockClient()

    def fake_get_collection():
        return client[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]

    monkeypatch.setattr("app.db.mongo.get_collection", fake_get_collection)
    return client


BASE_PARAMS = {
    "event_name": "CDR",
    "unique_id": "1700000000.123",
    "src": "101",
    "dst": "102",
    "type": "local",
    "billsec": "31",
    "disposition": "ANSWERED",
    "starttime": "2026-01-01 10:00:00",
    "endtime": "2026-01-01 10:00:34",
    "wait": "3",
    "api_key": "test-token-123",
}

# Real example payloads confirmed by the team (as GET query params).
REAL_ANSWERED_EXAMPLE = {
    "event_name": "CDR",
    "starttime": "2021-01-16 06:30:37.471398",
    "endtime": "2021-01-16 06:30:37.471398",
    "src": "991",
    "dst": "993",
    "type": "local",
    "disposition": "ANSWERED",
    "billsec": "9",
    "wait": "11",
    "record": "20210116_1610778618.378.mp3",
    "unique_id": "1610778618.378",
    "api_key": "test-token-123",
}

REAL_NO_ANSWER_EXAMPLE = {
    "event_name": "CDR",
    "starttime": "2021-01-16 07:17:00.508368",
    "endtime": "2021-01-16 07:17:01.508368",
    "src": "992",
    "dst": "66",
    "type": "local",
    "disposition": "NO ANSWER",
    "duration": "1",
    "wait": "1",
    "unique_id": "1610781419.387",
    "api_key": "test-token-123",
}


@pytest.mark.asyncio
async def test_valid_request_returns_200_and_is_stored(fake_mongo):
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            resp = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=BASE_PARAMS
            )
    assert resp.status_code == 200

    collection = fake_mongo[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]
    doc = await collection.find_one({"call_id": "1700000000.123"})
    assert doc is not None
    assert doc["direction"] == "internal"
    assert doc["call_type"] == "local"
    assert doc["wait"] == 3
    assert "record" not in doc
    assert doc["synced_to_sql"] is False


@pytest.mark.asyncio
async def test_real_answered_example_payload(fake_mongo):
    """Exact real payload from the team: ANSWERED call, has billsec, no duration."""
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            resp = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=REAL_ANSWERED_EXAMPLE
            )
    assert resp.status_code == 200

    collection = fake_mongo[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]
    doc = await collection.find_one({"call_id": "1610778618.378"})
    assert doc is not None
    assert doc["billsec"] == 9
    assert doc["duration"] is None
    assert doc["wait"] == 11
    assert "record" not in doc  # never persisted, even though Simotel sent it


@pytest.mark.asyncio
async def test_real_no_answer_example_payload(fake_mongo):
    """Exact real payload from the team: NO ANSWER call, has duration, no billsec, no record."""
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            resp = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=REAL_NO_ANSWER_EXAMPLE
            )
    assert resp.status_code == 200

    collection = fake_mongo[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]
    doc = await collection.find_one({"call_id": "1610781419.387"})
    assert doc is not None
    assert doc["duration"] == 1
    assert doc["billsec"] is None
    assert doc["disposition"] == "NO ANSWER"
    # This is the case the number-length heuristic got wrong: dst="66"
    # is only 2 digits, but type="local" correctly identifies it as
    # internal — confirming the type-based signal overrides the
    # heuristic as intended.
    assert doc["direction"] == "internal"


@pytest.mark.asyncio
async def test_invalid_token_rejected_and_not_stored(fake_mongo):
    bad_params = dict(BASE_PARAMS, api_key="wrong-token")
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            resp = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=bad_params
            )
    assert resp.status_code == 401

    collection = fake_mongo[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]
    doc = await collection.find_one({"call_id": "1700000000.123"})
    assert doc is None


@pytest.mark.asyncio
async def test_missing_required_field_returns_400(fake_mongo):
    broken_params = dict(BASE_PARAMS)
    del broken_params["disposition"]
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            resp = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=broken_params
            )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_call_id_is_safe_noop(fake_mongo):
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with main.lifespan(main.app):
            first = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=BASE_PARAMS
            )
            second = await client.get(
                "/SimotelLaugger/SimotelLogTabriz", params=BASE_PARAMS
            )
    assert first.status_code == 200
    assert second.status_code == 200  # duplicate delivery still acknowledged

    collection = fake_mongo[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]
    count = await collection.count_documents({"call_id": "1700000000.123"})
    assert count == 1  # not duplicated
