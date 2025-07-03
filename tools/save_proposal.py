# tools/save_proposal_tool.py
from pydantic import BaseModel
from tools.budget_db import write_proposal

class Args(BaseModel):
    budget_date: str
    table_markdown: str

def run(budget_date: str, table_markdown: str) -> str:
    ok = write_proposal(budget_date, table_markdown)
    return "Saved" if ok else "Nothing written"
