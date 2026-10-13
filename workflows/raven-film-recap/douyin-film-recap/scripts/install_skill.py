from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DEFAULT_TARGETS = {
    "claude": Path.home() / ".claude" / "skills" / "douyin-film-recap",
    "codex": Path.home() / ".codex" / "skills" / "douyin-film-recap",
    "cursor": Path.home() / ".cursor" / "skills" / "douyin-film-recap",
}


def checked_target(root: Path, target: Path) -> Path:
    # Keep the final path component lexical: resolving an installed symlink
    # would turn --force into deletion of the source that it points to.
    target = target.expanduser().absolute()
    if target.name == "..":
        raise SystemExit(f"Unsafe target: {target}. A parent-directory target is not allowed.")
    try:
        actual_target = target.parent.resolve() / target.name
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"Unsafe target parent: {target.parent}: {exc}") from exc
    # Resolve ancestors, not the final component, to also catch paths entering
    # the source through a parent symlink. Check before mkdir or removal.
    for candidate in (target, actual_target):
        if candidate == root or candidate in root.parents or root in candidate.parents:
            raise SystemExit(f"Unsafe target: {target}. Target and source must not overlap: {root}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the Skill by link or copy.")
    parser.add_argument("--agent", choices=sorted(DEFAULT_TARGETS), default="claude")
    parser.add_argument("--target", type=Path, default=None)
    parser.add_argument("--copy", action="store_true", help="Copy instead of symlink")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target = checked_target(root, args.target or DEFAULT_TARGETS[args.agent])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not args.force:
            raise SystemExit(f"Target exists: {target}. Use --force to replace it.")
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
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
