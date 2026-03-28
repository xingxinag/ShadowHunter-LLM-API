from __future__ import annotations


DIMENSION_LABELS = {
    "metadata_hallucination": "元数据幻觉 / Metadata Hallucination",
    "alignment_boundary": "对齐边界 / Alignment Boundary",
    "malformed_syntax": "畸形语法 / Malformed Syntax",
    "formatting_quirks": "格式癖好 / Formatting Quirks",
    "reasoning_trap": "逻辑陷阱 / Logical Consistency",
    "multilingual_nuance": "多语细节 / Multilingual Nuance",
    "coding_style": "代码风格 / Coding Style",
    "self_identification": "自我识别 / Self Identification",
}


def build_radar_option(points: list[dict[str, float | str]]) -> dict:
    return {
        "tooltip": {
            "trigger": "item",
        },
        "radar": {
            "indicator": [
                {"name": DIMENSION_LABELS.get(str(point["dimension"]), str(point["dimension"])), "max": 1}
                for point in points
            ],
            "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.14)"}},
        },
        "series": [
            {
                "type": "radar",
                "data": [
                    {"name": "Baseline", "value": [point["baseline"] for point in points]},
                    {"name": "Target", "value": [point["target"] for point in points]},
                ],
            }
        ],
    }


def build_heatmap_option(matrix: list[list[float]]) -> dict:
    data = []
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            data.append([column_index, row_index, value])
    return {
        "xAxis": {"type": "category", "data": list(range(len(matrix[0]) if matrix else 0))},
        "yAxis": {"type": "category", "data": list(range(len(matrix)))},
        "visualMap": {
            "min": 0,
            "max": 1,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
            "text": ["逻辑漂移", "高相似"],
            "inRange": {"color": ["#6EE7F9", "#0EA5E9", "#172554"]},
        },
        "legend_explanation": "浅蓝色代表低距离/高相似度，深色代表更强的逻辑漂移与跨轮次偏差。",
        "series": [{"type": "heatmap", "data": data}],
    }
