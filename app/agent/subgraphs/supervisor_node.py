from pydantic import BaseModel, Field
from typing import TypedDict, List, Annotated,Literal, Optional
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import supervisor_node_prompt
from langchain_core.messages import SystemMessage
import os
load_dotenv()

from langchain_core.runnables import RunnableLambda

groq_api=os.getenv("GROQ_API_KEY")
class AgentState(TypedDict):
    messages:Annotated[list[BaseMessage], add_messages]
    active_agent:Optional[str]

class RouteDecision(BaseModel):
    reply: str = Field(
        description="If the intent is unclear, ask the user a short clarification question. "
                    "If the intent is clear, return an empty string."
    )

    next_agent: Literal[
        "order_agent",
        "return_agent",
        "product_agent",
        "coupon_agent",
        "qa_agent",
        "not_sure"
    ]

llm=ChatGroq(
    model='openai/gpt-oss-20b',
    api_key=groq_api,
    temperature=0
)

def supervisor_node(state:AgentState):
    if not state.get('active_agent') or state.get('active_agent', '').strip() == 'not_sure':

        supervisor_llm=llm.with_structured_output(RouteDecision)

        response=supervisor_llm.invoke([SystemMessage(content=supervisor_node_prompt),*state['messages']])

        if response.next_agent.strip()=='not_sure':
            return {'active_agent':'not_sure',
                    'messages': [AIMessage(content=response.reply)]}
        else:
            return{'active_agent':response.next_agent}
    else:
        return {'active_agent':state['active_agent']}

if __name__=='__main__':
    human=input("Enter test query")
    supervisor_runnable=RunnableLambda(supervisor_node)
    result=supervisor_runnable.invoke({
        'messages':[HumanMessage(content=human)],
        'active_agent':None
    },config={'configurable':{"thread_id":'1'}})
    print(result)