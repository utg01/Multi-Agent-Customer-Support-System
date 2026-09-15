from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import order_agent_node_prompt
from langchain_core.messages import SystemMessage
from langgraph.prebuilt.tool_node import tools_condition, ToolNode
import os
load_dotenv()
from app.agent.subgraphs.supervisor_node import AgentState

from app.agent.tools.langchain_tool_register import (
    get_order_details_tool,
    get_user_orders_tool,
    place_order_tool,
    cancel_order_item_tool,
    modify_order_tool,
    search_products_tool,
    get_ordered_products_tool,
    escalate_to_supervisor
)

order_tools = [
    get_order_details_tool,
    get_user_orders_tool,
    place_order_tool,
    cancel_order_item_tool,
    modify_order_tool,
    search_products_tool,
    get_ordered_products_tool,
    escalate_to_supervisor
]

llm=ChatGroq(
    model='openai/gpt-oss-120b',
    api_key=os.getenv("GROQ_API_KEY")
)

order_llm = llm.bind_tools(order_tools)

tool_node=ToolNode(order_tools)

def order_agent_node(state: AgentState):
    llm_input=[SystemMessage(content=order_agent_node_prompt),*state['messages']]
    response=order_llm.invoke(llm_input)
    return {"messages": [response]}

from langchain_core.messages import ToolMessage

def check_escalation(state: AgentState):
    """Checks if the most recent tool call was escalate_to_supervisor"""
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages and tool_messages[-1].name == "escalate_to_supervisor":
        return {"active_agent": ""}
    return {"active_agent": "order_agent"}

order_graph = StateGraph(AgentState)

order_graph.add_node("order_agent", order_agent_node)
order_graph.add_node("tools", tool_node)
order_graph.add_node("check_escalation", check_escalation)

order_graph.add_edge(START, "order_agent")
order_graph.add_conditional_edges("order_agent",tools_condition)
order_graph.add_edge("tools","order_agent")
order_graph.add_edge("order_agent","check_escalation")
order_graph.add_edge("check_escalation",END)

order_agent=order_graph.compile()





#TESTING CODE 
def check_chat():
    human=""
    while human.strip().lower()!="exit":
        human=input("Human: ")
        response=order_agent.invoke({'messages':[HumanMessage(content=human)],'active_agent':'order_agent'},config={'configurable':{'thread_id':'4','user_id':'1'}})
        print("Chatbot:", response['messages'][-1].content)

def get_state_fux():
    print(order_agent.get_state(config={'configurable':{'thread_id':'4','user_id':'1'}}))

if __name__=="__main__":
    check_chat()
    get_state_fux()  
    