from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from utils import init_llm
from memory import history, HumanMessage, AIMessage

llm = init_llm()

CAPABILITIES = """
I can also hand off your request to specialist agents if you ask for:

• “campaign KPIs”, “CTR”, “ROAS”… → **performance insight**
• “reallocate budget”, “spend split”… → **budget recommender**
• “score this ad creative”, “image engagement”… → **creative analysis**

Just describe what you need in plain English.
"""

SYSTEM_PROMPT = (
    "You are a friendly marketing-assistant chatbot.\n"
    + CAPABILITIES
    + "\n\nChat history (oldest → newest):\n{history}\n\nUser: {q}\nAssistant:"
)

prompt_tmpl  = PromptTemplate.from_template(SYSTEM_PROMPT)

def run(question: str) -> str:
    # ① build the history text shown to the model
    hist_txt = "\n".join(m.content for m in history)

    ai_msg = (prompt_tmpl  | llm).invoke({"q": question, "history": hist_txt})
    
    # ➜ push the new turn into history
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=ai_msg.content))
    return ai_msg
