from ragpipeline.retrieve import dedupe_by_parent


def test_dedupe_keeps_best_per_parent():
    hits = [
        {"id": "c1", "parent_id": "p1", "score": 1.0},
        {"id": "c2", "parent_id": "p1", "score": 2.0},
        {"id": "c3", "parent_id": "p2", "score": 1.5},
    ]
    result = dedupe_by_parent(hits)
    assert len(result) == 2
    best_p1 = next(hit for hit in result if hit["parent_id"] == "p1")
    assert best_p1["id"] == "c2"


def test_dedupe_sorted_by_score_desc():
    hits = [
        {"id": "a", "parent_id": "p1", "score": 1.0},
        {"id": "b", "parent_id": "p2", "score": 3.0},
    ]
    result = dedupe_by_parent(hits)
    assert result[0]["parent_id"] == "p2"


def test_dedupe_handles_missing_parent_id():
    hits = [{"id": "only", "score": 1.0}]
    assert dedupe_by_parent(hits)[0]["id"] == "only"
