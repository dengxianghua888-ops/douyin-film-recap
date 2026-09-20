"""Minimal repository-local validation for the SKILL.md entrypoint."""
from pathlib import Path
import re

import yaml


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise SystemExit("SKILL.md is missing YAML frontmatter")
    frontmatter = yaml.safe_load(match.group(1))
    if frontmatter.get("name") != root.name:
        raise SystemExit("Skill name and repository directory must match")
    if not str(frontmatter.get("description", "")).strip():
        raise SystemExit("Skill description is required")
    if re.search(r"^\s*\[TODO:[^\n]*\]\s*$", content, re.MULTILINE):
        raise SystemExit("SKILL.md contains an unfinished TODO")
    print("Skill is valid")


if __name__ == "__main__":
    main()
