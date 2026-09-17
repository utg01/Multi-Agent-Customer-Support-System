import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from app.agent.subgraphs.supervisor_node import AgentState, supervisor_node
from app.agent.subgraphs.order_agent import order_agent as order_subgraph
from app.agent.subgraphs.return_agent import return_agent as return_subgraph
from app.agent.subgraphs.product_agent import product_agent as product_subgraph
from app.agent.subgraphs.coupon_agent import coupon_agent as coupon_subgraph
from app.agent.subgraphs.qa_agent import qa_agent as qa_subgraph

load_dotenv()

checkpointer_DB_URL = os.getenv("CHECKPOINTER_DB_URI")
pool = ConnectionPool(conninfo=checkpointer_DB_URL, max_size=20, kwargs={'autocommit': True, "prepare_threshold": 0})
checkpointer = PostgresSaver(pool)
checkpointer.setup()

main_graph = StateGraph(AgentState)

main_graph.add_node("supervisor", supervisor_node)
main_graph.add_node("order_agent", order_subgraph)
main_graph.add_node("return_agent", return_subgraph)
main_graph.add_node("product_agent", product_subgraph)
main_graph.add_node("coupon_agent", coupon_subgraph)
main_graph.add_node("qa_agent", qa_subgraph)

main_graph.add_edge(START, "supervisor")

main_graph.add_conditional_edges(
    "supervisor",
    lambda state: state["active_agent"],
    {
        "order_agent": "order_agent",
        "return_agent": "return_agent",
        "product_agent": "product_agent",
        "coupon_agent": "coupon_agent",
        "qa_agent": "qa_agent",
        "not_sure": END,
    }
)


def route_after_specialist(state: AgentState):
    if state.get("active_agent") in (None, "", "not_sure"):
        return "supervisor"
    return END


for agent_name in ["order_agent", "return_agent", "product_agent", "coupon_agent", "qa_agent"]:
    main_graph.add_conditional_edges(
        agent_name,
        route_after_specialist,
        {"supervisor": "supervisor", END: END},
    )

agent = main_graph.compile(checkpointer=checkpointer)

# TESTING CODE
from langchain_core.messages import HumanMessage

config = {
    'configurable': {
        'thread_id': '4',
        'user_id': '1'
    },
    'recursion_limit': 15,
}


def check_chat():
    human = ""
    while human.strip().lower() != "exit":
        human = input("Human: ")
        response = agent.invoke({'messages': [HumanMessage(content=human)], 'active_agent': ''}, config=config)
        print("Chatbot:", response['messages'][-1].content)


def get_state_fux():
    print(agent.get_state(config=config))


if __name__ == "__main__":
    check_chat()
    get_state_fux()