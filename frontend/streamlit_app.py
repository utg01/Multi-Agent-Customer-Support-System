import streamlit as st
import httpx
import uuid

from dotenv import load_dotenv
import os

load_dotenv()
API_BASE = os.getenv("API_BASE") 

import time

DEMO_QUERY_LIMIT = 5
DEMO_USER_ID = 200


def reset_demo():
    st.session_state["demo_mode"] = True
    st.session_state["demo_session_id"] = str(uuid.uuid4())
    st.session_state["demo_history"] = []
    st.session_state["demo_query_count"] = 0
    st.session_state.pop("demo_customer", None)


def render_processing_loader():
    processing_placeholder = st.empty()
    processing_placeholder.markdown(
        """
        <div class="processing-message" role="status" aria-live="polite">
            <span>Processing your request</span><span class="processing-dots">...</span>
        </div>
        <style>
            .processing-message { display: flex; align-items: center; gap: 2px; }
            .processing-dots {
                width: 18px; overflow: hidden;
                animation: processing-dots 1.2s steps(4, end) infinite;
            }
            @keyframes processing-dots {
                0% { width: 0; } 33% { width: 6px; }
                66% { width: 12px; } 100% { width: 18px; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    return processing_placeholder


def request_chat(path, payload, headers=None):
    response_text = ""
    with httpx.stream(
        "POST",
        f"{API_BASE}{path}",
        json=payload,
        headers=headers,
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_text():
            response_text += chunk
    return response_text

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
            except httpx.RequestError :
                pass
            time.sleep(15)

    st.error("Backend is taking longer than usual to wake up. Please refresh in a moment.")
    st.stop()

# **************** Recruiter demo ****************
if "demo_mode" not in st.session_state:
    st.session_state["demo_mode"] = False

if not st.session_state["demo_mode"] and not st.user.is_logged_in:
    st.title("BrightCart Support")
    st.write("Explore a five-question demo without signing in.")
    if st.button("Try recruiter demo", type="primary"):
        reset_demo()
        st.rerun()
    st.write("Or log in to access saved conversations.")
    st.button("Log in with Google", on_click=st.login)
    st.stop()

if st.session_state["demo_mode"]:
    wait_for_backend()
    if "demo_history" not in st.session_state:
        reset_demo()
    response = httpx.get(f"{API_BASE}/chat/demo-info", timeout=30.0)
    response.raise_for_status()
    st.session_state["demo_customer"] = response.json()

    st.title("BrightCart Support Demo")
    st.caption(
        f"Ask up to {DEMO_QUERY_LIMIT} questions. No account or saved chat history is required."
    )
    if st.button("Exit demo"):
        st.session_state["demo_mode"] = False
        st.rerun()

    with st.sidebar:
        st.header("Demo customer")
        st.caption(f"Customer ID: {DEMO_USER_ID}")
        st.write("Ordered products:")
        for product in st.session_state["demo_customer"]["ordered_products"]:
            st.write(
                f"- {product['name']} x{product['quantity']} "
                f"(₹{product['price']:.2f})"
            )

    for message in st.session_state["demo_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    demo_input = st.chat_input("Try the BrightCart chatbot")
    if demo_input:
        if st.session_state["demo_query_count"] >= DEMO_QUERY_LIMIT:
            st.warning("The five-question demo limit has been reached.")
            st.stop()

        st.session_state["demo_query_count"] += 1
        st.session_state["demo_history"].append(
            {"role": "user", "content": demo_input}
        )
        with st.chat_message("user"):
            st.markdown(demo_input)

        with st.chat_message("assistant"):
            processing_placeholder = render_processing_loader()
            try:
                answer = request_chat(
                    "/chat/demo-stream",
                    {
                        "session_id": st.session_state["demo_session_id"],
                        "message": demo_input,
                        "query_number": st.session_state["demo_query_count"],
                    },
                )
                st.markdown(answer)
                st.session_state["demo_history"].append(
                    {"role": "assistant", "content": answer}
                )
            finally:
                processing_placeholder.empty()
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
        processing_placeholder = render_processing_loader()
        try:
            full_response = request_chat(
                "/chat/stream",
                {
                    "thread_id": st.session_state["thread_id"],
                    "message": user_input,
                },
                headers=AUTH_HEADERS,
            )
            st.markdown(full_response)
        finally:
            processing_placeholder.empty()

    st.session_state["message_history"].append(
        {"role": "assistant", "content": full_response}
    )