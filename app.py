"""
Streamlit UI that sends chat messages to the FastAPI backend on localhost:8000.
"""

import streamlit as st
import requests

# Browser tab title and a clean, centered layout for the chat page.
st.set_page_config(page_title="🤖 AI Chatbot", layout="centered")

# Main heading and a short line explaining what powers the bot.
st.title("🤖 AI Chatbot")
st.subheader("Powered by Mistral + Ollama")

# On the very first visit, create an empty list to hold chat turns (role + content).
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar holds identity controls so one browser tab can pick user and session.
with st.sidebar:
    # Integer-like picker for which backend user_id to send on every /chat call.
    user_id = st.number_input("user_id", min_value=0, value=1, step=1)
    # Free-text session name; must match a session you created via the API (POST /session).
    session_id = st.text_input("session_id", value="session-abc")
    # Clicking this wipes the on-screen history only (does not delete server-side DB rows).
    if st.button("Start / Switch Session"):
        st.session_state.messages = []
    # Green banner so you always see which user/session the next message will use.
    st.success(f"Active: user {int(user_id)} | session {session_id}")

# Replay everything stored in session_state so refreshes keep the conversation visible.
for msg in st.session_state.messages:
    # Streamlit shows user bubbles on one side and assistant on the other based on role.
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Bottom text box; returns the latest user text when they press Enter, otherwise None.
prompt = st.chat_input("Type your message here...")

# Only run the API block when the user actually submitted a non-empty message.
if prompt:
    # Remember the user line first so it still appears after a rerun even if the API fails.
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Show the human turn right away so the UI feels responsive.
    with st.chat_message("user"):
        st.markdown(prompt)
    # Block the page with a spinner label while the FastAPI server talks to Ollama.
    with st.spinner("Thinking..."):
        try:
            # POST JSON matches the FastAPI ChatRequest model (user_id, session_id, message).
            response = requests.post(
                "http://localhost:8000/chat",
                json={
                    "user_id": int(user_id),
                    "session_id": session_id,
                    "message": prompt,
                },
                timeout=130,
            )
            # Turn HTTP errors (4xx/5xx) into exceptions so we hit the same error banner.
            response.raise_for_status()
            # Backend returns ChatResponse; we only need the assistant text field here.
            reply = response.json()["reply"]
        except (requests.RequestException, KeyError, ValueError):
            # Covers offline server, timeouts, bad JSON, or missing "reply" key.
            st.error("Could not connect to backend. Is uvicorn running?")
            reply = None
    # If we got a model answer, render it like other assistant messages.
    if reply is not None:
        with st.chat_message("assistant"):
            st.markdown(reply)
        # Store the assistant turn so the history loop can redraw it on the next run.
        st.session_state.messages.append({"role": "assistant", "content": reply})
