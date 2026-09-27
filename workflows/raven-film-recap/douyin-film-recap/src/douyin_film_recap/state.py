from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import PipelineState, StageRecord
from .utils import read_json, write_json


STAGES = [
    "ingest",
    "transcript",
    "scenes",
    "scene_analysis",
    "story",
    "highlights",
    "plan",
    "storyboard",
    "tts",
    "pre_qc",
    "render",
    "post_qc",
    "delivery",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, work_dir: str | Path):
        self.work_dir = Path(work_dir)
        self.path = self.work_dir / "state.json"

    def load_or_create(
        self,
        *,
        project_name: str,
        input_paths: list[str],
        config_fingerprint: str,
        input_fingerprint: str | None = None,
    ) -> PipelineState:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return PipelineState.model_validate(read_json(self.path))
        state = PipelineState(
            project_name=project_name,
            input_paths=input_paths,
            input_fingerprint=input_fingerprint,
            config_fingerprint=config_fingerprint,
            stages={stage: StageRecord() for stage in STAGES},
        )
        self.save(state)
        return state

    def save(self, state: PipelineState) -> None:
        state.updated_at = utc_now()
        write_json(self.path, state)

    def start(self, state: PipelineState, stage: str) -> None:
        record = state.stages[stage]
        record.status = "running"
        record.started_at = utc_now()
        record.finished_at = None
        record.error = None
        self.save(state)

    def pass_stage(
        self,
        state: PipelineState,
        stage: str,
        *,
        artifact: str | None = None,
        fingerprint: str | None = None,
        artifacts: dict[str, str] | None = None,
        input_fingerprint: str | None = None,
    ) -> None:
        record = state.stages[stage]
        record.status = "passed"
        record.finished_at = utc_now()
        record.artifact = artifact
        record.fingerprint = fingerprint
        record.artifacts = artifacts or {}
        record.input_fingerprint = input_fingerprint
        record.error = None
        if state.last_error and state.last_error.get("stage") == stage:
            state.last_error = None
        self.save(state)

    def skip(self, state: PipelineState, stage: str, reason: str) -> None:
        record = state.stages[stage]
        record.status = "skipped"
        record.finished_at = utc_now()
        record.error = {"code": "SKIPPED", "message": reason}
        self.save(state)

    def fail(self, state: PipelineState, stage: str, error: Exception) -> None:
        record = state.stages[stage]
        record.status = "failed"
        record.finished_at = utc_now()
        record.error = {"code": type(error).__name__, "message": str(error)}
        state.last_error = {"stage": stage, **record.error}
        self.save(state)

    def invalidate_from(self, state: PipelineState, stage: str) -> None:
        start = STAGES.index(stage)
        for name in STAGES[start:]:
            state.stages[name] = StageRecord()
        self.save(state)

    def should_run(self, state: PipelineState, stage: str, from_stage: str | None = None) -> bool:
        if from_stage:
            return STAGES.index(stage) >= STAGES.index(from_stage)
        return state.stages[stage].status != "passed"

    @staticmethod
    def selected_stages(until: str | None = None) -> Iterable[str]:
        if until is None:
            return STAGES
        return STAGES[: STAGES.index(until) + 1]
