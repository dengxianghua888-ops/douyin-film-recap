from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/check_evaluation_readiness.py"
spec = importlib.util.spec_from_file_location("evaluation_readiness", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_placeholder_is_not_a_benchmark_pass(tmp_path):
    result = module.check_case({"id": "pending", "material": "placeholder"}, tmp_path)
    assert result["status"] == "NOT_READY"
    assert result["quality_passed"] is None


def test_ready_input_is_not_a_quality_pass_and_changes_invalidate_gold(tmp_path):
    # Deliberately synthetic file: tests contract validation, not media/content quality.
    media = tmp_path / "synthetic.bin"
    media.write_bytes(b"synthetic contract fixture")
    gold = {"case_id": "fixture", "source_sha256": hashlib.sha256(media.read_bytes()).hexdigest(),
            "source_duration_sec": 10, "reviewers": ["fixture A", "fixture B"],
            "key_facts": [{"id": "fact"}], "forbidden_prepose": [],
            "must_keep": [{"start": 1, "end": 3, "types": ["performance"], "reason": "fixture"}]}
    (tmp_path / "gold.json").write_text(json.dumps(gold))
    case = {"id": "fixture", "material": media.name, "gold": "gold.json"}
    result = module.check_case(case, tmp_path)
    assert result["status"] == "READY_FOR_REVIEW" and result["quality_passed"] is None
    media.write_bytes(b"changed input")
    result = module.check_case(case, tmp_path)
    assert result["status"] == "NOT_READY"
    assert "source_gold_fingerprint_mismatch" in result["issues"]
