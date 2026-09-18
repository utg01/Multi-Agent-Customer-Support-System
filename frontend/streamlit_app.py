import streamlit as st
import httpx
import uuid

from dotenv import load_dotenv
import os

load_dotenv()
API_BASE = os.getenv("API_BASE") 

import time

def wait_for_backend():
    """Ping /health with a generous timeout until the backend wakes up.
    Render's free tier sleeps after inactivity — first request after
    sleep can take 30-50s, so we handle that explicitly here instead
    of letting the real chat/auth calls time out and error."""
    if st.session_state.get("backend_awake"):
        return

    with st.spinner("Waking up the backend — this can take up to a minute on first load..."):
        for attempt in range(6):  # ~6 tries, generous total wait
            try:
                resp = httpx.get(f"{API_BASE}/health", timeout=20.0)
                if resp.status_code == 200:
                    st.session_state["backend_awake"] = True
                    return
            except httpx.RequestError:
                pass
            time.sleep(10)

    st.error("Backend is taking longer than usual to wake up. Please refresh in a moment.")
    st.stop()

# **************** Google login gate ****************
if not st.user.is_logged_in:
    st.title("BrightCart Support")
    st.write("Please log in to continue.")
    st.button("Log in with Google", on_click=st.login)
    st.stop()

wait_for_backend()

# syncing with postgres after login
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET")

if "session_token" not in st.session_state:
    resp = httpx.post(
        f"{API_BASE}/auth/google-sync",
        json={
            "email": st.user.email,
            "google_sub": st.user.sub,
            "name": st.user.get("name"),
        },
        headers={"x-internal-secret": INTERNAL_SERVICE_SECRET},
        timeout=30.0,
    )
    resp.raise_for_status()
    st.session_state["session_token"] = resp.json()["session_token"]

AUTH_HEADERS = {"Authorization": f"Bearer {st.session_state['session_token']}"}

# **************** utility functions ****************
def generate_thread_id():
    return str(uuid.uuid4())


def reset_chat():
    st.session_state["thread_id"] = generate_thread_id()
    st.session_state["message_history"] = []


def fetch_threads():
    resp = httpx.get(f"{API_BASE}/chat/threads",timeout=30.0, headers=AUTH_HEADERS)
    resp.raise_for_status()
    return resp.json()["thread_ids"]


def load_conversation(thread_id):
    resp = httpx.get(
        f"{API_BASE}/chat/threads/{thread_id}/messages",timeout=30.0, headers=AUTH_HEADERS
    )
    resp.raise_for_status()
    return resp.json()["messages"]


# **************** session state setup ****************
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = fetch_threads()

# **************** sidebar UI ****************
st.sidebar.title("BrightCart Support")
st.sidebar.caption(f"Logged in as {st.user.email}")
st.sidebar.button("Log out", on_click=st.logout)

if st.sidebar.button("New Chat"):
    reset_chat()

st.sidebar.header("My conversations")
for thread_id in st.session_state["chat_threads"][::-1]:
    if st.sidebar.button(str(thread_id)):
        st.session_state["thread_id"] = thread_id
        st.session_state["message_history"] = load_conversation(thread_id)

# **************** render chat history ****************
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.text(message["content"])

user_input = st.chat_input("Type here:")

if user_input:
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    if st.session_state["thread_id"] not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(st.session_state["thread_id"])

    # **************** FastAPI streaming ****************
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        with httpx.stream(
            "POST",
            f"{API_BASE}/chat/stream",
            json={
                "thread_id": st.session_state["thread_id"],
                "message": user_input,
            },
            headers=AUTH_HEADERS,
            timeout=120.0,
        ) as response:
            for chunk in response.iter_text():
                full_response += chunk
                placeholder.text(full_response)

    st.session_state["message_history"].append(
        {"role": "assistant", "content": full_response}
    )