from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import coupon_agent_node_prompt
from langchain_core.messages import SystemMessage
from langgraph.prebuilt.tool_node import tools_condition, ToolNode
import os
load_dotenv()
from app.agent.subgraphs.supervisor_node import AgentState

from app.agent.tools.langchain_tool_register import (
    get_active_coupons_tool,
    validate_coupon_tool,
    escalate_to_supervisor
)


coupon_tools = [
    get_active_coupons_tool,
    validate_coupon_tool,
    escalate_to_supervisor
]


llm=ChatGroq(
    model='openai/gpt-oss-120b',
    api_key=os.getenv("GROQ_API_KEY")
)


coupon_llm = llm.bind_tools(coupon_tools)

tool_node=ToolNode(coupon_tools)


def coupon_agent_node(state: AgentState):
    llm_input=[SystemMessage(content=coupon_agent_node_prompt),*state['messages']]
    response=coupon_llm.invoke(llm_input)
    return {"messages": [response]}


from langchain_core.messages import ToolMessage


def check_escalation(state: AgentState):
    """Checks if the most recent tool call was escalate_to_supervisor"""
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages and tool_messages[-1].name == "escalate_to_supervisor":
        return {"active_agent": ""}
    return {"active_agent": "coupon_agent"}


coupon_graph = StateGraph(AgentState)

coupon_graph.add_node("coupon_agent", coupon_agent_node)
coupon_graph.add_node("tools", tool_node)
coupon_graph.add_node("check_escalation", check_escalation)

coupon_graph.add_edge(START, "coupon_agent")
coupon_graph.add_conditional_edges("coupon_agent",tools_condition)
coupon_graph.add_edge("tools","coupon_agent")
coupon_graph.add_edge("coupon_agent","check_escalation")
coupon_graph.add_edge("check_escalation",END)

coupon_agent=coupon_graph.compile()


#TESTING CODE 
def check_chat():
    human=""
    while human.strip().lower()!="exit":
        human=input("Human: ")
        response=coupon_agent.invoke({'messages':[HumanMessage(content=human)],'active_agent':'coupon_agent'},config={'configurable':{'thread_id':'11','user_id':'1'}})
        print("Chatbot:", response['messages'][-1].content)


def get_state_fux():
    print(coupon_agent.get_state(config={'configurable':{'thread_id':'11','user_id':'1'}}))


if __name__=="__main__":
    check_chat()
    get_state_fux()