import ragpipeline.strategies as strategies


def _parents():
    return [
        {"id": "c1", "parent_id": "p1", "parent_content": "alpha", "score": 0.9},
        {"id": "c2", "parent_id": "p2", "parent_content": "beta", "score": 0.8},
    ]


def test_registry_exposes_modes():
    assert set(strategies.STRATEGIES) == {"vector", "hybrid", "hybrid_rerank"}


def test_hybrid_rerank_uses_llm_order(monkeypatch):
    calls = {}

    def fake_search(query, mode="hybrid", top_n=20, index_name=None):
        calls["mode"] = mode
        return _parents()

    def fake_rerank(query, hits, top_k, text_field="parent_content"):
        calls["reranked"] = True
        return list(reversed(hits))

    monkeypatch.setattr(strategies, "search_children", fake_search)
    monkeypatch.setattr(strategies, "llm_rerank", fake_rerank)

    result = strategies.strategy_hybrid_rerank("q", top_k=2)
    assert calls["mode"] == "hybrid"
    assert calls["reranked"] is True
    assert result[0]["parent_id"] == "p2"


def test_hybrid_dedupes_by_parent(monkeypatch):
    def fake_search(query, mode="hybrid", top_n=20, index_name=None):
        return [
            {"id": "c1", "parent_id": "p1", "parent_content": "a", "score": 0.5},
            {"id": "c2", "parent_id": "p1", "parent_content": "a", "score": 0.9},
        ]

    monkeypatch.setattr(strategies, "search_children", fake_search)
    result = strategies.strategy_hybrid("q", top_k=5)
    assert len(result) == 1
    assert result[0]["id"] == "c2"
