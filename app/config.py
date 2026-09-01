"""
Central configuration for the telephone call log service.

Everything in this file that is still an open item in the roadmap (see
audit-log-service-roadmap.md's sibling doc for this project) is called out
explicitly below, so Phase 0's payload capture can be turned into code
changes here without touching the rest of the app.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Simotel webhook auth -------------------------------------------
    # OPEN ITEM: confirm in Phase 0 whether the token arrives as a query
    # param (and under what name) or as a header. Default assumes a query
    # param named "api_key"; change SIMOTEL_TOKEN_PARAM_NAME if the real
    # capture shows a different name (e.g. "apikey", "token", "X-APIKEY").
    SIMOTEL_API_TOKEN: str = os.getenv("SIMOTEL_API_TOKEN", "")
    SIMOTEL_TOKEN_PARAM_NAME: str = os.getenv("SIMOTEL_TOKEN_PARAM_NAME", "api_key")

    # --- MongoDB (hot store) --------------------------------------------
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "telephone_log_service")
    MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "call_logs")

    # --- SQL Server (cold store) ----------------------------------------
    SQLSERVER_CONN_STR: str = os.getenv("SQLSERVER_CONN_STR", "")
    SQLSERVER_TABLE: str = os.getenv("SQLSERVER_TABLE", "dbo.tblCallLog")

    # --- ETL --------------------------------------------------------------
    ETL_INTERVAL_MINUTES: int = int(os.getenv("ETL_INTERVAL_MINUTES", "5"))
    ETL_BATCH_SIZE: int = int(os.getenv("ETL_BATCH_SIZE", "500"))

    # --- Direction derivation ---------------------------------------------
    # OPEN ITEM: confirm the real internal numbering plan with the team.
    # Default assumes internal extensions are purely numeric and within
    # this length range; anything outside it is treated as an external
    # number. Adjust once Phase 0 test calls confirm the actual format.
    EXTENSION_MIN_LENGTH: int = int(os.getenv("EXTENSION_MIN_LENGTH", "3"))
    EXTENSION_MAX_LENGTH: int = int(os.getenv("EXTENSION_MAX_LENGTH", "5"))

    # --- Hot store retention ----------------------------------------------
    # OPEN ITEM: confirm retention window with the team (roadmap suggested
    # 90 days as a starting point).
    HOT_STORE_RETENTION_DAYS: int = int(os.getenv("HOT_STORE_RETENTION_DAYS", "90"))


settings = Settings()
