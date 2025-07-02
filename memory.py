# memory.py  (new helper file)
from collections import deque
from langchain_core.messages import HumanMessage, AIMessage

MAX_TURNS = 20        # keep the last 20 exchanges

history: deque = deque(maxlen=MAX_TURNS)   # shared inside the process
