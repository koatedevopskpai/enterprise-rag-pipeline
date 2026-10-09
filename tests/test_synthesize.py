from ragpipeline.synthesize import build_context


def test_build_context_uses_parent_content_and_section():
    docs = [
        {
            "id": "refund_policy-p02-c00",
            "source_id": "refund_policy",
            "section": "Exceptions",
            "content": "child text",
            "parent_content": "full parent text",
        }
    ]
    context = build_context(docs)
    assert "refund_policy > Exceptions" in context
    assert "full parent text" in context
    assert context.count("[source") == 1


def test_build_context_falls_back_to_content():
    docs = [{"id": "d-0000", "source_id": "d", "content": "short"}]
    context = build_context(docs)
    assert "[source d]" in context
    assert "short" in context


def test_build_context_handles_empty():
    assert build_context([]) == ""
