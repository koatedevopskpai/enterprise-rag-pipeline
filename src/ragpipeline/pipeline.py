from ragpipeline.config import RETRIEVE_TOP_K
from ragpipeline.strategies import STRATEGIES
from ragpipeline.synthesize import synthesize_answer
from ragpipeline.telemetry import span

DEFAULT_MODE = "hybrid"


def answer(question, mode=DEFAULT_MODE, top_k=RETRIEVE_TOP_K):
    strategy = STRATEGIES.get(mode)
    if strategy is None:
        raise ValueError(f"Unknown mode: {mode}. Options: {sorted(STRATEGIES)}")
    with span("retrieve", mode=mode, top_k=top_k):
        docs = strategy(question, top_k=top_k)
    with span("synthesize", mode=mode, sources=len(docs)):
        text = synthesize_answer(question, docs)
    return {"answer": text, "sources": docs, "mode": mode}
