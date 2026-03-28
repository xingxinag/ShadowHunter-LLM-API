from app import (
    build_default_form_state,
    build_interface_field_specs,
    build_result_cards,
    classify_error_message,
    build_gateway_configs,
    classify_interaction_status,
    filter_raw_interactions,
    build_audit_role_explanation,
)
from ui.theme import build_theme_css


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
    assert state["translations"]["zh"]["role_help_title"]
    assert state["translations"]["en"]["role_help_title"]


def test_interface_field_specs_cover_requested_providers() -> None:
    specs = build_interface_field_specs()["zh"]
    assert "anthropic_messages" in specs
    assert "amazon_bedrock" in specs
    assert "gemini_native" in specs
    assert "gemini_openai_compatible" in specs
    assert any("Tooltip" not in field["help"] and "采样温度" in field["help"] for field in specs["openai_responses"])
    assert any("Anthropic" in field["help"] or "Claude" in field["help"] for field in specs["anthropic_messages"])
    assert any("AWS" in field["help"] for field in specs["amazon_bedrock"])
    assert any("Gemini" in field["help"] or "Google" in field["help"] for field in specs["gemini_native"])
    assert any("OpenAI 兼容" in field["help"] or "OpenAI compatibility" in field["help"] for field in specs["gemini_openai_compatible"])


def test_default_form_state_contains_provider_runtime_defaults() -> None:
    state = build_default_form_state()
    options = state["provider_runtime_defaults"]
    assert options["anthropic_messages"]["anthropic_version"] == "2023-06-01"
    assert options["amazon_bedrock"]["aws_region"] == "us-east-1"
    assert options["amazon_bedrock"]["aws_secret_access_key"] == ""
    assert options["gemini_native"]["google_api_version"] == "v1beta"
    assert options["gemini_openai_compatible"]["max_tokens"] == 512


def test_theme_css_contains_bento_and_floating_history_styles() -> None:
    css = build_theme_css()
    assert ".bento-grid" in css
    assert ".history-drawer" in css
    assert "@keyframes radarReveal" in css
    assert "@keyframes heatmapGlow" in css


def test_result_cards_include_main_scores_and_raw_data() -> None:
    cards = build_result_cards(
        {
            "similarity": 88.8,
            "confidence": 72.5,
            "ratio": 1.22,
            "feasibility": 81.4,
            "verdict": "FRAUD DETECTED",
            "active_interface": "openai_compatible",
            "active_path": "/v1/chat/completions",
            "output_state": "empty_output",
            "error_summary": "Target endpoint blocked the request.",
            "raw_interactions": [{"probe": "reasoning_trap"}],
        }
    )
    assert cards["metrics"][0]["label_zh"] == "模型相似度"
    assert cards["metrics"][0]["label_en"] == "Similarity"
    assert cards["metrics"][3]["label_zh"] == "可行度评分"
    assert cards["verdict"] == "FRAUD DETECTED"
    assert cards["path_card"]["path"] == "/v1/chat/completions"
    assert cards["path_card"]["interface"] == "openai_compatible"
    assert cards["path_card"]["output_state"] == "empty_output"
    assert cards["error_summary"] == "Target endpoint blocked the request."
    assert cards["raw_interactions"][0]["probe"] == "reasoning_trap"


def test_interaction_status_and_filtering_support_success_empty_and_error() -> None:
    success = {"baseline_response": "ok", "target_response": "done"}
    empty = {"baseline_response": "[ERROR] /v1/chat/completions SSE response did not contain content", "target_response": "done"}
    failed = {"baseline_response": "[ERROR] upstream failed", "target_response": "done"}

    assert classify_interaction_status(success) == "success"
    assert classify_interaction_status(empty) == "empty_output"
    assert classify_interaction_status(failed) == "error"
    assert len(filter_raw_interactions([success, empty, failed], "all")) == 3
    assert len(filter_raw_interactions([success, empty, failed], "success")) == 1
    assert len(filter_raw_interactions([success, empty, failed], "empty_output")) == 1
    assert len(filter_raw_interactions([success, empty, failed], "error")) == 1


def test_error_classifier_explains_upstream_failures_bilingually() -> None:
    assert "上游接口返回错误" in classify_error_message("[ERROR] upstream failed", "zh")
    assert "upstream endpoint returned an error" in classify_error_message("[ERROR] upstream failed", "en")
    assert "空输出" in classify_error_message("[ERROR] /v1/chat/completions SSE response did not contain content", "zh")


def test_error_classifier_handles_upstream_500_and_bedrock_signing() -> None:
    assert "上游服务暂时异常" in classify_error_message("500 Internal Server Error", "zh")
    assert "Bedrock" in classify_error_message("request signing failed", "en")
    assert "请为基线接口填写 Base URL" in classify_error_message("responses interface requires base_url", "zh")


def test_gateway_configs_provide_base_urls_for_baseline_and_target() -> None:
    configs = build_gateway_configs(
        interface_type="openai_responses",
        baseline_model="gpt-5.2",
        target_model="gpt-5.4-mini",
        baseline_key="b-key",
        target_key="t-key",
        baseline_url="https://api.42w.shop/v1",
        target_url="https://api.42w.shop/v1",
        runtime_options={},
    )

    assert configs["baseline"]["base_url"] == "https://api.42w.shop/v1"
    assert configs["target"]["base_url"] == "https://api.42w.shop/v1"


def test_theme_css_increases_metric_and_legend_contrast() -> None:
    css = build_theme_css()
    assert ".metric-value" in css
    assert ".legend-callout" in css
    assert "color: #FFFFFF" in css


def test_audit_role_explanation_explains_why_two_models_and_keys_exist() -> None:
    zh = build_audit_role_explanation("zh")
    en = build_audit_role_explanation("en")

    assert "基线模型" in zh
    assert "目标模型" in zh
    assert "2 个模型" in zh or "两套" in zh
    assert "Baseline model" in en
    assert "Target model" in en
