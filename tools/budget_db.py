# tools/budget_db.py
from datetime import date
from textwrap import dedent
from langchain_community.utilities.sql_database import SQLDatabase
import os
from dotenv import load_dotenv
import anyio

load_dotenv()

_db = SQLDatabase.from_uri(
    f"snowflake://{os.getenv('SNOWFLAKE_USER')}:{os.getenv('SNOWFLAKE_PASSWORD')}"
    f"@{os.getenv('SNOWFLAKE_ACCOUNT')}/{os.getenv('SNOWFLAKE_DATABASE')}/"
    f"{os.getenv('SNOWFLAKE_SCHEMA')}?warehouse={os.getenv('SNOWFLAKE_WAREHOUSE')}"
)

def fetch_budget_sync(day: str) -> str:
    q = f"""
      SELECT channel, spend, clicks, sales
      FROM METRICS
      WHERE DATE = '{day}'
      ORDER BY channel;
    """
    return _db.run(q)

async def fetch_budget(day: str) -> str:
    return await anyio.to_thread.run_sync(fetch_budget_sync, day)

def write_proposal_sync(day: str, markdown: str) -> bool:
    """
    Parse a Markdown table like

      | channel | current_spend | proposed_spend | Δ% | brief_rationale |
      |---------|---------------|----------------|----|-----------------|
      | google  | 100           | 105            | 5% | Good perf       |

    and insert rows into PROPOSED_BUDGETS.
    """

    rows = []
    for line in markdown.splitlines():
        if not line.startswith("|"):
            continue                        # not a table row
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:                  # too short
            continue
        if cells[0].lower() == "channel":   # header row
            continue
        if set(cells[0]) <= {"-"}:          # separator row
            continue

        channel, cur, prop, _delta, rationale = cells[:5]
        # Escape single quotes inside rationale
        rationale = rationale.replace("'", "''")
        rows.append(
            f"('{day}', '{channel}', {cur}, {prop}, '{rationale}')"
        )

    if not rows:
        return False

    sql = dedent(f"""
        INSERT INTO PROPOSED_BUDGETS 
            (proposal_date, channel, current_spend, proposed_spend, rationale)
        VALUES {", ".join(rows)};
    """)
    _db.run(sql)            # reuse the same SQLDatabase instance
    return True

async def write_proposal(day: str, markdown: str) -> bool:
    return await anyio.to_thread.run_sync(write_proposal_sync, day, markdown)