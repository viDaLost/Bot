"""Lazy access to the ten embedded background templates."""

from __future__ import annotations

import base64
import importlib
from functools import lru_cache

MODULES = {
    "arctic_botanic_paper.jpg": "arctic_botanic_paper",
    "dune_linen_frame.jpg": "dune_linen_frame",
    "emerald_terracotta_flow.jpg": "emerald_terracotta_flow",
    "ivory_carbon_copper.jpg": "ivory_carbon_copper",
    "modern_midnight_horizon.jpg": "modern_midnight_horizon",
    "noir_mint_geometry.jpg": "noir_mint_geometry",
    "ocean_lavender_orbit.jpg": "ocean_lavender_orbit",
    "rose_emerald_hall.jpg": "rose_emerald_hall",
    "synth_crystal_silk.jpg": "synth_crystal_silk",
    "void_zen_room.jpg": "void_zen_room",
}


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    try:
        module_name = MODULES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown background: {name}") from exc
    module = importlib.import_module(f"{__name__}.{module_name}")
    return base64.b64decode(module.DATA)
