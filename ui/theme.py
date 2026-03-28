from __future__ import annotations


def build_theme_css() -> str:
    return """
    <style>
    .stApp { background: #0E1117; color: #E6F8EE; }
    .metric-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 16px; }
    .audit-shell { border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03); border-radius: 24px; padding: 24px; }
    </style>
    """


def load_css(st_module) -> None:
    st_module.markdown(build_theme_css(), unsafe_allow_html=True)
