# tools/get_budget_tool.py
from pydantic import BaseModel
from tools.budget_db import fetch_budget
import anyio

class Args(BaseModel):
    day: str

async def run(day: str) -> str:
     return await fetch_budget(day)
