"""Where the household's own replaceable files live (ADR-0062).

One manifest for every file a household may drop in and swap out: the product
catalogue, the taxonomy workbook, the *talões*, the LEGO inventory and its box
art. None of them is committed and none of them is required — a path that does
not exist means "nothing to load yet", never an error.

They sit under a mounted directory rather than inside the package on purpose:
replacing a catalogue with a newer export has to be dropping a file in, not
rebuilding the image. Reference data — the taxonomy JSON, the attribute
vocabulary — is the opposite kind of thing and stays in ``app/data`` (ADR-0029).
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

DEFAULTS_DIR: Path = settings.defaults_root

#: Built by ``dev/build-product-seed.py`` from the household's purchase history.
SUPERMARKET_PRODUCTS = DEFAULTS_DIR / "supermarket" / "products.xlsx"
#: The taxonomy the household edits by hand. Only the *source*: ``ensure_categories``
#: reads the shipped JSON, and ``dev/build-category-seed.py`` regenerates it from here.
SUPERMARKET_CATEGORIES = DEFAULTS_DIR / "supermarket" / "categories.xlsx"
#: The real *talões* (ADR-0027), ingested through the ordinary upload path.
SUPERMARKET_INVOICES = DEFAULTS_DIR / "supermarket" / "invoices"

#: The collection, converted from the household's spreadsheet. The live path for
#: replacing it is the "Importar em lote" dialog (ADR-0048); this is what a fresh
#: install loads before anyone has opened that dialog.
LEGO_INVENTORY = DEFAULTS_DIR / "lego" / "inventory.json"
#: Box shot + gallery per set number, fetched once by ``dev/download-lego-images.py``.
LEGO_IMAGES = DEFAULTS_DIR / "lego" / "images"
