from core.statistics import compute_confidence, compute_similarity, compute_summary, next_round_target


def test_similarity_uses_updated_exponential_formula() -> None:
    assert compute_similarity(1.1) == 100.0
    assert round(compute_similarity(1.8), 1) == 35.0


def test_confidence_penalizes_high_target_variance() -> None:
    assert compute_confidence(success_rate=1.0, target_self_distance=0.6) == 0.0


def test_summary_uses_medians() -> None:
    summary = compute_summary([0.1, 0.2, 0.9], [0.2, 0.3, 0.8], [0.4, 0.5, 0.6], 1.0)
    assert summary["ratio"] == 1.6129


def test_adaptive_sampling_caps_at_twelve_rounds() -> None:
    assert next_round_target(current_rounds=6, target_self_distance=0.6) == 7
    assert next_round_target(current_rounds=12, target_self_distance=0.9) == 12
