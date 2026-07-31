"""Lazy and resilient access to the embedded background templates."""

from __future__ import annotations

import base64
import binascii
import importlib
import logging
from functools import lru_cache
from io import BytesIO
from typing import Iterable

from PIL import Image

logger = logging.getLogger(__name__)

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


def _normalize_payload(value: object) -> str:
    if isinstance(value, bytes):
        payload = value.decode("ascii", errors="ignore")
    else:
        payload = str(value)

    payload = "".join(payload.split())
    if payload.lower().startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]

    # A JPEG encoded as base64 normally starts with /9j/. Remove accidental
    # prefixes that may have appeared while a large resource was published.
    jpeg_marker = payload.find("/9j/")
    if jpeg_marker > 0:
        payload = payload[jpeg_marker:]
    return payload


def _repair_candidates(payload: str) -> Iterable[str]:
    """Yield conservative padding/one-character repair candidates."""
    body = payload.rstrip("=")
    seen: set[str] = set()

    raw_candidates = [body]
    if len(body) % 4 == 1:
        # A base64 payload can never contain 1 data character modulo 4.
        # The common publication failure is one accidental trailing character.
        raw_candidates.extend((body[:-1], body[1:]))

    # Also tolerate a short damaged suffix. Every candidate is verified as a
    # complete image before it can be returned.
    raw_candidates.extend(body[:-trim] for trim in range(1, 4) if len(body) > trim)

    for candidate in raw_candidates:
        if not candidate or candidate in seen or len(candidate) % 4 == 1:
            continue
        seen.add(candidate)
        yield candidate + ("=" * (-len(candidate) % 4))


def _decode_module(module_name: str) -> bytes:
    module = importlib.import_module(f"{__name__}.{module_name}")
    payload = _normalize_payload(getattr(module, "DATA", ""))
    last_error: Exception | None = None

    for candidate in _repair_candidates(payload):
        try:
            data = base64.b64decode(candidate, validate=True)
            if not (data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")):
                raise ValueError("decoded resource is not a complete JPEG")
            with Image.open(BytesIO(data)) as image:
                image.verify()
            return data
        except (binascii.Error, OSError, ValueError) as exc:
            last_error = exc

    raise ValueError(f"Invalid embedded background {module_name}: {last_error}")


def _fallback_names(requested_name: str) -> Iterable[str]:
    yield requested_name
    preferred = "modern_midnight_horizon.jpg"
    if requested_name != preferred:
        yield preferred
    for name in MODULES:
        if name not in {requested_name, preferred}:
            yield name


@lru_cache(maxsize=None)
def get_background_bytes(name: str) -> bytes:
    if name not in MODULES:
        raise ValueError(f"Unknown background: {name}")

    failures: list[str] = []
    for candidate_name in _fallback_names(name):
        try:
            data = _decode_module(MODULES[candidate_name])
            if candidate_name != name:
                logger.warning(
                    "Background %s is invalid; using %s instead",
                    name,
                    candidate_name,
                )
            return data
        except (ImportError, ValueError) as exc:
            failures.append(f"{candidate_name}: {exc}")

    raise ValueError("No valid embedded background is available: " + "; ".join(failures))
