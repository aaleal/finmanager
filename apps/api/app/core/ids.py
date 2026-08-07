"""UUID v7 — time-sortable primary keys, generated in Python before insert.

Python 3.12 has no ``uuid.uuid7``; this is the RFC 9562 layout:
48-bit big-endian Unix epoch milliseconds, 4-bit version, 12 bits of randomness,
2-bit variant, 62 bits of randomness.
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    unix_ms = int(time.time() * 1000)
    rand = os.urandom(10)

    value = unix_ms << 80
    value |= 0x7 << 76  # version 7
    value |= (int.from_bytes(rand[:2], "big") & 0x0FFF) << 64
    value |= 0b10 << 62  # RFC 4122 variant
    value |= int.from_bytes(rand[2:], "big") & ((1 << 62) - 1)

    return uuid.UUID(int=value)
