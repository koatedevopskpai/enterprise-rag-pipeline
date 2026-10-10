from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from ragpipeline.auth import search_credential
from ragpipeline.config import (
    RETRIEVE_TOP_K,
    SEARCH_ENDPOINT,
    SEARCH_INDEX_NAME,
    require,
)
from ragpipeline.embeddings import embed

SELECT_FIELDS = ["id", "source_id", "parent_id", "section", "content", "parent_content"]


def get_search_client(index_name=SEARCH_INDEX_NAME):
    return SearchClient(
        endpoint=require("SEARCH_ENDPOINT", SEARCH_ENDPOINT),
        index_name=index_name,
        credential=search_credential(),
    )


def dedupe_by_parent(hits):
    best = {}
    for hit in hits:
        key = hit.get("parent_id") or hit.get("id")
        current = best.get(key)
        if current is None or (hit.get("score") or 0) > (current.get("score") or 0):
            best[key] = hit
    return sorted(best.values(), key=lambda h: h.get("score") or 0, reverse=True)


def search_children(query, mode="hybrid", top_n=20, index_name=SEARCH_INDEX_NAME):
    client = get_search_client(index_name)

    vector_query = None
    search_text = None

    if mode in ("hybrid", "vector"):
        query_vector = embed([query])[0]
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_n,
            fields="content_vector",
        )
    if mode in ("hybrid", "bm25"):
        search_text = query

    kwargs = {"select": SELECT_FIELDS, "top": top_n}
    if vector_query is not None:
        kwargs["vector_queries"] = [vector_query]
    if search_text is not None:
        kwargs["search_text"] = search_text

    results = client.search(**kwargs)

    return [
        {
            "id": result["id"],
            "source_id": result.get("source_id"),
            "parent_id": result.get("parent_id"),
            "section": result.get("section"),
            "content": result.get("content", ""),
            "parent_content": result.get("parent_content", ""),
            "score": result.get("@search.score"),
        }
        for result in results
    ]


def hybrid_retrieve(query, top_k=RETRIEVE_TOP_K, index_name=SEARCH_INDEX_NAME):
    hits = search_children(query, mode="hybrid", top_n=top_k * 4, index_name=index_name)
    return dedupe_by_parent(hits)[:top_k]
