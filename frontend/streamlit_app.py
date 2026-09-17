import streamlit as st
import httpx
import uuid

from dotenv import load_dotenv
import os

load_dotenv()
API_BASE = os.getenv("API_BASE") 

# **************** Google login gate ****************
if not st.user.is_logged_in:
    st.title("BrightCart Support")
    st.write("Please log in to continue.")
    st.button("Log in with Google", on_click=st.login)
    st.stop()

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
    resp = httpx.get(f"{API_BASE}/chat/threads", headers=AUTH_HEADERS)
    resp.raise_for_status()
    return resp.json()["thread_ids"]


def load_conversation(thread_id):
    resp = httpx.get(
        f"{API_BASE}/chat/threads/{thread_id}/messages", headers=AUTH_HEADERS
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