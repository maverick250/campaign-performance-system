# tools/get_budget_tool.py
from pydantic import BaseModel
from tools.budget_db import fetch_budget

class Args(BaseModel):
    day: str

def run(day: str) -> str:
    return fetch_budget(day)
