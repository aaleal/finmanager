"""One-off fetch of the LEGO box/gallery art into ``data/lego/images/``.

Run manually, from a plain Python environment with ``httpx`` installed, whenever
a new set is added to the collection:

    pip install httpx
    python3 dev/download-lego-images.py

Lives in ``dev/`` rather than in the API package because it is the only piece of
the LEGO seeding that touches the network, and nothing the app serves ever calls
it (ADR-0062). Deliberately standalone (no ``app`` import): the set numbers come
straight off the two JSON files, so this needs neither a database connection nor
the rest of the app's dependencies — just network access.

``app/demo`` never touches the network — it only reads whatever this script
already saved. Re-running is safe: a set whose folder already has a box shot is
skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LEGO_DIR = ROOT / "data" / "lego"
IMAGES_DIR = LEGO_DIR / "images"
INVENTORY_FILE = LEGO_DIR / "inventory.json"
DEMO_FILE = ROOT / "apps" / "api" / "app" / "demo" / "data" / "lego.json"
BOX_URL = "https://images.brickset.com/sets/images/{number}-1.jpg"
ALT_URL = "https://images.brickset.com/sets/AdditionalImages/{number}-1/{number}_alt{index}.jpg"
MAX_ALTS = 3


def _numbers(path: Path) -> set[str]:
    """Every ``set_number`` in one of the two collections. A MOC has none."""
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["set_number"] for row in payload["sets"] if row["set_number"]}


def all_set_numbers() -> list[str]:
    return sorted(_numbers(DEMO_FILE) | _numbers(INVENTORY_FILE))


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
