"""Lazy access to built-in split background templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BACKGROUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    parts = sorted(BACKGROUNDS_DIR.glob(f"{name}.part*"))
    if not parts:
        raise ValueError(f"Unknown background: {name}")
    return b"".join(part.read_bytes() for part in parts)
