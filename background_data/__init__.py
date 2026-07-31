"""Lazy access to built-in background templates stored in assets/backgrounds."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BACKGROUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    path = BACKGROUNDS_DIR / name
    if not path.is_file():
        raise ValueError(f"Unknown background: {name}")
    return path.read_bytes()
