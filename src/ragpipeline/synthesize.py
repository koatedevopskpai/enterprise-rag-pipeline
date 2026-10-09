from ragpipeline.config import MODEL_DEPLOYMENT_NAME
from ragpipeline.embeddings import get_openai_client

SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided context. "
    "Cite sources inline using the format [source <source_id>] and include the "
    "section when available, e.g. [source refund_policy > Exceptions]. "
    "If the answer is not in the context, reply exactly: I do not know."
)


def build_context(retrieved_docs):
    parts = []
    for doc in retrieved_docs:
        text = doc.get("parent_content") or doc.get("content", "")
        label = doc.get("source_id", "")
        if doc.get("section"):
            label = f"{label} > {doc['section']}"
        parts.append(f"[source {label}] {text}")
    return "\n\n".join(parts)


def synthesize_answer(query, retrieved_docs):
    context = build_context(retrieved_docs)
    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL_DEPLOYMENT_NAME,
        temperature=0,
        messages=[
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context}"},
            {"role": "user", "content": query},
        ],
    )
    return response.choices[0].message.content
