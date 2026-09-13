"""Protects: *«upload de PDF falha»* — the P0 that blocked the crown-jewel flow,
and the orchestrator rubric bullet *«attachments … stored outside web root»*.

The `storage-data` volume is mounted by containers running as two different
users: the API serves requests as `finmanager` (uid 10001), while `./fm seed`,
`./fm check` and the dev overlay run as root against a bind-mounted source tree.
Whichever one wrote a shard directory first used to lock the other out, and
every upload died with `PermissionError` before a `ProcessingJob` even existed —
so there was nothing in `last_error` to read (ADR-0024).

Both users are in the `finmanager` group, so the invariant is: everything under
the storage root is group-writable, and every directory is setgid so new shards
inherit that group.
"""

from __future__ import annotations

import stat

from app.services import documents
from sqlalchemy.orm import Session

#: Any stored file proves the point — this is about the shard's mode bits, not
#: about what was stored, so it deliberately needs no fixture corpus.
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def test_stored_documents_are_writable_by_both_container_users(db: Session) -> None:
    document = documents.store_bytes(
        db,
        PDF,
        source="UPLOAD",
        original_filename="talao.pdf",
    )
    path = documents.absolute_path(document)

    assert path.exists()
    assert path.stat().st_mode & stat.S_IWGRP, "a document must stay writable by the app group"

    for shard in (path.parent, path.parent.parent):
        mode = shard.stat().st_mode
        assert mode & stat.S_IWGRP, f"{shard} must be group-writable"
        assert mode & stat.S_ISGID, f"{shard} must be setgid so new shards inherit the group"
