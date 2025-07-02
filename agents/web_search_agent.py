from dotenv import load_dotenv
load_dotenv()  # make sure SERPER_API_KEY is in your env

# 1. Import the new API wrapper and tool
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from langchain_community.tools.google_serper.tool import GoogleSerperRun

from langchain_core.prompts import PromptTemplate
from utils import init_llm

# 2. Instantiate Serper with the working pattern
api_wrapper = GoogleSerperAPIWrapper()           # reads SERPER_API_KEY
search = GoogleSerperRun(api_wrapper=api_wrapper)

# 3. LLM and prompt setup
llm = init_llm()

SUMMARY_PROMPT = PromptTemplate.from_template(
    "Summarise these search snippets in 3–4 bullet points, marketing-focused:\n\n{snips}"
)

def run(question: str) -> str:
    # 4. Do your lookup, truncate, then summarise
    snippets = search.run(question)[:1500]   # keep under token limit
    return (SUMMARY_PROMPT | llm).invoke({"snips": snippets}).content
