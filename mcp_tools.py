# mcp_tools.py
import importlib, pkgutil
from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
import inspect

load_dotenv()

app = FastAPI(title="MCP-Tool-Hub")
mcp = APIRouter(prefix="/mcp")          # renamed var for clarity
app.include_router(mcp)

def register_tool_pkg(mod):
    name = mod.__name__.split(".")[-1]
    schema_route = f"/{name}/schema"
    invoke_route = f"/{name}/invoke"

    args_model: BaseModel = mod.Args      # type: ignore[attr-defined]
    run_fn = mod.run

    @mcp.get(schema_route)
    async def schema():
        return args_model.schema()

    @mcp.post(invoke_route)
    async def invoke(payload: dict):
        if "arguments" not in payload:
            raise HTTPException(422, detail="Missing 'arguments'")
        args = args_model(**payload["arguments"])
        result = run_fn(**args.dict())

        # if the tool returned a coroutine, await it
        if inspect.iscoroutine(result):
            result = await result

        return {"result": result}

    print(f"Registered MCP tool: {name}")

# auto-discover
for _, module_name, _ in pkgutil.iter_modules(["tools"]):
    mod = importlib.import_module(f"tools.{module_name}")
    if hasattr(mod, "Args") and hasattr(mod, "run"):
        register_tool_pkg(mod)

# include the router **after** all tools are registered
app.include_router(mcp)

@app.get("/manifest")
def manifest():
    return [
        {"name": r.path.split("/")[2], "schema": r.path}
        for r in app.routes if r.path.endswith("/schema")
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
