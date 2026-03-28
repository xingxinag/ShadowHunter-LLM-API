import asyncio

from core.engine import AuditEngine
from core.probes import PROBE_LIBRARY


class StubGateway:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.calls = 0

    async def async_generate(self, prompt: str) -> str:
        self.calls += 1
        return f"{self.prefix}:{self.calls}:{prompt[:12]}"


def test_engine_runs_all_probe_dimensions_and_reports_progress() -> None:
    progress = []
    engine = AuditEngine(
        baseline_gateway=StubGateway("base"),
        target_gateway=StubGateway("target"),
    )

    result = asyncio.run(engine.run_audit(rounds=3, progress_callback=progress.append))

    assert len(result["raw_interactions"]) == len(PROBE_LIBRARY) * 3
    assert progress[-1] == 1.0


def test_engine_never_exceeds_twelve_rounds_when_adapting() -> None:
    engine = AuditEngine(
        baseline_gateway=StubGateway("base"),
        target_gateway=StubGateway("target"),
    )

    result = asyncio.run(engine.run_audit(rounds=12, progress_callback=lambda _: None))

    assert result["rounds_completed"] == 12
