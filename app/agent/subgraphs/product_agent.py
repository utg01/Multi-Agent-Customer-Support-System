from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import product_agent_node_prompt
from langchain_core.messages import SystemMessage
from langgraph.prebuilt.tool_node import tools_condition, ToolNode
import os
load_dotenv()
from app.agent.subgraphs.supervisor_node import AgentState


from app.agent.tools.langchain_tool_register import (
    get_ordered_products_tool,
    search_products_tool,
    get_product_info_tool,
    escalate_to_supervisor
)


product_tools = [
    get_ordered_products_tool,
    search_products_tool,
    get_product_info_tool,
    escalate_to_supervisor
]


llm=ChatGroq(
    model='openai/gpt-oss-120b',
    api_key=os.getenv("GROQ_API_KEY")
)


product_llm = llm.bind_tools(product_tools)

tool_node=ToolNode(product_tools)


def product_agent_node(state: AgentState):
    llm_input=[SystemMessage(content=product_agent_node_prompt),*state['messages']]
    response=product_llm.invoke(llm_input)
    return {"messages": [response]}


from langchain_core.messages import ToolMessage

def check_escalation(state: AgentState):
    """Checks if the most recent tool call was escalate_to_supervisor"""
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages and tool_messages[-1].name == "escalate_to_supervisor":
        return {"active_agent": ""}
    return {"active_agent": "product_agent"}


product_graph = StateGraph(AgentState)

product_graph.add_node("product_agent", product_agent_node)
product_graph.add_node("tools", tool_node)
product_graph.add_node("check_escalation", check_escalation)

product_graph.add_edge(START, "product_agent")
product_graph.add_conditional_edges("product_agent",tools_condition)
product_graph.add_edge("tools","product_agent")
product_graph.add_edge("product_agent","check_escalation")
product_graph.add_edge("check_escalation",END)

product_agent=product_graph.compile()


#TESTING CODE 
def check_chat():
    human=""
    while human.strip().lower()!="exit":
        human=input("Human: ")
        response=product_agent.invoke({'messages':[HumanMessage(content=human)],'active_agent':'product_agent'},config={'configurable':{'thread_id':'10','user_id':'9'}})
        print("Chatbot:", response['messages'][-1].content)


def get_state_fux():
    print(product_agent.get_state(config={'configurable':{'thread_id':'10','user_id':'1'}}))


if __name__=="__main__":
    check_chat()
    get_state_fux()