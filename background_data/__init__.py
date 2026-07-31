"""Lazy access to built-in background templates."""

from __future__ import annotations

import base64
import importlib
from functools import lru_cache

PARTS = {
    'arctic_botanic_paper.jpg': ['arctic_botanic_paper_0', 'arctic_botanic_paper_1', 'arctic_botanic_paper_2'],
    'dune_linen_frame.jpg': ['dune_linen_frame_0', 'dune_linen_frame_1', 'dune_linen_frame_2', 'dune_linen_frame_3', 'dune_linen_frame_4'],
    'emerald_terracotta_flow.jpg': ['emerald_terracotta_flow_0', 'emerald_terracotta_flow_1', 'emerald_terracotta_flow_2'],
    'ivory_carbon_copper.jpg': ['ivory_carbon_copper_0', 'ivory_carbon_copper_1'],
    'modern_midnight_horizon.jpg': ['modern_midnight_horizon_0', 'modern_midnight_horizon_1', 'modern_midnight_horizon_2'],
    'noir_mint_geometry.jpg': ['noir_mint_geometry_0', 'noir_mint_geometry_1'],
    'ocean_lavender_orbit.jpg': ['ocean_lavender_orbit_0', 'ocean_lavender_orbit_1'],
    'rose_emerald_hall.jpg': ['rose_emerald_hall_0', 'rose_emerald_hall_1', 'rose_emerald_hall_2'],
    'synth_crystal_silk.jpg': ['synth_crystal_silk_0', 'synth_crystal_silk_1'],
    'void_zen_room.jpg': ['void_zen_room_0', 'void_zen_room_1', 'void_zen_room_2'],
}


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    try:
        modules = PARTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown background: {name}") from exc
    encoded = "".join(importlib.import_module(f"{__name__}.{module}").DATA for module in modules)
    return base64.b64decode(encoded)
