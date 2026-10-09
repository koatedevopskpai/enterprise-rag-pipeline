import ragpipeline.pipeline as pipeline


def test_answer_combines_retrieval_and_synthesis(monkeypatch):
    fake_docs = [{"id": "d-0000", "source_id": "d", "content": "c", "score": 1.0}]
    monkeypatch.setitem(pipeline.STRATEGIES, "hybrid", lambda question, top_k=5: fake_docs)
    monkeypatch.setattr(pipeline, "synthesize_answer", lambda question, docs: "grounded answer")

    result = pipeline.answer("what?", mode="hybrid")
    assert result["answer"] == "grounded answer"
    assert result["sources"] == fake_docs
    assert result["mode"] == "hybrid"


def test_answer_rejects_unknown_mode():
    import pytest

    with pytest.raises(ValueError):
        pipeline.answer("what?", mode="does-not-exist")
