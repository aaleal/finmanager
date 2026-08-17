"""Regenerate the extraction golden files.

    docker compose run --rm --no-deps api python -m tests.fixtures.regenerate_golden

**Pin the extraction, not the parse.** With the word boxes committed, a parser
change shows up as a diff in parsed output alone and an extractor upgrade as a
diff in these files — so the two failure modes can never masquerade as each other.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.receipts import extraction

FIXTURES = Path(__file__).parent / "receipts"
GOLDEN = Path(__file__).parent / "golden"

MIME_TYPES = {".pdf": "application/pdf", ".jpeg": "image/jpeg", ".jpg": "image/jpeg"}


def golden_for(path: Path) -> dict:
    data = path.read_bytes()
    result = extraction.extract(data, MIME_TYPES[path.suffix.lower()])
    return {
        "engine": result.engine,
        "document_kind": result.document_kind,
        "pages": [
            {
                "width": round(page.width, 2),
                "height": round(page.height, 2),
                "lines": [line.as_golden() for line in page.lines],
            }
            for page in result.pages
        ],
    }


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix.lower() not in MIME_TYPES:
            continue
        target = GOLDEN / f"{path.stem}.json"
        target.write_text(
            json.dumps(golden_for(path), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"wrote {target.name}")


if __name__ == "__main__":
    main()
