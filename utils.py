# utils.py
import os, re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def init_llm():
    """Return a ChatOpenAI client using your personal key."""
    return ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        temperature=0.2,
        streaming=True,   # nice UX; safe in LangGraph
    )

def correct_json(json_str: str) -> str:
    """
    Strip ```json fences, balance {} and [] so json.loads won't crash.
    (Same logic as the lengthy version—condensed.)
    """
    # 1) fence-strip
    cleaned = json_str.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
    # 2) drop a leading 'json' if present
    cleaned = re.sub(r'^json\s*', '', cleaned.strip(), flags=re.I)

    # 3) balance braces/brackets
    for open_c, close_c in (('{', '}'), ('[', ']')):
        diff = cleaned.count(open_c) - cleaned.count(close_c)
        if diff > 0:
            cleaned += close_c * diff
        # if too many closing, trim from end
        while cleaned.count(close_c) > cleaned.count(open_c):
            cleaned = cleaned[:-1]
    return cleaned
