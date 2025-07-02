import json
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.prompts import PromptTemplate
from memory import history
from agents import web_search_agent as web

from utils import init_llm, correct_json
from agents import (
    generic_bot,
    performance_insight_agent as perf,
    budget_recommender_agent as budget,
    creative_analysis_agent as creative,
)

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

      • performance_insight   – explore campaign KPIs
      • budget_recommender    – suggest new budget split
      • creative_analysis     – analyse ad creatives
      • web_search            – factual or open-ended questions answerable via the web
      • generic               – greetings or off-topic

    Respond ONLY with JSON like: 
    {{"next": "<branch>"}}

    User Query: {question}
    """
    prompt_tmpl = PromptTemplate.from_template(prompt)

    # Pass the last turns so the router can leverage context
    text = (prompt_tmpl | llm).invoke(
        {"question": state["question"], "history": list(history)}
    ).content      # plain string

    text = correct_json(text)
    print("[ROUTER raw]", text)

    try:
        #branch = json.loads(correct_json(text))["next"]
        branch = json.loads(text)["next"]
    except Exception:
        print("Failed to parse router response. Falling back to 'generic'.")
        branch = "generic"

    mapping = {
        "performance_insight":  "performance_node",
        "budget_recommender":   "budget_node",
        "creative_analysis":    "creative_node",
        "web_search":           "search_node",
        "generic":              "generic_node",
    }
    return Command(goto=mapping.get(branch, "generic_node"), update={"branch": branch})

# ── Leaf nodes (just call the stub agents) ────────────────────────────────────
def performance_node(state: RouterState):
    return Command(
        update={"answer": perf.run(state["question"]),
                "branch": state.get("branch")},
        goto=END
    )

def budget_node(state: RouterState):
    return Command(
        update={"answer": perf.run(state["question"]),
                "branch": state.get("branch")},
        goto=END
    )

def creative_node(state: RouterState):
    return Command(
        update={"answer": perf.run(state["question"]),
                "branch": state.get("branch")},
        goto=END
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
    g.add_node("performance_node", performance_node)
    g.add_node("budget_node",      budget_node)
    g.add_node("creative_node",    creative_node)
    g.add_node("search_node",      search_node)
    g.add_node("generic_node",     generic_node)

    g.add_edge(START, "router")
    for leaf in ("performance_node", "budget_node", "creative_node", "generic_node", "search_node"):
        g.add_edge(leaf, END)
    return g.compile()