from core.distance import combined_distance, cosine_distance, markdown_tag_set, structural_distance


def test_cosine_distance_is_zero_for_identical_vectors() -> None:
    assert cosine_distance([1.0, 2.0], [1.0, 2.0]) == 0.0


def test_markdown_tags_detect_heading_list_and_code() -> None:
    tags = markdown_tag_set("# Title\n- item\n```python\nprint('x')\n```")
    assert {"heading", "list", "code"}.issubset(tags)


def test_combined_distance_uses_weighted_formula() -> None:
    distance = combined_distance(0.5, 0.25)
    assert distance == 0.45


def test_structural_distance_drops_for_similar_markdown() -> None:
    assert structural_distance("# A\n- item", "# B\n- item") == 0.0
