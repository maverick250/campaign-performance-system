from langchain_core.prompts import PromptTemplate
from utils import init_llm
from datetime import date, datetime
import dateparser

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import OpenAIEmbeddings            # for future RAG
import os

from dateparser.search import search_dates

from dotenv import load_dotenv
load_dotenv()

_db = SQLDatabase.from_uri(
    f"snowflake://{os.getenv('SNOWFLAKE_USER')}:{os.getenv('SNOWFLAKE_PASSWORD')}"
    f"@{os.getenv('SNOWFLAKE_ACCOUNT')}/{os.getenv('SNOWFLAKE_DATABASE')}/"
    f"{os.getenv('SNOWFLAKE_SCHEMA')}?warehouse={os.getenv('SNOWFLAKE_WAREHOUSE')}"
)

def extract_day(text: str) -> str:
    """Return first date found in text, else today in ISO‐8601."""
    hits = search_dates(text, settings={"PREFER_DATES_FROM": "past"})
    if hits:
        return hits[0][1].date().isoformat()   # hits is [(matched_text, datetime)]
    return date.today().isoformat()

def fetch_budget(date_str: str) -> str:
    """Return today’s (or requested) budget rows as CSV‐styled text."""
    q = f"""
    SELECT channel, spend, clicks, sales
    FROM METRICS
    WHERE DATE = '{date_str}'
    ORDER BY channel;
    """
    #print(date_str)
    return _db.run(q)

llm = init_llm()

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

def run(question: str) -> str:
    # 1. Figure out which date to fetch.  For MVP assume “today”.
    day  = extract_day(question)           # e.g. "2025-06-28"
    rows = fetch_budget(day)

    if not rows:
        return f"⚠️ No metrics found for {day}."

    # 2. Let the LLM crunch a recommendation
    return (ANALYSE_PROMPT | llm).invoke({"rows": rows}).content
