import streamlit as st

from consumer_agent import clear_inter_agent_log, run_consumer


st.set_page_config(page_title="Provider Consumer Agents", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "agent_log" not in st.session_state:
    st.session_state.agent_log = []


left_column, right_column = st.columns(2)

with left_column:
    st.header("🛒 Consumer Agent")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input("Ask the consumer agent...")
    if user_input:
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )
        response, log_snapshot = run_consumer(user_input)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": response}
        )
        st.session_state.agent_log = log_snapshot
        st.rerun()

with right_column:
    st.header("📡 Agent-to-Agent Log")
    st.subheader("Provider ↔ Consumer Communication")

    if not st.session_state.agent_log:
        st.info("No agent communication yet.")
    else:
        for entry in st.session_state.agent_log:
            sender = entry.get("from")
            avatar = "🛒" if sender == "consumer" else "🏪"
            with st.chat_message(sender or "assistant", avatar=avatar):
                st.write(entry.get("message", ""))

    if st.button("🗑 Clear Log"):
        clear_inter_agent_log()
        st.session_state.agent_log = []
        st.rerun()
