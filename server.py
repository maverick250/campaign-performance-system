# server.py
import uvicorn, uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import build_graph          # ← your LangGraph builder

graph = build_graph()                         # compile once

app = FastAPI(title="Campaign-Agent API")

class ChatReq(BaseModel):
    session_id: str | None = None             # allow stateless too
    message: str

# very small in-memory session store
_sessions: dict[str, dict] = {}

@app.post("/chat")
def chat(req: ChatReq):
    sid = req.session_id or str(uuid.uuid4())
    state = _sessions.get(sid, {})            # graph state is a dict
    try:
        # stream=False so we get the final merged state
        #new_state = graph.invoke({"question": req.message}, state=state)
        new_state = graph.invoke({"question": req.message}, state)
    except Exception as e:
        raise HTTPException(500, str(e))

    _sessions[sid] = new_state                # persist between turns
    return {
        "session_id": sid,
        "reply": new_state["answer"],
        "branch": new_state["branch"],        # optional debug
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
