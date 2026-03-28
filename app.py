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
            "anthropic_messages": shared_zh + [
                {"key": "anthropic_version", "label": "Anthropic Version", "help": "Claude/Anthropic 请求版本头。用于 POST /v1/messages 兼容。", "enabled": True},
            ],
            "amazon_bedrock": shared_zh + [
                {"key": "aws_region", "label": "AWS Region", "help": "AWS 区域：Bedrock 鉴权与模型路由依赖该参数。", "enabled": True},
                {"key": "aws_access_key_id", "label": "AWS Access Key ID", "help": "AWS 访问密钥 ID。建议使用最小权限的 Bedrock 专用凭证。", "enabled": True},
                {"key": "aws_secret_access_key", "label": "AWS Secret Access Key", "help": "AWS Secret Key：用于 SigV4 签名，不会展示到图表结果中。", "enabled": True},
                {"key": "aws_session_token", "label": "AWS Session Token", "help": "临时凭证时需要填写 Session Token；长期密钥可以留空。", "enabled": False},
            ],
            "gemini_native": shared_zh + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Gemini / Google AI key。Gemini 使用 contents 结构而非 messages。", "enabled": True},
            ],
            "gemini_openai_compatible": shared_zh + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Gemini 的 OpenAI 兼容模式。仅在代理层明确支持 OpenAI compatibility 时使用。", "enabled": True},
            ],
        },
        "en": {
            "openai_responses": shared_en,
            "openai_compatible": shared_en,
            "anthropic_messages": shared_en + [
                {"key": "anthropic_version", "label": "Anthropic Version", "help": "Claude/Anthropic version header for the Messages API.", "enabled": True},
            ],
            "amazon_bedrock": shared_en + [
                {"key": "aws_region", "label": "AWS Region", "help": "AWS region used for Bedrock signing and model routing.", "enabled": True},
                {"key": "aws_access_key_id", "label": "AWS Access Key ID", "help": "Dedicated Bedrock credentials with least privilege are recommended.", "enabled": True},
                {"key": "aws_secret_access_key", "label": "AWS Secret Access Key", "help": "Secret key used for SigV4 signing. It should never appear in result panels.", "enabled": True},
                {"key": "aws_session_token", "label": "AWS Session Token", "help": "Required for temporary credentials; optional for long-lived keys.", "enabled": False},
            ],
            "gemini_native": shared_en + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Gemini uses a contents payload instead of messages.", "enabled": True},
            ],
            "gemini_openai_compatible": shared_en + [
                {"key": "google_api_key", "label": "Google API Key", "help": "Use this only when Gemini is exposed through an OpenAI-compatible gateway.", "enabled": True},
            ],
        },
    }


def build_provider_runtime_defaults() -> dict[str, dict[str, str | int | float]]:
    return {
        "openai_responses": {"temperature": 0.3, "max_tokens": 512},
        "openai_compatible": {"temperature": 0.3, "max_tokens": 512},
        "anthropic_messages": {"anthropic_version": "2023-06-01", "temperature": 0.3, "max_tokens": 512},
        "amazon_bedrock": {"aws_region": "us-east-1", "aws_access_key_id": "", "aws_secret_access_key": "", "aws_session_token": "", "temperature": 0.3, "max_tokens": 512},
        "gemini_native": {"google_api_version": "v1beta", "google_api_key": "", "temperature": 0.3, "top_p": 0.9, "max_tokens": 512},
        "gemini_openai_compatible": {"google_api_key": "", "temperature": 0.3, "max_tokens": 512},
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
        "upstream failed": {
            "zh": "上游接口返回错误：请检查原始探针对话历史中的具体错误文本，再确认接口格式、模型权限或网关状态。",
            "en": "The upstream endpoint returned an error. Check the raw probe history for the exact failure, then verify interface type, model access, or gateway health.",
        },
        "did not contain content": {
            "zh": "接口调用成功但返回空输出：日志显示请求已到达上游，但正文为空。建议先核对该接口是否真的支持当前模型，或切换到更匹配的接口格式。",
            "en": "The request reached the upstream but returned no content. Verify that the selected interface truly supports this model, or switch to a more suitable interface type.",
        },
        "empty responses output": {
            "zh": "Responses 接口返回空输出：请求成功但没有正文，可结合原始探针对话与后台日志检查模型是否只记账未产出。",
            "en": "The Responses endpoint returned an empty body. The request succeeded but produced no text output.",
        },
        "rate": {
            "zh": "触发频率限制：请稍后重试，或降低并发和采样轮数。",
            "en": "Rate limit hit: retry later or lower concurrency and sampling rounds.",
        },
        "500": {
            "zh": "上游服务暂时异常：服务端返回 500，可稍后重试或切换接口格式。",
            "en": "Upstream service is unstable: received HTTP 500. Retry later or switch interface type.",
        },
        "permission": {
            "zh": "模型无权限：当前账号或 key 没有该模型的访问资格。",
            "en": "Model access denied: the account or key is not allowed to use this model.",
        },
        "signing failed": {
            "zh": "Bedrock 请求签名失败：请检查 AWS Access Key、Secret Key、Session Token 与 Region。",
            "en": "Bedrock request signing failed: verify AWS access key, secret, session token, and region.",
        },
        "requires base_url": {
            "zh": "请为基线接口填写 Base URL；Responses 与部分兼容接口必须同时提供基线和目标地址。",
            "en": "Provide a Base URL for the baseline endpoint; Responses and some compatible interfaces require both baseline and target URLs.",
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
            "role_help_title": "基线 / 目标是什么意思？",
            "baseline_key": "基线 API Key",
            "target_key": "目标 API Key",
            "baseline_model": "基线模型",
            "baseline_url": "基线 Base URL",
            "target_model": "目标模型",
            "target_url": "目标 Base URL",
            "rounds": "采样轮数",
            "language": "界面语言",
            "interface_type": "接口格式",
            "start": "启动深度审计",
            "probing": "[INFO] 正在执行多维探针与响应采集...",
            "done": "[SUCCESS] 审计完成。",
            "verdict": "结论",
            "feasibility": "可行度评分",
            "radar": "8 维探针雷达图",
            "heatmap": "跨轮次距离热力图",
            "raw": "原始探针对话",
        },
        "en": {
            "title": "ShadowHunter-X: LLM API Audit System",
            "sidebar": "Audit Configuration",
            "role_help_title": "What do baseline and target mean?",
            "baseline_key": "Baseline API Key",
            "target_key": "Target API Key",
            "baseline_model": "Baseline Model",
            "baseline_url": "Baseline Base URL",
            "target_model": "Target Model",
            "target_url": "Target Base URL",
            "rounds": "Sampling Rounds",
            "language": "Language",
            "interface_type": "Interface Type",
            "start": "Launch Deep Audit",
            "probing": "[INFO] Running multi-probe collection...",
            "done": "[SUCCESS] Audit completed.",
            "verdict": "Verdict",
            "feasibility": "Feasibility",
            "radar": "8-Dimension Probe Radar",
            "heatmap": "Cross-Round Distance Heatmap",
            "raw": "Raw Probe Dialogs",
        },
    }


def build_audit_role_explanation(language: str) -> str:
    if language == "zh":
        return (
            "基线模型（可信参考）是你认为正常、官方或稳定的接口；目标模型（待审查对象）是你想拿来对比审计的接口。"
            "本工具会用同一组探针同时请求两边，再比较语义、结构、多轮一致性和漂移，所以通常需要两套配置。"
            "如果两边其实是同一个平台，也可以填写同一个 URL、同一个 API Key，只替换模型名。"
        )
    return (
        "Baseline model: the trusted reference endpoint. Target model: the endpoint you want to audit against it. "
        "The tool sends the same probes to both sides, then compares semantic similarity, structure, multi-round consistency, and drift. "
        "If both sides are on the same platform, you can still reuse the same URL and API key and only change the model name."
    )


def build_default_form_state() -> dict[str, object]:
    return {
        "baseline_provider": "openai-compatible",
        "target_provider": "openai-compatible",
        "baseline_model": "gpt-5.2",
        "baseline_url": os.getenv("SHADOWHUNTER_BASELINE_BASE_URL", "https://api.42w.shop/v1"),
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
            "anthropic_messages",
            "amazon_bedrock",
            "gemini_native",
            "gemini_openai_compatible",
        ],
        "translations": build_translations(),
        "interface_field_specs": build_interface_field_specs(),
        "provider_runtime_defaults": build_provider_runtime_defaults(),
    }


def build_result_cards(results: dict) -> dict:
    return {
        "metrics": [
            {"label_zh": "模型相似度", "label_en": "Similarity", "value": results["similarity"], "tone": _metric_tone(float(results["similarity"]))},
            {"label_zh": "可信度评分", "label_en": "Confidence", "value": results["confidence"], "tone": _metric_tone(float(results["confidence"]))},
            {"label_zh": "差异比率", "label_en": "Ratio", "value": results["ratio"], "tone": _ratio_tone(float(results["ratio"]))},
            {"label_zh": "可行度评分", "label_en": "Feasibility", "value": results.get("feasibility", results["confidence"]), "tone": _metric_tone(float(results.get("feasibility", results["confidence"])))},
        ],
        "verdict": results.get("verdict", "UNKNOWN"),
        "path_card": {
            "interface": results.get("active_interface", "unknown"),
            "path": results.get("active_path", "unknown"),
            "output_state": results.get("output_state", "unknown"),
        },
        "error_summary": results.get("error_summary", ""),
        "error_explained": results.get("error_explained", ""),
        "raw_interactions": results["raw_interactions"],
    }


def classify_interaction_status(item: dict[str, Any]) -> str:
    joined = f"{item.get('baseline_response', '')} {item.get('target_response', '')}".lower()
    if "did not contain content" in joined or "empty responses output" in joined or "empty chat completion payload" in joined:
        return "empty_output"
    if "[error]" in joined:
        return "error"
    return "success"


def filter_raw_interactions(items: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "all":
        return items
    return [item for item in items if classify_interaction_status(item) == mode]


def _metric_tone(value: float) -> str:
    if value >= 75:
        return "good"
    if value >= 45:
        return "warn"
    return "danger"


def _ratio_tone(value: float) -> str:
    if value <= 1.15:
        return "good"
    if value <= 1.5:
        return "warn"
    return "danger"


def build_gateway_configs(
    *,
    interface_type: str,
    baseline_model: str,
    target_model: str,
    baseline_key: str,
    target_key: str,
    baseline_url: str,
    target_url: str,
    runtime_options: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    base_provider = "openai-compatible"
    return {
        "baseline": {
            "provider": base_provider,
            "model": baseline_model,
            "api_key": baseline_key,
            "base_url": baseline_url,
            "interface_type": interface_type,
            "provider_options": runtime_options,
        },
        "target": {
            "provider": base_provider,
            "model": target_model,
            "api_key": target_key,
            "base_url": target_url,
            "interface_type": interface_type,
            "provider_options": runtime_options,
        },
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
        with st.expander(str(copy["role_help_title"]), expanded=False):
            st.caption(build_audit_role_explanation(language))
        interface_index = list(defaults["supported_interfaces"]).index(str(defaults["interface_type"]))
        interface_type = st.selectbox(str(copy["interface_type"]), options=list(defaults["supported_interfaces"]), index=interface_index)
        baseline_key = st.text_input(str(copy["baseline_key"]), type="password")
        target_key = st.text_input(str(copy["target_key"]), type="password")
        baseline_model = st.text_input(str(copy["baseline_model"]), value=str(defaults["baseline_model"]))
        baseline_url = st.text_input(str(copy["baseline_url"]), value=str(defaults["baseline_url"]))
        target_model = st.text_input(str(copy["target_model"]), value=str(defaults["target_model"]))
        target_url = st.text_input(str(copy["target_url"]), value=str(defaults["target_url"]))
        rounds = st.slider(str(copy["rounds"]), min_value=int(defaults["min_rounds"]), max_value=int(defaults["max_rounds"]), value=int(defaults["rounds"]))
        st.caption("Best practice / 最佳实践：默认保持低 Temperature，OpenAI Compatible 建议关闭 Top-P。")
        with st.expander("Provider Parameters / 参数说明", expanded=False):
            for field in defaults["interface_field_specs"][language][interface_type]:
                st.checkbox(str(field["label"]), value=bool(field["enabled"]), key=f"param-toggle-{interface_type}-{field['key']}", help=str(field["help"]))
                default_value = defaults["provider_runtime_defaults"].get(interface_type, {}).get(field["key"], "")
                if isinstance(default_value, (int, float)):
                    st.text_input(str(field["label"]) + " Value", value=str(default_value), key=f"param-value-{interface_type}-{field['key']}")
                else:
                    st.text_input(str(field["label"]) + " Value", value=str(default_value), key=f"param-value-{interface_type}-{field['key']}")
        start_btn = st.button(str(copy["start"]), use_container_width=True)

    st.title(str(copy["title"]))

    if start_btn and baseline_key and target_key:
        status_text = st.empty()
        progress_bar = st.progress(0.0)
        status_text.info(str(copy["probing"]))
        runtime_options = collect_provider_runtime_options(interface_type, defaults)
        configs = build_gateway_configs(
            interface_type=interface_type,
            baseline_model=baseline_model,
            target_model=target_model,
            baseline_key=baseline_key,
            target_key=target_key,
            baseline_url=baseline_url,
            target_url=target_url,
            runtime_options=runtime_options,
        )
        baseline_gateway = UnifiedGateway(**configs["baseline"])
        target_gateway = UnifiedGateway(**configs["target"])
        engine = AuditEngine(baseline_gateway=baseline_gateway, target_gateway=target_gateway)
        results = asyncio.run(engine.run_audit(rounds=rounds, progress_callback=progress_bar.progress))
        results["error_explained"] = classify_error_message(results.get("error_summary", ""), language)
        status_text.success(str(copy["done"]))
        render_results(results, copy)


def render_results(results: dict, copy: dict[str, str]) -> None:
    if st is None:
        return
    cards = build_result_cards(results)
    st.markdown('<div class="bento-grid">', unsafe_allow_html=True)
    columns = st.columns(4)
    for column, item in zip(columns, cards["metrics"], strict=False):
        with column:
            st.markdown(f'<div class="metric-card metric-card-animated metric-{item["tone"]}">', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-label">{item["label_zh"]} / {item["label_en"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{item["value"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    st.caption(f"{copy['verdict']}: {cards['verdict']}")
    path_card = cards["path_card"]
    st.markdown(
        f'<div class="error-card error-secondary">Interface: {path_card["interface"]} | Path: {path_card["path"]} | Output: {path_card["output_state"]}</div>',
        unsafe_allow_html=True,
    )
    if cards["error_summary"]:
        st.markdown(f'<div class="error-card error-primary">{cards["error_summary"]}</div>', unsafe_allow_html=True)
    if cards["error_explained"]:
        st.markdown(f'<div class="error-card error-secondary">{cards["error_explained"]}</div>', unsafe_allow_html=True)

    st.divider()
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader(str(copy["radar"]))
        if st_echarts is not None:
            st.markdown('<div class="chart-card radar-card">', unsafe_allow_html=True)
            st_echarts(build_radar_option(results["radar_data"]), height="420px")
            st.markdown('</div>', unsafe_allow_html=True)
    with chart_col2:
        st.subheader(str(copy["heatmap"]))
        if st_echarts is not None:
            heatmap_option = build_heatmap_option(results["heatmap_data"])
            st.markdown('<div class="chart-card heatmap-card">', unsafe_allow_html=True)
            st_echarts(heatmap_option, height="420px")
            st.markdown(f'<div class="legend-callout">{heatmap_option.get("legend_explanation", "")}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="history-drawer">', unsafe_allow_html=True)
    with st.expander(str(copy["raw"])):
        filter_mode = st.selectbox("History Filter / 历史筛选", options=["all", "success", "empty_output", "error"], index=0)
        st.json(filter_raw_interactions(cards["raw_interactions"], filter_mode))
    st.markdown('</div></div>', unsafe_allow_html=True)


def collect_provider_runtime_options(interface_type: str, defaults: dict[str, object]) -> dict[str, Any]:
    options = dict(defaults["provider_runtime_defaults"].get(interface_type, {}))
    if st is None:
        return options
    for key in list(options.keys()):
        value = st.session_state.get(f"param-value-{interface_type}-{key}", options[key])
        if isinstance(options[key], float):
            try:
                options[key] = float(value)
            except (TypeError, ValueError):
                pass
        elif isinstance(options[key], int):
            try:
                options[key] = int(value)
            except (TypeError, ValueError):
                pass
        else:
            options[key] = value
    return options


if __name__ == "__main__":
    render_app()
