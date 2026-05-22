from runtime.values import stable_sort


def test_stable_sort_handles_mixed_field_types_without_type_error():
    rows = [
        {"name": "int", "score": 1},
        {"name": "str", "score": "2"},
        {"name": "none", "score": None},
        {"name": "missing"},
    ]

    out = stable_sort(rows, "score")

    assert [item["name"] for item in out] == ["int", "str", "none", "missing"]


def test_stable_sort_handles_mixed_field_types_descending():
    rows = [
        {"name": "int", "score": 1},
        {"name": "str", "score": "2"},
        {"name": "none", "score": None},
        {"name": "missing"},
    ]

    out = stable_sort(rows, "score", desc=True)

    assert [item["name"] for item in out] == ["none", "missing", "str", "int"]


def test_stable_sort_keeps_stable_order_for_equal_keys():
    rows = [
        {"name": "first", "score": 1},
        {"name": "second", "score": 1},
        {"name": "third", "score": 1},
    ]

    out = stable_sort(rows, "score")

    assert [item["name"] for item in out] == ["first", "second", "third"]


def test_stable_sort_handles_nested_values_without_type_error():
    rows = [
        {"name": "dict", "score": {"value": 1}},
        {"name": "list", "score": [1, 2]},
        {"name": "str", "score": "2"},
    ]

    out = stable_sort(rows, "score")

    assert [item["name"] for item in out] == ["dict", "list", "str"]
