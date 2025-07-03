# serve.py
from fastapi import FastAPI, Request
from orchestrator import build_graph

from dotenv import load_dotenv
load_dotenv()

graph = build_graph()
app = FastAPI(title="Marketing-Assistant", version="0.1.0")

@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    user_msg = body["message"]

    answer = None
    for step in graph.stream({"question": user_msg}, stream_mode="values"):
        answer = step["answer"]

    return {"answer": answer}
