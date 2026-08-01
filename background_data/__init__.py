"""Reliable access to built-in background templates stored as binary file parts."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image

BACKGROUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"

BACKGROUND_NAMES = {
    "arctic_botanic_paper.jpg",
    "dune_linen_frame.jpg",
    "emerald_terracotta_flow.jpg",
    "ivory_carbon_copper.jpg",
    "modern_midnight_horizon.jpg",
    "noir_mint_geometry.jpg",
    "ocean_lavender_orbit.jpg",
    "rose_emerald_hall.jpg",
    "synth_crystal_silk.jpg",
    "void_zen_room.jpg",
}


def _validate_image(data: bytes) -> bytes:
    """Fail early if the reconstructed asset is not a readable image."""
    with Image.open(BytesIO(data)) as image:
        image.verify()
    return data


def _read_asset_parts(name: str) -> bytes:
    """Join raw binary .partXX files belonging only to the requested background."""
    direct = BACKGROUNDS_DIR / name
    if direct.is_file():
        return _validate_image(direct.read_bytes())

    parts = sorted(BACKGROUNDS_DIR.glob(f"{name}.part*"))
    if not parts:
        raise FileNotFoundError(
            f"Background asset '{name}' was not found in {BACKGROUNDS_DIR}"
        )

    data = b"".join(part.read_bytes() for part in parts)
    return _validate_image(data)


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    if name not in BACKGROUND_NAMES:
        raise ValueError(f"Unknown background: {name}")

    # Assets are committed as raw binary chunks under assets/backgrounds.
    # Do not import synthetic background_data.* Python modules and do not
    # substitute another style when an asset is broken.
    return _read_asset_parts(name)
