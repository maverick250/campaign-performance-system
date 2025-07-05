# server.py  (abridged)

import os, uuid, json, redis, anyio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import build_graph

graph = build_graph()                 # compile once

# ── 1.  connect to Redis ───────────────────────────────────────────
# Try Redis, else fall back to in-process dict
try:
    import redis
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    _use_redis = True
except ImportError:
    _use_redis = False
    _inproc_sessions = {}

SESSION_TTL = 30 * 60  # 30 min

def load_state(sid: str) -> dict:
    if _use_redis:
        raw = r.get(sid)
        return json.loads(raw) if raw else {}
    else:
        return _inproc_sessions.get(sid, {})

def save_state(sid: str, state: dict):
    # Build a JSON-serializable snapshot
    snapshot = {}
    for k, v in state.items():
        if k == "history" and isinstance(v, list):
            # turn messages into plain strings
            snapshot["history"] = [
                (m.content if hasattr(m, "content") else str(m))
                for m in v
            ]
        elif isinstance(v, (str, int, float, bool, type(None))):
            snapshot[k] = v
        else:
            # skip anything else (e.g. ConversationBufferMemory, callbacks, etc.)
            pass

    data = json.dumps(snapshot)
    if _use_redis:
        r.setex(sid, SESSION_TTL, data)
    else:
        _inproc_sessions[sid] = snapshot

# ── 2.  FastAPI endpoint stays async ───────────────────────────────
app = FastAPI(title="Campaign-Agent API")

class ChatReq(BaseModel):
    session_id: str | None = None
    message:    str

@app.post("/chat")
async def chat(req: ChatReq):
    sid   = req.session_id or str(uuid.uuid4())
    stored = load_state(sid)

    # graph.invoke is still synchronous → run it in a worker thread
    try:
        new_state = await anyio.to_thread.run_sync(
            graph.invoke,
            {"question": req.message},
            stored,
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    save_state(sid, new_state)

    return {
        "session_id": sid,
        "reply"     : new_state["answer"],
        "branch"    : new_state["branch"],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
