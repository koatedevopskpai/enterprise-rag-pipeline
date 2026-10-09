from ragpipeline.rerank import parse_index_order


def test_parse_valid_order_pads_missing():
    assert parse_index_order("[3, 0]", 4) == [3, 0, 1, 2]


def test_parse_filters_out_of_range_and_dupes():
    assert parse_index_order("[2, 2, 9, -1, 0]", 3) == [2, 0, 1]


def test_parse_invalid_json_falls_back():
    assert parse_index_order("no array here", 3) == [0, 1, 2]


def test_parse_empty_text_falls_back():
    assert parse_index_order("", 2) == [0, 1]


def test_parse_caps_to_all_indices():
    order = parse_index_order("[1, 0, 2]", 3)
    assert sorted(order) == [0, 1, 2]
