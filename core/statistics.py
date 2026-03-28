from __future__ import annotations

from math import exp
from statistics import median


def compute_similarity(ratio: float) -> float:
    return round(max(0.0, 100 * exp(-1.5 * max(0.0, ratio - 1.1))), 4)


def compute_confidence(success_rate: float, target_self_distance: float) -> float:
    penalty = 1 - min(1.0, target_self_distance / 0.5)
    return round(success_rate * penalty * 100, 4)


def next_round_target(current_rounds: int, target_self_distance: float) -> int:
    if target_self_distance > 0.5 and current_rounds < 12:
        return current_rounds + 1
    return current_rounds


def compute_summary(
    base_self_distances: list[float],
    target_self_distances: list[float],
    cross_distances: list[float],
    success_rate: float,
) -> dict[str, float | str | int]:
    s_base = median(base_self_distances) if base_self_distances else 0.0
    s_target = median(target_self_distances) if target_self_distances else 0.0
    c_cross = median(cross_distances) if cross_distances else 1.0
    ratio = round(c_cross / (max(s_base, s_target) + 0.01), 4)
    similarity = round(compute_similarity(ratio), 1)
    confidence = round(compute_confidence(success_rate, s_target), 1)
    verdict = "VERIFIED" if similarity >= 60 else "FRAUD DETECTED"
    return {
        "ratio": ratio,
        "similarity": similarity,
        "confidence": confidence,
        "verdict": verdict,
        "s_base": round(s_base, 4),
        "s_target": round(s_target, 4),
        "c_cross": round(c_cross, 4),
    }
