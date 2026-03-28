from __future__ import annotations

import asyncio
from itertools import combinations

from core.distance import multimodal_distance
from core.probes import PROBE_LIBRARY, build_probe_conversation
from core.statistics import compute_summary, next_round_target


class AuditEngine:
    def __init__(self, baseline_gateway, target_gateway) -> None:
        self.baseline_gateway = baseline_gateway
        self.target_gateway = target_gateway

    async def run_audit(self, rounds: int, progress_callback) -> dict:
        current_rounds = rounds
        results = None
        while True:
            results = await self._run_fixed_rounds(current_rounds, progress_callback)
            next_rounds = next_round_target(current_rounds, float(results["s_target"]))
            if next_rounds == current_rounds:
                results["rounds_completed"] = current_rounds
                return results
            current_rounds = next_rounds

    async def _run_fixed_rounds(self, rounds: int, progress_callback) -> dict:
        baseline_by_probe: dict[str, list[str]] = {probe.dimension: [] for probe in PROBE_LIBRARY}
        target_by_probe: dict[str, list[str]] = {probe.dimension: [] for probe in PROBE_LIBRARY}
        raw_interactions = []
        total = len(PROBE_LIBRARY) * rounds
        completed = 0

        for round_index in range(rounds):
            tasks = [self._run_probe(round_index, probe) for probe in PROBE_LIBRARY]
            probe_rows = await asyncio.gather(*tasks)
            for row in probe_rows:
                baseline_by_probe[row["dimension"]].append(row["baseline_response"])
                target_by_probe[row["dimension"]].append(row["target_response"])
                raw_interactions.append(row)
                completed += 1
                progress_callback(round(completed / total, 4))

        base_self = []
        target_self = []
        cross = []
        radar_data = []
        for probe in PROBE_LIBRARY:
            base_values = baseline_by_probe[probe.dimension]
            target_values = target_by_probe[probe.dimension]
            probe_base_self = self._pairwise_self(base_values)
            probe_target_self = self._pairwise_self(target_values)
            probe_cross = [multimodal_distance(a, b) for a, b in zip(base_values, target_values, strict=False)]
            base_self.extend(probe_base_self)
            target_self.extend(probe_target_self)
            cross.extend(probe_cross)
            radar_data.append(
                {
                    "dimension": probe.dimension,
                    "baseline": round(1 - (sum(probe_base_self) / len(probe_base_self) if probe_base_self else 0.0), 4),
                    "target": round(1 - (sum(probe_target_self) / len(probe_target_self) if probe_target_self else 0.0), 4),
                }
            )

        summary = compute_summary(base_self, target_self, cross, success_rate=1.0)
        error_messages = []
        for row in raw_interactions:
            if row["baseline_response"].startswith("[ERROR]"):
                error_messages.append(f"Baseline endpoint error: {row['baseline_response']}")
            if row["target_response"].startswith("[ERROR]"):
                error_messages.append(f"Target endpoint error: {row['target_response']}")
        return {
            **summary,
            "error_summary": error_messages[0] if error_messages else "",
            "raw_interactions": raw_interactions,
            "radar_data": radar_data,
            "heatmap_data": self._build_heatmap(cross),
        }

    async def _run_probe(self, round_index: int, probe) -> dict:
        messages = build_probe_conversation(probe)
        prompt = "\n\n".join(message["content"] for message in messages) + f"\n\n[round={round_index + 1}]"
        baseline_response, target_response = await asyncio.gather(
            self.baseline_gateway.async_generate(prompt),
            self.target_gateway.async_generate(prompt),
        )
        return {
            "round": round_index + 1,
            "probe": probe.title,
            "dimension": probe.dimension,
            "prompt": messages,
            "baseline_response": baseline_response,
            "target_response": target_response,
        }

    def _pairwise_self(self, texts: list[str]) -> list[float]:
        return [multimodal_distance(left, right) for left, right in combinations(texts, 2)]

    def _build_heatmap(self, cross: list[float]) -> list[list[float]]:
        if not cross:
            return []
        size = min(8, len(cross))
        matrix = []
        for row in range(size):
            matrix.append([round(cross[(row + column) % len(cross)], 4) for column in range(size)])
        return matrix
