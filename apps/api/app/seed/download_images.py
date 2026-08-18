"""One-off fetch of the LEGO box/gallery art into ``data/lego-images/``.

Run manually, from a plain Python environment with ``httpx`` installed, whenever
a new set is added to the demo data:

    pip install httpx
    python3 apps/api/app/seed/download_images.py

Deliberately standalone (no ``app`` import): the set numbers come straight from
``lego-inventory.json`` plus the hand-written sets below, so this never needs a
database connection or the rest of the app's dependencies — just network access.

The seed itself (``app/seed/__init__.py``) never touches the network — it only
reads whatever this script already saved. Re-running is safe: a set whose
folder already has a box shot is skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).parent / "data"
IMAGES_DIR = DATA_DIR / "lego-images"
BOX_URL = "https://images.brickset.com/sets/images/{number}-1.jpg"
ALT_URL = "https://images.brickset.com/sets/AdditionalImages/{number}-1/{number}_alt{index}.jpg"
MAX_ALTS = 3

#: Kept in sync by hand with the ``set_number`` values in ``app/seed/__init__.py``'s
#: hand-written ``SETS`` list (the MOC has none, so it is not here).
HAND_WRITTEN_SET_NUMBERS = ["10307", "75192", "21318", "42115", "10497", "76240"]


def all_set_numbers() -> list[str]:
    inventory = json.loads((DATA_DIR / "lego-inventory.json").read_text(encoding="utf-8"))
    inventory_numbers = [row["set_number"] for row in inventory["sets"] if row["set_number"]]
    return sorted(set(HAND_WRITTEN_SET_NUMBERS) | set(inventory_numbers))


def _fetch(client: httpx.Client, url: str) -> bytes | None:
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError:
        return None


def download_all() -> None:
    numbers = all_set_numbers()

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for index, number in enumerate(numbers, start=1):
            folder = IMAGES_DIR / number
            box_path = folder / "box.jpg"
            if box_path.exists():
                print(f"[{index}/{len(numbers)}] {number}: already have it", flush=True)
                continue

            box = _fetch(client, BOX_URL.format(number=number))
            if box is None:
                print(f"[{index}/{len(numbers)}] {number}: no box shot", flush=True)
                continue

            folder.mkdir(parents=True, exist_ok=True)
            box_path.write_bytes(box)
            fetched = 1
            for alt_index in range(1, MAX_ALTS + 1):
                alt = _fetch(client, ALT_URL.format(number=number, index=alt_index))
                if alt is None:
                    break
                (folder / f"alt{alt_index}.jpg").write_bytes(alt)
                fetched += 1
            print(f"[{index}/{len(numbers)}] {number}: saved {fetched} image(s)", flush=True)


if __name__ == "__main__":
    download_all()
    sys.exit(0)
