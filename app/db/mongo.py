from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client


def get_collection() -> AsyncIOMotorCollection:
    return get_client()[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION]


async def ensure_indexes() -> None:
    """
    Call once at startup. call_id is unique — this is the idempotency
    guard against duplicate webhook deliveries (see roadmap §3.4).
    """
    collection = get_collection()
    await collection.create_index("call_id", unique=True)
    await collection.create_index([("start_time", -1)])
    await collection.create_index([("caller_number", 1), ("start_time", -1)])
    await collection.create_index([("callee_number", 1), ("start_time", -1)])
    await collection.create_index([("direction", 1), ("start_time", -1)])
    await collection.create_index("synced_to_sql")


async def insert_call_log(document: dict) -> bool:
    """
    Insert one call record. Returns True if inserted, False if this
    call_id already existed (duplicate delivery treated as a safe
    no-op, not an error).
    """
    from pymongo.errors import DuplicateKeyError

    try:
        await get_collection().insert_one(document)
        return True
    except DuplicateKeyError:
        return False


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
