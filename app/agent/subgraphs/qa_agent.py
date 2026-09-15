from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from app.agent.system_prompts import qa_agent_node_prompt
from langchain_core.messages import SystemMessage
from langgraph.prebuilt.tool_node import tools_condition, ToolNode
import os
load_dotenv()
from app.agent.subgraphs.supervisor_node import AgentState


from app.agent.tools.langchain_tool_register import (
    retrieve_policy_info_tool,
    escalate_to_supervisor
)


qa_tools = [
    retrieve_policy_info_tool,
    escalate_to_supervisor
]


llm=ChatGroq(
    model='openai/gpt-oss-120b',
    api_key=os.getenv("GROQ_API_KEY")
)


qa_llm = llm.bind_tools(qa_tools)

tool_node=ToolNode(qa_tools)


def qa_agent_node(state: AgentState):
    llm_input=[SystemMessage(content=qa_agent_node_prompt),*state['messages']]
    response=qa_llm.invoke(llm_input)
    return {"messages": [response]}


def check_escalation(state: AgentState):
    """Checks if the most recent tool call was escalate_to_supervisor"""
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages and tool_messages[-1].name == "escalate_to_supervisor":
        return {"active_agent": ""}
    return {"active_agent": "qa_agent"}


qa_graph = StateGraph(AgentState)

qa_graph.add_node("qa_agent", qa_agent_node)
qa_graph.add_node("tools", tool_node)
qa_graph.add_node("check_escalation", check_escalation)

qa_graph.add_edge(START, "qa_agent")
qa_graph.add_conditional_edges("qa_agent",tools_condition)
qa_graph.add_edge("tools","qa_agent")
qa_graph.add_edge("qa_agent","check_escalation")
qa_graph.add_edge("check_escalation",END)

qa_agent=qa_graph.compile()


#TESTING CODE 
def check_chat():
    human=""
    while human.strip().lower()!="exit":
        human=input("Human: ")
        response=qa_agent.invoke({'messages':[HumanMessage(content=human)],'active_agent':'qa_agent'},config={'configurable':{'thread_id':'14','user_id':'1'}})
        print("Chatbot:", response['messages'][-1].content)


def get_state_fux():
    print(qa_agent.get_state(config={'configurable':{'thread_id':'14','user_id':'1'}}))


if __name__=="__main__":
    check_chat()
    get_state_fux()