from __future__ import annotations

import asyncio
import os

try:
    import streamlit as st
    from streamlit_echarts import st_echarts
except ModuleNotFoundError:  # pragma: no cover
    st = None
    st_echarts = None

from adapters.llm_gateway import UnifiedGateway
from core.engine import AuditEngine
from ui.charts import build_heatmap_option, build_radar_option
from ui.theme import load_css


def build_interface_field_specs() -> dict[str, dict[str, list[dict[str, str | bool]]]]:
    shared_zh = [
        {"key": "temperature", "label": "Temperature", "help": "采样温度：越高越发散，审计最佳实践建议保持低温。", "enabled": True},
        {"key": "top_p", "label": "Top-P", "help": "核采样阈值：仅在需要时开启。对部分 OpenAI 兼容网关，建议关闭以避免兼容问题。", "enabled": True},
        {"key": "max_tokens", "label": "Max Tokens", "help": "最大输出长度：建议只给足够的预算，避免干扰方差统计。", "enabled": True},
    ]
    shared_en = [
        {"key": "temperature", "label": "Temperature", "help": "Sampling temperature. Best practice for audits is to keep it low.", "enabled": True},
        {"key": "top_p", "label": "Top-P", "help": "Nucleus sampling threshold. Disable it when compatibility is unstable.", "enabled": True},
        {"key": "max_tokens", "label": "Max Tokens", "help": "Maximum output budget. Keep it tight for cleaner variance measurements.", "enabled": True},
    ]
    return {
        "zh": {
            "openai_responses": shared_zh,
            "openai_compatible": shared_zh,
            "openai_compatible_chat": shared_zh,
            "anthropic": shared_zh + [
                {"key": "anthropic_version", "label": "Anthropic Version", "help": "Claude/Anthropic 请求版本头。用于 POST /v1/messages 兼容。", "enabled": True},
            ],
            "amazon_bedrock": shared_zh + [
                {"key": "aws_region", "label": "AWS Region", "help": "AWS 区域：Bedrock 鉴权与模型路由依赖该参数。", "enabled": True},
                {"key": "aws_access_key_id", "label": "AWS Access Key ID", "help": "AWS 访问密钥 ID。建议使用最小权限的 Bedrock 专用凭证。", "enabled": True},
            ],
            "google_gemini": shared_zh + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Gemini / Google AI key。Gemini 使用 contents 结构而非 messages。", "enabled": True},
            ],
        },
        "en": {
            "openai_responses": shared_en,
            "openai_compatible": shared_en,
            "openai_compatible_chat": shared_en,
            "anthropic": shared_en + [
                {"key": "anthropic_version", "label": "Anthropic Version", "help": "Claude/Anthropic version header for the Messages API.", "enabled": True},
            ],
            "amazon_bedrock": shared_en + [
                {"key": "aws_region", "label": "AWS Region", "help": "AWS region used for Bedrock signing and model routing.", "enabled": True},
                {"key": "aws_access_key_id", "label": "AWS Access Key ID", "help": "Dedicated Bedrock credentials with least privilege are recommended.", "enabled": True},
            ],
            "google_gemini": shared_en + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Gemini uses a contents payload instead of messages.", "enabled": True},
            ],
        },
    }


def classify_error_message(message: str, language: str) -> str:
    if not message:
        return ""
    catalog = {
        "invalid api key": {
            "zh": "API Key 无效：请检查密钥是否复制完整、是否已过期、是否绑定到当前网关。",
            "en": "Invalid API key: check whether the key is complete, active, and allowed on this gateway.",
        },
        "blocked": {
            "zh": "请求被上游拦截：通常是接口类型不匹配、模型无权限，或网关策略阻断。",
            "en": "The upstream blocked the request, usually due to interface mismatch, model access, or gateway policy.",
        },
        "rate": {
            "zh": "触发频率限制：请稍后重试，或降低并发和采样轮数。",
            "en": "Rate limit hit: retry later or lower concurrency and sampling rounds.",
        },
        "permission": {
            "zh": "模型无权限：当前账号或 key 没有该模型的访问资格。",
            "en": "Model access denied: the account or key is not allowed to use this model.",
        },
    }
    lowered = message.lower()
    for token, mapping in catalog.items():
        if token in lowered:
            return mapping[language]
    return message


def build_translations() -> dict[str, dict[str, str | list[str]]]:
    return {
        "zh": {
            "title": "猎影-X：大模型 API 审计系统",
            "sidebar": "审计配置",
            "baseline_key": "基线 API Key",
            "target_key": "目标 API Key",
            "baseline_model": "基线模型",
            "target_model": "目标模型",
            "target_url": "目标 Base URL",
            "rounds": "采样轮数",
            "language": "界面语言",
            "interface_type": "接口格式",
            "start": "启动深度审计",
            "probing": "[INFO] 正在执行多维探针与响应采集...",
            "done": "[SUCCESS] 审计完成。",
            "verdict": "结论",
            "radar": "8 维探针雷达图",
            "heatmap": "跨轮次距离热力图",
            "raw": "原始探针对话",
        },
        "en": {
            "title": "ShadowHunter-X: LLM API Audit System",
            "sidebar": "Audit Configuration",
            "baseline_key": "Baseline API Key",
            "target_key": "Target API Key",
            "baseline_model": "Baseline Model",
            "target_model": "Target Model",
            "target_url": "Target Base URL",
            "rounds": "Sampling Rounds",
            "language": "Language",
            "interface_type": "Interface Type",
            "start": "Launch Deep Audit",
            "probing": "[INFO] Running multi-probe collection...",
            "done": "[SUCCESS] Audit completed.",
            "verdict": "Verdict",
            "radar": "8-Dimension Probe Radar",
            "heatmap": "Cross-Round Distance Heatmap",
            "raw": "Raw Probe Dialogs",
        },
    }


def build_default_form_state() -> dict[str, object]:
    return {
        "baseline_provider": "openai-compatible",
        "target_provider": "openai-compatible",
        "baseline_model": "gpt-5.2",
        "target_model": "gpt-5.4-mini",
        "target_url": os.getenv("SHADOWHUNTER_TARGET_BASE_URL", "https://api.42w.shop/v1"),
        "rounds": 6,
        "min_rounds": 3,
        "max_rounds": 12,
        "language": "zh",
        "interface_type": "openai_responses",
        "supported_interfaces": [
            "openai_responses",
            "openai_compatible",
            "openai_compatible_chat",
            "anthropic",
            "amazon_bedrock",
            "google_gemini",
        ],
        "translations": build_translations(),
        "interface_field_specs": build_interface_field_specs(),
    }


def build_result_cards(results: dict) -> dict:
    return {
        "metrics": [
            {"label": "Similarity", "value": results["similarity"]},
            {"label": "Confidence", "value": results["confidence"]},
            {"label": "Ratio", "value": results["ratio"]},
        ],
        "verdict": results.get("verdict", "UNKNOWN"),
        "error_summary": results.get("error_summary", ""),
        "error_explained": results.get("error_explained", ""),
        "raw_interactions": results["raw_interactions"],
    }


def render_app() -> None:
    if st is None:
        raise RuntimeError("streamlit is not installed")
    defaults = build_default_form_state()
    translations = defaults["translations"]
    st.set_page_config(page_title="ShadowHunter-X", layout="wide", page_icon="spy")
    load_css(st)

    with st.sidebar:
        language = st.selectbox(str(translations[defaults["language"]]["language"]), options=["zh", "en"], index=0)
        copy = translations[language]
        st.header(str(copy["sidebar"]))
        interface_index = list(defaults["supported_interfaces"]).index(str(defaults["interface_type"]))
        interface_type = st.selectbox(str(copy["interface_type"]), options=list(defaults["supported_interfaces"]), index=interface_index)
        baseline_key = st.text_input(str(copy["baseline_key"]), type="password")
        target_key = st.text_input(str(copy["target_key"]), type="password")
        baseline_model = st.text_input(str(copy["baseline_model"]), value=str(defaults["baseline_model"]))
        target_model = st.text_input(str(copy["target_model"]), value=str(defaults["target_model"]))
        target_url = st.text_input(str(copy["target_url"]), value=str(defaults["target_url"]))
        rounds = st.slider(str(copy["rounds"]), min_value=int(defaults["min_rounds"]), max_value=int(defaults["max_rounds"]), value=int(defaults["rounds"]))
        st.caption("Best practice / 最佳实践：默认保持低 Temperature，OpenAI Compatible 建议关闭 Top-P。")
        with st.expander("Provider Parameters / 参数说明", expanded=False):
            for field in defaults["interface_field_specs"][language][interface_type]:
                st.checkbox(str(field["label"]), value=bool(field["enabled"]), key=f"param-toggle-{interface_type}-{field['key']}", help=str(field["help"]))
        start_btn = st.button(str(copy["start"]), use_container_width=True)

    st.title(str(copy["title"]))

    if start_btn and baseline_key and target_key:
        status_text = st.empty()
        progress_bar = st.progress(0.0)
        status_text.info(str(copy["probing"]))
        baseline_gateway = UnifiedGateway("openai-compatible", baseline_model, baseline_key, interface_type=interface_type)
        target_gateway = UnifiedGateway("openai-compatible", target_model, target_key, base_url=target_url, interface_type=interface_type)
        engine = AuditEngine(baseline_gateway=baseline_gateway, target_gateway=target_gateway)
        results = asyncio.run(engine.run_audit(rounds=rounds, progress_callback=progress_bar.progress))
        results["error_explained"] = classify_error_message(results.get("error_summary", ""), language)
        status_text.success(str(copy["done"]))
        render_results(results, copy)


def render_results(results: dict, copy: dict[str, str]) -> None:
    if st is None:
        return
    cards = build_result_cards(results)
    col1, col2, col3 = st.columns(3)
    for column, item in zip((col1, col2, col3), cards["metrics"], strict=False):
        column.metric(item["label"], item["value"])
    st.caption(f"{copy['verdict']}: {cards['verdict']}")
    if cards["error_summary"]:
        st.warning(cards["error_summary"])
    if cards["error_explained"]:
        st.info(cards["error_explained"])

    st.divider()
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader(str(copy["radar"]))
        if st_echarts is not None:
            st_echarts(build_radar_option(results["radar_data"]), height="420px")
    with chart_col2:
        st.subheader(str(copy["heatmap"]))
        if st_echarts is not None:
            st_echarts(build_heatmap_option(results["heatmap_data"]), height="420px")
    with st.expander(str(copy["raw"])):
        st.json(cards["raw_interactions"])


if __name__ == "__main__":
    render_app()
