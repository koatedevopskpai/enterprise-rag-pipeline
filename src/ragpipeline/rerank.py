import json
import re

from ragpipeline.config import MODEL_DEPLOYMENT_NAME
from ragpipeline.embeddings import get_openai_client


def parse_index_order(text, n):
    match = re.search(r"\[[^\]]*\]", text or "")
    if not match:
        return list(range(n))
    try:
        values = json.loads(match.group(0))
    except Exception:
        return list(range(n))

    order = []
    for value in values:
        if isinstance(value, int) and 0 <= value < n and value not in order:
            order.append(value)
    for index in range(n):
        if index not in order:
            order.append(index)
    return order


def llm_rerank(query, hits, top_k, text_field="parent_content"):
    if not hits:
        return []

    lines = []
    for index, hit in enumerate(hits):
        text = (hit.get(text_field) or hit.get("content") or "").replace("\n", " ")
        lines.append(f"{index}: {text[:600]}")

    prompt = (
        "Rank the candidate passages by how well they help answer the question. "
        f"Return ONLY a JSON array of up to {top_k} integer indices, most relevant first.\n\n"
        f"Question: {query}\n\nCandidates:\n" + "\n".join(lines)
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL_DEPLOYMENT_NAME,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    order = parse_index_order(response.choices[0].message.content, len(hits))
    return [hits[index] for index in order[:top_k]]
