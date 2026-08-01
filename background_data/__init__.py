"""Resilient access to built-in background templates."""

from __future__ import annotations

import base64
import importlib
from functools import lru_cache
from io import BytesIO

from PIL import Image

try:
    from background_assets import BACKGROUNDS as EMBEDDED_BACKGROUNDS
except Exception:  # pragma: no cover
    EMBEDDED_BACKGROUNDS = {}

PARTS = {
    'arctic_botanic_paper.jpg': ['arctic_botanic_paper_00', 'arctic_botanic_paper_01', 'arctic_botanic_paper_02', 'arctic_botanic_paper_03'],
    'dune_linen_frame.jpg': ['dune_linen_frame_00', 'dune_linen_frame_01', 'dune_linen_frame_02', 'dune_linen_frame_03', 'dune_linen_frame_04'],
    'emerald_terracotta_flow.jpg': ['emerald_terracotta_flow_00', 'emerald_terracotta_flow_01', 'emerald_terracotta_flow_02', 'emerald_terracotta_flow_03'],
    'ivory_carbon_copper.jpg': ['ivory_carbon_copper_00', 'ivory_carbon_copper_01', 'ivory_carbon_copper_02', 'ivory_carbon_copper_03'],
    'modern_midnight_horizon.jpg': ['modern_midnight_horizon_00', 'modern_midnight_horizon_01', 'modern_midnight_horizon_02', 'modern_midnight_horizon_03', 'modern_midnight_horizon_04'],
    'noir_mint_geometry.jpg': ['noir_mint_geometry_00', 'noir_mint_geometry_01', 'noir_mint_geometry_02', 'noir_mint_geometry_03', 'noir_mint_geometry_04'],
    'ocean_lavender_orbit.jpg': ['ocean_lavender_orbit_00', 'ocean_lavender_orbit_01', 'ocean_lavender_orbit_02', 'ocean_lavender_orbit_03', 'ocean_lavender_orbit_04'],
    'rose_emerald_hall.jpg': ['rose_emerald_hall_00', 'rose_emerald_hall_01', 'rose_emerald_hall_02', 'rose_emerald_hall_03', 'rose_emerald_hall_04'],
    'synth_crystal_silk.jpg': ['synth_crystal_silk_00', 'synth_crystal_silk_01', 'synth_crystal_silk_02', 'synth_crystal_silk_03'],
    'void_zen_room.jpg': ['void_zen_room_00', 'void_zen_room_01', 'void_zen_room_02', 'void_zen_room_03', 'void_zen_room_04'],
}


def _validate_image(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as image:
        image.verify()
    return data


def _load_from_embedded(name: str) -> bytes | None:
    payload = EMBEDDED_BACKGROUNDS.get(name)
    if not payload:
        return None
    return _validate_image(base64.b64decode(payload))


def _load_from_parts(name: str) -> bytes:
    modules = PARTS[name]
    encoded = ''.join(importlib.import_module(f'{__name__}.{module}').DATA for module in modules)
    return _validate_image(base64.b64decode(encoded))


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    if name not in PARTS:
        raise ValueError(f'Unknown background: {name}')

    # Prefer the single embedded asset. These payloads are validated independently
    # for each style, so one broken module cannot silently replace another style.
    try:
        data = _load_from_embedded(name)
        if data is not None:
            return data
    except Exception:
        pass

    # Fall back only to the split parts of the SAME requested background.
    # Never substitute a different style: that made several buttons show one image.
    return _load_from_parts(name)
