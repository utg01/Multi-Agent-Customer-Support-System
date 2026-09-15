from langchain_core.tools import tool
from embeddings import pc, vector_store

def retrieve_policy_info(query: str, k: int = 3) -> dict:
    """Retrieve relevant company policy information (returns, refunds, shipping, cancellation, coupons, app FAQ) for a customer question. Use this whenever a user asks about company policies, procedures, or general platform questions."""

    mmr_results = vector_store.max_marginal_relevance_search(
        query,
        k=8,
        fetch_k=20
    )

    candidates = [doc.page_content for doc in mmr_results]

    rerank_response = pc.inference.rerank(
        model="bge-reranker-v2-m3",
        query=query,
        documents=candidates,
        top_n=k
    )

    reranked_chunks = [result.document["text"] for result in rerank_response.data]
    return {"relevant_policy_info": reranked_chunks}