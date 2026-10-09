from ragpipeline.config import RETRIEVE_TOP_K
from ragpipeline.rerank import llm_rerank
from ragpipeline.retrieve import dedupe_by_parent, search_children


def strategy_vector(query, top_k=RETRIEVE_TOP_K):
    hits = search_children(query, mode="vector", top_n=top_k * 4)
    return dedupe_by_parent(hits)[:top_k]


def strategy_hybrid(query, top_k=RETRIEVE_TOP_K):
    hits = search_children(query, mode="hybrid", top_n=top_k * 4)
    return dedupe_by_parent(hits)[:top_k]


def strategy_hybrid_rerank(query, top_k=RETRIEVE_TOP_K):
    hits = search_children(query, mode="hybrid", top_n=max(20, top_k * 4))
    parents = dedupe_by_parent(hits)[:20]
    return llm_rerank(query, parents, top_k=top_k)


STRATEGIES = {
    "vector": strategy_vector,
    "hybrid": strategy_hybrid,
    "hybrid_rerank": strategy_hybrid_rerank,
}
