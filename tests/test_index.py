from ragpipeline.index import build_index


def test_index_has_key_field():
    index = build_index("test-index")
    key_fields = [f for f in index.fields if getattr(f, "key", False)]
    assert len(key_fields) == 1
    assert key_fields[0].name == "id"


def test_index_has_parent_child_fields():
    index = build_index("test-index")
    names = [f.name for f in index.fields]
    for expected in ("parent_id", "section", "parent_content", "content", "content_vector"):
        assert expected in names


def test_index_has_vector_field_and_profile():
    index = build_index("test-index")
    assert index.vector_search is not None
    assert index.vector_search.profiles[0].name == "hnsw-profile"
