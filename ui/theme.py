from __future__ import annotations


def build_theme_css() -> str:
    return """
    <style>
    .stApp { background: radial-gradient(circle at top left, rgba(0,255,65,0.12), transparent 28%), radial-gradient(circle at bottom right, rgba(255,0,127,0.12), transparent 25%), #0E1117; color: #E6F8EE; }
    .bento-grid { display: grid; gap: 18px; }
    .metric-card { background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04)); border: 1px solid rgba(255,255,255,0.14); border-radius: 20px; padding: 14px; box-shadow: 0 16px 40px rgba(0,0,0,0.24); backdrop-filter: blur(14px); min-height: 150px; }
    .metric-card-animated { animation: metricFade 0.7s ease-out; }
    .metric-label { color: #D1FAE5; font-size: 0.95rem; font-weight: 700; line-height: 1.45; margin-bottom: 10px; }
    .metric-value { color: #FFFFFF; font-size: 2rem; font-weight: 900; letter-spacing: 0.01em; text-shadow: 0 2px 14px rgba(255,255,255,0.08); }
    .metric-good { box-shadow: 0 0 0 1px rgba(16,185,129,0.22), 0 16px 40px rgba(16,185,129,0.12); }
    .metric-warn { box-shadow: 0 0 0 1px rgba(245,158,11,0.22), 0 16px 40px rgba(245,158,11,0.12); }
    .metric-danger { box-shadow: 0 0 0 1px rgba(239,68,68,0.24), 0 16px 40px rgba(239,68,68,0.12); }
    .chart-card { border: 1px solid rgba(255,255,255,0.08); background: rgba(10,16,26,0.82); border-radius: 22px; padding: 14px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.04); }
    .radar-card { animation: radarReveal 0.8s cubic-bezier(.2,.8,.2,1); }
    .heatmap-card { animation: heatmapGlow 1.1s ease-out; }
    .history-drawer { position: relative; border: 1px solid rgba(255,255,255,0.08); background: rgba(8,12,19,0.76); border-radius: 22px; padding: 8px 14px 14px; box-shadow: 0 18px 48px rgba(0,0,0,0.26); }
    .error-card { border-radius: 16px; padding: 12px 14px; margin: 10px 0; font-weight: 500; }
    .error-primary { background: rgba(255,82,82,0.14); border: 1px solid rgba(255,82,82,0.28); color: #FFD4D4; }
    .error-secondary { background: rgba(56,189,248,0.12); border: 1px solid rgba(56,189,248,0.22); color: #D8F5FF; }
    .legend-callout { margin-top: 10px; color: #FFFFFF; font-size: 0.96rem; font-weight: 700; line-height: 1.6; background: rgba(37,99,235,0.18); border: 1px solid rgba(96,165,250,0.34); border-radius: 14px; padding: 10px 12px; }
    @keyframes radarReveal { from { opacity: 0; transform: translateY(16px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes heatmapGlow { from { opacity: 0; box-shadow: 0 0 0 rgba(14,165,233,0); } to { opacity: 1; box-shadow: 0 0 32px rgba(14,165,233,0.08); } }
    @keyframes metricFade { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
    """


def load_css(st_module) -> None:
    st_module.markdown(build_theme_css(), unsafe_allow_html=True)
