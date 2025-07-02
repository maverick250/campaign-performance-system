from orchestrator import build_graph

graph = build_graph()

while True:
    q = input("\nYou ➜ ")
    if q.lower() in {"exit", "quit"}:
        break
    state = None
    for step in graph.stream({"question": q}, stream_mode="values"):
        state = step
    print("\nAgent ➜", state["answer"])
