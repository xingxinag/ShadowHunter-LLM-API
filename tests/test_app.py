from app import build_default_form_state, build_interface_field_specs, build_result_cards


def test_default_form_state_matches_document_ranges() -> None:
    state = build_default_form_state()
    assert state["rounds"] == 6
    assert state["min_rounds"] == 3
    assert state["max_rounds"] == 12
    assert state["language"] == "zh"
    assert state["interface_type"] == "openai_responses"
    assert len(state["supported_interfaces"]) == 6


def test_default_form_state_contains_bilingual_labels() -> None:
    state = build_default_form_state()
    assert state["translations"]["zh"]["title"]
    assert state["translations"]["en"]["title"]


def test_interface_field_specs_cover_requested_providers() -> None:
    specs = build_interface_field_specs()["zh"]
    assert "anthropic" in specs
    assert "amazon_bedrock" in specs
    assert "google_gemini" in specs
    assert any("Tooltip" not in field["help"] and "采样温度" in field["help"] for field in specs["openai_responses"])
    assert any("Anthropic" in field["help"] or "Claude" in field["help"] for field in specs["anthropic"])
    assert any("AWS" in field["help"] for field in specs["amazon_bedrock"])
    assert any("Gemini" in field["help"] or "Google" in field["help"] for field in specs["google_gemini"])


def test_result_cards_include_main_scores_and_raw_data() -> None:
    cards = build_result_cards(
        {
            "similarity": 88.8,
            "confidence": 72.5,
            "ratio": 1.22,
            "verdict": "FRAUD DETECTED",
            "error_summary": "Target endpoint blocked the request.",
            "raw_interactions": [{"probe": "reasoning_trap"}],
        }
    )
    assert cards["metrics"][0]["label"] == "Similarity"
    assert cards["verdict"] == "FRAUD DETECTED"
    assert cards["error_summary"] == "Target endpoint blocked the request."
    assert cards["raw_interactions"][0]["probe"] == "reasoning_trap"
