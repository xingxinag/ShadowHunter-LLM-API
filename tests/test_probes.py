from ui.charts import build_heatmap_option, build_radar_option
from core.probes import PROBE_LIBRARY, build_probe_conversation


def test_probe_library_contains_eight_dimensions() -> None:
    assert len(PROBE_LIBRARY) == 8
    assert {probe.dimension for probe in PROBE_LIBRARY} == {
        "metadata_hallucination",
        "alignment_boundary",
        "malformed_syntax",
        "formatting_quirks",
        "reasoning_trap",
        "multilingual_nuance",
        "coding_style",
        "self_identification",
    }


def test_each_probe_builds_three_turn_trap() -> None:
    conversation = build_probe_conversation(PROBE_LIBRARY[0])

    assert len(conversation) == 3
    assert all(turn["role"] == "user" for turn in conversation)


def test_chart_builders_return_expected_shapes() -> None:
    radar = build_radar_option(
        [
            {"dimension": "reasoning_trap", "baseline": 0.8, "target": 0.7},
            {"dimension": "coding_style", "baseline": 0.9, "target": 0.6},
        ]
    )
    heatmap = build_heatmap_option([[0.1, 0.2], [0.3, 0.4]])

    assert "逻辑陷阱" in radar["radar"]["indicator"][0]["name"]
    assert len(radar["series"][0]["data"]) == 2
    assert heatmap["series"][0]["type"] == "heatmap"
    assert heatmap["visualMap"]["text"] == ["逻辑漂移", "高相似"]
    assert "低距离/高相似度" in heatmap["legend_explanation"]
