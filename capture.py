import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request

app = FastAPI()

LOG_FILE = "capture_log.jsonl"


@app.get("/SimotelLaugger/SimotelLogTabriz")
async def capture(request: Request):
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "full_url": str(request.url),
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print("Captured a Simotel delivery:")
    print(json.dumps(entry, indent=2))
    return {"status": "received"}


@app.get("/health")
async def health():
    return {"status": "ok"}
