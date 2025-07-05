"""
Budget agent that uses OpenAI function-calling to (1) fetch metrics from
Snowflake and (2) write the proposed split back when the user is happy and says
'apply' / 'commit'.
"""

from langchain_core.prompts import PromptTemplate
from utils import init_llm, extract_day
from langchain_community.utilities.sql_database import SQLDatabase
from dotenv import load_dotenv

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from memory import history 

import httpx

# new
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferMemory

#from langchain_openai.agents import create_openai_mcp_agent

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
# ───────────────────────────────────────────────────────────


# ── LLM & prompt ────────────────────────────────────────────────────
MEMORY = shared_memory

SYSTEM_PROMPT = """
You are a paid-media analyst.

You have access to two tools:
• `get_budget(day: str)`: pull channel metrics for the given date.
• `save_proposal(table_markdown: str)`: save a proposed budget split.

Your instructions: are:
• Use `get_budget` to pull metrics for the requested day
  (default to the date_hint if provided).
• Re-allocate the given date's spend so total budget stays within ± 5 % of the current total. Analyse the data and reply with **only** a Markdown table:
  | channel | current_spend | proposed_spend | Δ% | brief_rationale |
• Ask the user if they're happy with the new proposed budget, and wait for the user to say “apply” / “commit” or any other form of agreement.
  Then call `save_proposal` with the same table.
• After saving, respond: “✅ New budget split stored." **Do not call any tool again in the same turn.**

• When you call `save_proposal`, pass both:
    • `budget_date` – the date you fetched
    • `table_markdown` – the Markdown table you proposed
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

MCP_BASE = "http://localhost:9000/mcp"

@tool
def get_budget(day: str) -> str:
    """Return channel metrics for the given ISO date (YYYY-MM-DD)."""
    r = httpx.post(f"{MCP_BASE}/get_budget/invoke",
                   json={"arguments": {"day": day}},
                   timeout=15)
    r.raise_for_status()
    return r.json()["result"]

@tool
def save_proposal(budget_date: str, table_markdown: str) -> str:
    """Persist a proposed budget split."""
    r = httpx.post(
        f"{MCP_BASE}/save_proposal/invoke",
        json={"arguments": {
            "budget_date": budget_date,
            "table_markdown": table_markdown,
        }},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["result"]

llm = ChatOpenAI(model="gpt-4o", temperature=0)

functions_agent = create_openai_functions_agent(
    llm=llm,
    tools=[get_budget, save_proposal],
    prompt=prompt,
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

