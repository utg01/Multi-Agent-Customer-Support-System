import os

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_KEY_API")
SUPERVISOR_MODEL = "gpt-4o-mini"
SPECIALIST_MODEL = "gpt-4o-mini"

supervisor_llm = ChatOpenAI(
    model=SUPERVISOR_MODEL,
    api_key=OPENAI_API_KEY,
    #temperature=0,
)

llm = ChatOpenAI(
    model=SPECIALIST_MODEL,
    api_key=OPENAI_API_KEY,
    #temperature=0.1,
    #reasoning_effort="low",
    use_responses_api=True,
)

medium_reasoning_llm = ChatOpenAI(
    model=SPECIALIST_MODEL,
    api_key=OPENAI_API_KEY,
    #temperature=0.1,
    #reasoning_effort="medium",
    use_responses_api=True,
)
"""

from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_SUPERVISOR_MODEL = "openai/gpt-oss-20b"
GROQ_MODEL = "openai/gpt-oss-120b"

supervisor_llm = ChatGroq(
    model=GROQ_SUPERVISOR_MODEL,
    api_key=GROQ_API_KEY,
)

llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
)

medium_reasoning_llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
)
"""