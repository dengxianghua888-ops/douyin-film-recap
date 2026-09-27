"""Check benchmark inputs; readiness is not a content-quality result."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml


def check_case(case: dict, base: Path) -> dict:
    issues: list[str] = []
    material = case.get("material")
    gold_value = case.get("gold")
    media = base / material if material and material != "placeholder" else None
    gold_path = base / gold_value if gold_value else None
    if media is None or not media.is_file():
        issues.append("missing_source_material")
    if gold_path is None or not gold_path.is_file():
        issues.append("missing_human_gold")
    else:
        try:
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            if gold.get("case_id") != case.get("id"):
                issues.append("gold_case_mismatch")
            if len(set(x for x in gold.get("reviewers", []) if isinstance(x, str) and x.strip())) < 2:
                issues.append("two_named_reviewers_required")
            if not gold.get("key_facts") or not gold.get("must_keep"):
                issues.append("incomplete_gold_annotations")
            if "forbidden_prepose" not in gold or not isinstance(gold["forbidden_prepose"], list):
                issues.append("missing_reveal_annotations")
            duration = gold.get("source_duration_sec", 0)
            if not isinstance(duration, (int, float)) or duration <= 0:
                issues.append("invalid_source_duration")
                duration = 0
            for item in gold.get("must_keep", []):
                if not isinstance(item, dict):
                    issues.append("invalid_highlight_annotation")
                    continue
                start, end = item.get("start"), item.get("end")
                if not (isinstance(start, (int, float)) and isinstance(end, (int, float))
                        and 0 <= start < end <= duration):
                    issues.append("invalid_highlight_boundary")
                if not item.get("reason") or not item.get("types"):
                    issues.append("incomplete_highlight_annotation")
            if media and media.is_file():
                with media.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                if digest != gold.get("source_sha256"):
                    issues.append("source_gold_fingerprint_mismatch")
        except (ValueError, TypeError, AttributeError, OSError) as exc:
            issues.append(f"invalid_gold:{type(exc).__name__}")
    return {"case_id": case.get("id"), "status": "NOT_READY" if issues else "READY_FOR_REVIEW",
            "issues": sorted(set(issues)), "quality_passed": None}


def check_manifest(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    results = [check_case(case, path.parent) for case in data["cases"]]
    return {"kind": "benchmark_readiness_only", "cases": results,
            "ready_count": sum(c["status"] == "READY_FOR_REVIEW" for c in results),
            "case_count": len(results), "quality_passed": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check_manifest(args.manifest.resolve())
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(0 if report["ready_count"] == report["case_count"] and report["case_count"] else 2)


if __name__ == "__main__":
    main()
