#!/usr/bin/env python3
"""Source-tree convenience entry; distributable B uses its own copied sources."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
    "workflows/raven-film-recap/douyin-film-recap/src"))
from douyin_film_recap.workspace import recovery_main

if __name__ == "__main__":
    raise SystemExit(recovery_main())
