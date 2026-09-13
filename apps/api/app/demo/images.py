"""Deterministic placeholder cover art for the demo dataset.

The seed must work on an offline NAS, and hotlinking is banned by M9 FR-9.11 — so
instead of downloading anything, it generates a small PNG per set locally and pushes
it through the *same* ``documents.store_bytes`` path a real upload takes (magic-byte
validation, content addressing, signed delivery). That proves the image pipeline end
to end in the demo data without a single network call.
"""

from __future__ import annotations

import struct
import zlib

WIDTH = 320
HEIGHT = 240


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _blend(
    top: tuple[int, int, int], bottom: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))  # type: ignore[return-value]


def gradient_png(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> bytes:
    """A vertical gradient with a simple stud grid — enough to look like a set tile."""
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)  # PNG filter type 0 (None) for this scanline
        base = _blend(top, bottom, y / (HEIGHT - 1))
        for x in range(WIDTH):
            # Faint 40px grid of "studs" so the tiles are visually distinguishable.
            on_stud = ((x % 40) - 20) ** 2 + ((y % 40) - 20) ** 2 < 90
            pixel = _blend(base, (255, 255, 255), 0.22) if on_stud else base
            rows += bytes(pixel)

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)  # 8-bit truecolour
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + _chunk(b"IEND", b"")
    )


# One palette per seeded theme, so the demo grid is readable at a glance.
PALETTES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "Icons": ((37, 99, 235), (12, 40, 105)),
    "Star Wars": ((13, 148, 136), (6, 60, 56)),
    "Ideas": ((192, 38, 211), (85, 15, 95)),
    "Technic": ((234, 88, 12), (110, 38, 5)),
    "MOC": ((101, 163, 13), (43, 70, 6)),
}
DEFAULT_PALETTE = ((100, 116, 139), (30, 41, 59))


def cover_for(theme: str | None) -> bytes:
    top, bottom = PALETTES.get(theme or "", DEFAULT_PALETTE)
    return gradient_png(top, bottom)
