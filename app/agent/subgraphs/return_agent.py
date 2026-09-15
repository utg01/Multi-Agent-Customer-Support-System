from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import return_agent_node_prompt
from langchain_core.messages import SystemMessage
from langgraph.prebuilt.tool_node import tools_condition, ToolNode
import os
load_dotenv()
from app.agent.subgraphs.supervisor_node import AgentState

from app.agent.tools.langchain_tool_register import (
    get_order_details_tool,
    get_user_orders_tool,
    get_ordered_products_tool,
    escalate_to_supervisor,
    create_return_tool,
    get_return_details_tool,
    list_user_returns_tool,
    create_coupon_tool
)

tools = [
    get_order_details_tool,
    get_user_orders_tool,
    get_ordered_products_tool,     
    create_return_tool,
    get_return_details_tool,
    list_user_returns_tool,
    create_coupon_tool,
    escalate_to_supervisor
]


llm=ChatGroq(
    model='openai/gpt-oss-120b',
    api_key=os.getenv("GROQ_API_KEY")
)


return_llm = llm.bind_tools(tools)

tool_node=ToolNode(tools)


def return_agent_node(state: AgentState):
    llm_input=[SystemMessage(content=return_agent_node_prompt),*state['messages']]
    response=return_llm.invoke(llm_input)
    return {"messages": [response]}


from langchain_core.messages import ToolMessage

def check_escalation(state: AgentState):
    """Checks if the most recent tool call was escalate_to_supervisor"""
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages and tool_messages[-1].name == "escalate_to_supervisor":
        return {"active_agent": ""}
    return {"active_agent": "return_agent"}


return_graph = StateGraph(AgentState)

return_graph.add_node("return_agent", return_agent_node)
return_graph.add_node("tools", tool_node)
return_graph.add_node("check_escalation", check_escalation)

return_graph.add_edge(START, "return_agent")
return_graph.add_conditional_edges("return_agent",tools_condition)
return_graph.add_edge("tools","return_agent")
return_graph.add_edge("return_agent","check_escalation")
return_graph.add_edge("check_escalation",END)

return_agent=return_graph.compile()


#TESTING CODE 
def check_chat():
    human=""
    while human.strip().lower()!="exit":
        human=input("Human: ")
        response=return_agent.invoke({'messages':[HumanMessage(content=human)],'active_agent':'return_agent'},config={'configurable':{'thread_id':'7','user_id':'7'}})
        print("Chatbot:", response['messages'][-1].content)


def get_state_fux():
    print(return_agent.get_state(config={'configurable':{'thread_id':'7','user_id':'7'}}))


if __name__=="__main__":
    check_chat()
    get_state_fux()