"""The real *talões* the parser suite runs against.

Private since ADR-0062 — they are the household's own purchases, so they are
mounted, not committed. A clone that is not this household's has nothing to run
these tests against, which is a skip rather than a failure: the parsers are
still exercised by the golden files, and the assertions here are measurements of
specific receipts nobody else has.
"""

from __future__ import annotations

import pytest
from app.services.supermarket.defaults import INVOICES_DIR

RECEIPTS = INVOICES_DIR

requires_receipts = pytest.mark.skipif(
    not RECEIPTS.is_dir() or not any(RECEIPTS.iterdir()),
    reason=f"Sem talões reais em {RECEIPTS} (privados, ADR-0062).",
)
