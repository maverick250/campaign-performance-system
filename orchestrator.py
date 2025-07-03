import json
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.prompts import PromptTemplate
from memory import history

from utils import init_llm, correct_json
from agents import (
    generic_bot,
    web_search_agent as web,
    budget_recommender_agent as budget,
)

BUDGET_KEYWORDS = {"spend", "budget", "roas", "channel", "metrics"}

llm = init_llm()

# ── State schema ──────────────────────────────────────────────────────────────
class RouterState(TypedDict):
    question: str
    branch: str
    answer: str
    history: list

# ── Router node ───────────────────────────────────────────────────────────────
def router(state: RouterState) -> Command:
    prompt = """
    Route the user query to one of these branches:

      • budget_insights       – questions about looking at the company's current budget, marketing spend, ROAS, channels, reallocating budget, daily metrics, proposing a new budget
      • web_search            – factual or open-ended questions answerable via the web
      • generic               – greetings or off-topic

    Respond ONLY with JSON like: 
    {{"next": "<branch>"}}

    User Query: {question}
    """
    prompt_tmpl = PromptTemplate.from_template(prompt)

    q_lower = state["question"].lower()
    # 1) keyword shortcut
    if any(k in q_lower for k in BUDGET_KEYWORDS):
        branch = "budget_insights"
    else:
        # Pass the last turns so the router can leverage context
        text = (prompt_tmpl | llm).invoke(
            {"question": state["question"], "history": list(history)}
        ).content      # plain string

        text = correct_json(text)
        print("[ROUTER raw]", text)

        try:
            branch = json.loads(text)["next"]
        except Exception:
            print("Failed to parse router response. Falling back to 'generic'.")
            branch = "generic"

    mapping = {
        "budget_insights":      "budget_node",
        "web_search":           "search_node",
        "generic":              "generic_node",
    }
    return Command(goto=mapping.get(branch, "generic_node"), update={"branch": branch})

# ── Leaf nodes ────────────────────────────────────
def budget_node(state: RouterState):
    answer = budget.run(state["question"])
    return Command(
        update={
            "answer": answer, 
            "branch": state.get("branch"),
            "history": list(history)
        },
        goto=END,
    )

def search_node(state: RouterState):
    answer = web.run(state["question"])
    return Command(
        update={
            "answer": answer, 
            "branch": state.get("branch"),
            "history": list(history)
        },
        goto=END,
    )

def generic_node(state: RouterState):
    answer = generic_bot.run(state["question"])
    return Command(
        update={
            "answer":  answer,
            "branch":  state.get("branch"),   # keep for debug
            "history": list(history)          # optional
        },
        goto=END
    )

# ── Build the graph ───────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(RouterState)
    g.add_node("router", router)
    g.add_node("budget_node",      budget_node)
    g.add_node("search_node",      search_node)
    g.add_node("generic_node",     generic_node)

    g.add_edge(START, "router")
    for leaf in ("budget_node", "generic_node", "search_node"):
        g.add_edge(leaf, END)
    return g.compile()