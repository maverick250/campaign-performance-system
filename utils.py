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
    cleaned = re.sub(r'^json\s*', '', json_str.strip(), flags=re.I)
    for o, c in (('{', '}'), ('[', ']')):
        diff = cleaned.count(o) - cleaned.count(c)
        if diff > 0:
            cleaned += c * diff
        while cleaned.count(c) > cleaned.count(o):
            cleaned = cleaned[:-1]
    return cleaned
