import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db.mongo import get_collection

logger = logging.getLogger("telephone_log_service.etl")


async def run_etl_once() -> None:
    """
    Read unsynced records from Mongo, batch-insert into SQL Server,
    mark them synced. Any failure here is logged and skipped — it
    must never affect the ingestion endpoint (roadmap Phase 4, item 12).
    """
    collection = get_collection()
    cursor = collection.find({"synced_to_sql": False}).limit(settings.ETL_BATCH_SIZE)
    batch = await cursor.to_list(length=settings.ETL_BATCH_SIZE)

    if not batch:
        return

    try:
        from app.db.sql_server import batch_insert

        inserted = batch_insert(batch)
        ids = [doc["_id"] for doc in batch]
        await collection.update_many(
            {"_id": {"$in": ids}}, {"$set": {"synced_to_sql": True}}
        )
        logger.info("ETL: synced %d call log record(s) to SQL Server", inserted)
    except Exception:
        # Deliberately broad: the ETL job must degrade gracefully if
        # SQL Server is unreachable, and retry on the next tick.
        logger.exception("ETL: failed to sync batch to SQL Server, will retry next tick")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_etl_once,
        "interval",
        minutes=settings.ETL_INTERVAL_MINUTES,
        id="call_log_etl",
    )
    scheduler.start()
    return scheduler
