from __future__ import annotations

import json
from pathlib import Path

from douyin_film_recap.models import (
    CharacterRegistry,
    HighlightDocument,
    KnowledgeTimeline,
    PipelineState,
    QCReport,
    RecapPlan,
    SceneAnalysisDocument,
    SceneIndex,
    SourceManifest,
    StoryGraph,
    Storyboard,
    TranscriptDocument,
)

MODELS = [
    SourceManifest,
    TranscriptDocument,
    SceneIndex,
    SceneAnalysisDocument,
    CharacterRegistry,
    StoryGraph,
    KnowledgeTimeline,
    HighlightDocument,
    RecapPlan,
    Storyboard,
    QCReport,
    PipelineState,
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        path = output_dir / f"{model.__name__}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(path)


if __name__ == "__main__":
    main()
