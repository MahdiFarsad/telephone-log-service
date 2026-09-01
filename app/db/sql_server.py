from app.config import settings

_INSERT_SQL = f"""
INSERT INTO {settings.SQLSERVER_TABLE}
    (CallId, Direction, CallerNumber, CalleeNumber, Queue,
     StartTime, RingTime, AnswerTime, EndTime,
     Duration, BillSec, Disposition, ReceivedAt)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def get_connection():
    # Imported lazily so the rest of the app (and its tests) don't need
    # the ODBC driver installed to run.
    import pyodbc

    return pyodbc.connect(settings.SQLSERVER_CONN_STR)


def batch_insert(records: list[dict]) -> int:
    """
    Insert a batch of normalized call-log dicts into SQL Server.
    Returns the number of rows inserted. Errors here should be caught
    by the caller (the ETL job) and must never affect the ingestion
    endpoint's own request path (roadmap Phase 4, item 12).
    """
    if not records:
        return 0

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        rows = [
            (
                r["call_id"],
                r["direction"],
                r["caller_number"],
                r["callee_number"],
                r.get("queue"),
                r["start_time"],
                r.get("ring_time"),
                r.get("answer_time"),
                r["end_time"],
                r["duration"],
                r["billsec"],
                r["disposition"],
                r["received_at"],
            )
            for r in records
        ]
        cursor.executemany(_INSERT_SQL, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()
