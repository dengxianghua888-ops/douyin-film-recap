from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DEFAULT_TARGETS = {
    "claude": Path.home() / ".claude" / "skills" / "douyin-film-recap",
    "codex": Path.home() / ".codex" / "skills" / "douyin-film-recap",
    "cursor": Path.home() / ".cursor" / "skills" / "douyin-film-recap",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the Skill by link or copy.")
    parser.add_argument("--agent", choices=sorted(DEFAULT_TARGETS), default="claude")
    parser.add_argument("--target", type=Path, default=None)
    parser.add_argument("--copy", action="store_true", help="Copy instead of symlink")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target = (args.target or DEFAULT_TARGETS[args.agent]).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not args.force:
            raise SystemExit(f"Target exists: {target}. Use --force to replace it.")
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    if args.copy:
        shutil.copytree(
            root,
            target,
            ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "work"),
        )
        action = "copied"
    else:
        target.symlink_to(root, target_is_directory=True)
        action = "linked"
    print(f"Skill {action}: {target} -> {root}")


if __name__ == "__main__":
    main()
