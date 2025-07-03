"""
Budget agent that uses OpenAI function-calling to (1) fetch metrics from
Snowflake and (2) write the proposed split back when the user is happy and says
'apply' / 'commit'.
"""

from langchain_core.prompts import PromptTemplate
from utils import init_llm, extract_day
from datetime import date, datetime
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import OpenAIEmbeddings            # for future RAG
import os
from dotenv import load_dotenv
from textwrap import dedent

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from memory import history 

# new
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferMemory


load_dotenv()

# 0️⃣  Reuse the shared message history object
shared_chat_history = ChatMessageHistory(messages=history)

# ───────────────────────────────────────────────────────────
#  A)  ONE memory object seen by every agent  (shared)
shared_memory = ConversationBufferMemory(
    chat_memory=shared_chat_history,          # <— same underlying list
    memory_key="chat_history",
    return_messages=True,
    input_key="input",        # 👈  ignore `date_hint`
    output_key="output",      # default in AgentExecutor
)

#  B)  SEPARATE memory just for the budget agent  (isolated)
budget_memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
)
# ───────────────────────────────────────────────────────────

# ── Snowflake connection ────────────────────────────────────────────
_db = SQLDatabase.from_uri(
    f"snowflake://{os.getenv('SNOWFLAKE_USER')}:{os.getenv('SNOWFLAKE_PASSWORD')}"
    f"@{os.getenv('SNOWFLAKE_ACCOUNT')}/{os.getenv('SNOWFLAKE_DATABASE')}/"
    f"{os.getenv('SNOWFLAKE_SCHEMA')}?warehouse={os.getenv('SNOWFLAKE_WAREHOUSE')}"
)

# ── Low-level helpers ───────────────────────────────────────────────
def _fetch(date_str: str) -> str:
    """Return today’s (or requested) budget rows as CSV‐styled text."""
    q = f"""
    SELECT channel, spend, clicks, sales
    FROM METRICS
    WHERE DATE = '{date_str}'
    ORDER BY channel;
    """
    #print(date_str)
    return _db.run(q)

def _write_proposal_to_db(markdown: str):
    """
    Parse a Markdown table like

      | channel | current_spend | proposed_spend | Δ% | brief_rationale |
      |---------|---------------|----------------|----|-----------------|
      | google  | 100           | 105            | 5% | Good perf       |

    and insert rows into PROPOSED_BUDGETS.
    """
    import re, textwrap, html
    rows = []
    today = date.today().isoformat()

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
            f"('{today}', '{channel}', {cur}, {prop}, '{rationale}')"
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

# ── Expose helpers as LangChain tools ───────────────────────────────
@tool
def get_budget(day: str) -> str:
    """Return channel metrics for the given ISO date (YYYY-MM-DD)."""
    return _fetch(day)

@tool
def save_proposal(table_markdown: str) -> str:
    """
    Persist the previously proposed Markdown table into the database.
    Returns a human-friendly confirmation string.
    """
    ok = _write_proposal_to_db(table_markdown)
    return "Saved" if ok else "Nothing written"

# ── LLM & prompt ────────────────────────────────────────────────────
MEMORY = shared_memory

llm = ChatOpenAI(model="gpt-4o", temperature=0)

SYSTEM_PROMPT = """
You are a paid-media analyst.

You have access to two tools:
• `get_budget(day: str)`: pull channel metrics for the given date.
• `save_proposal(table_markdown: str)`: save a proposed budget split as a

Your instructions: are:
• Use `get_budget` to pull metrics for the requested day
  (default to the date_hint if provided).
• Re-allocate the given date's spend so total budget stays within ± 5 % of the current total. Analyse the data and reply with **only** a Markdown table:
  | channel | current_spend | proposed_spend | Δ% | brief_rationale |
• Ask the user if they're happy with the new proposed budget, and wait for the user to say “apply” / “commit” or any other form of agreement.
  Then call `save_proposal` with the same table.
• After saving, respond: “✅ New budget split stored.”
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT.strip()),
        # Pass the hint as an extra system message
        ("system", "Date hint: {date_hint}"),
        MessagesPlaceholder("chat_history"),      # ← will be filled from MEMORY
        ("user", "{input}"),
        # <assistant scratchpad> for function calls & responses
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

functions_agent = create_openai_functions_agent(
    llm=llm,
    tools=[get_budget, save_proposal],
    prompt=prompt
)

executor = AgentExecutor(
    agent=functions_agent,
    tools=[get_budget, save_proposal],
    memory=MEMORY,            # ← plug the chosen memory here
    verbose=True,
)


# ── Public entry point used by the orchestrator ────────────────────
def run(question: str) -> str:
    # Provide a hint so the model doesn’t have to parse the date itself
    day = extract_day(question)
    resp: Dict = executor.invoke({"input": question, "date_hint": day})
    return resp["output"]


#llm = init_llm()

ANALYSE_PROMPT = PromptTemplate.from_template("""
You are a helpful budget assistant.
You are able to pull the budget data from the database and analyse it.  
                                                                                     
**Task**
1. Review the channel-level metrics below.
2. Re-allocate the given date's spend so total budget stays within ± 5 % of the current total.
3. Optimise for highest overall ROAS.
4. Output **only** a Markdown table with columns:
   | channel | current_spend | proposed_spend | Δ% | brief_rationale |
          
Metrics:
{rows}
""")

#def run(question: str) -> str:
#    # 1. Figure out which date to fetch.  For MVP assume “today”.
#    day  = extract_day(question)           # e.g. "2025-06-28"
#    #rows = fetch_budget(day)
#
#    if not rows:
#        return f"⚠️ No metrics found for {day}."
#
#    # 2. Let the LLM crunch a recommendation
#    return (ANALYSE_PROMPT | llm).invoke({"rows": rows}).content
