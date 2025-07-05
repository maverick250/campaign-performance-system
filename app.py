# app.py
import streamlit as st, requests, uuid

BACKEND = "http://localhost:8000/chat"
if "sid" not in st.session_state:
    st.session_state.sid = str(uuid.uuid4())

st.title("📊 Campaign-Budget Assistant")

user_in = st.chat_input("Ask me anything about spend, ROAS, …")
if user_in:
    st.chat_message("user").write(user_in)

    print("POSTing to", BACKEND)
    resp = requests.post(
        BACKEND,
        json={"session_id": st.session_state.sid, "message": user_in},
        timeout=60,
    )
    print(resp.status_code, resp.text)   # keep for debugging

    try:
        data = resp.json()               # <-- keep this
    except ValueError:
        st.error("Backend did not return JSON")
        st.stop()

    if "reply" not in data:
        st.error(f"Backend error: {data}")
    else:
        st.chat_message("assistant").write(data["reply"])
