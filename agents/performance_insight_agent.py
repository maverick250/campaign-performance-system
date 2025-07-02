# agents/performance_insight_agent.py
"""
Stub agent that will one day query your data warehouse for campaign KPIs.
For now it just echoes its branch name.
"""

def run(question: str) -> str:
    return (
        "📊 [Performance-Insight Agent]\n"
        "I’m not wired to the database yet, but I received your request:\n"
        f"    “{question}”\n"
        "Once connected, I’ll pull metrics like CTR, CPA, and ROAS."
    )
