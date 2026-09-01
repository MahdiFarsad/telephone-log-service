"""
Phase 0 capture tool — NOT the real service.

Run this temporarily at the registered path
(/SimotelLaugger/SimotelLogTabriz) to see exactly what Simotel sends:
every query param name, and where the token actually lives (query
param vs. header). It logs everything to capture_log.jsonl and always
returns 200, so it won't cause Simotel to treat the delivery as failed.

Usage:
    pip install fastapi "uvicorn[standard]"
    uvicorn capture:app --host 0.0.0.0 --port 8000

Then either:
  (a) temporarily point Simotel's webhook path at this server/port, or
  (b) if it's already pointed at 192.168.1.18/SimotelLaugger/SimotelLogTabriz,
      run this on that exact path/port instead of the real app.py,
      trigger one real call, then swap back to the real service.

After one test call (try to get one of each: internal, inbound
external, outbound external), open capture_log.jsonl and send me its
contents — that's all Phase 0 needs.
"""
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
