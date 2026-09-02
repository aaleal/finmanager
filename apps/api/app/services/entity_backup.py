"""Round-trip backup of a household's entities.

Nothing else in the backup registry can normalise an import until the
entities it attributes rows to already exist under the same names — LEGO's
own archive (``lego_backup.py``) resolves a model's or instance's owning
entity *by name*, and refuses a name it does not recognise rather than
guessing (ADR-0007). This module is the other half of that: it lets a
household's entities be exported and re-created, by name, on a fresh
installation, so every other module's archive then resolves cleanly.

Only ``name`` and ``color`` travel as data to be recreated. ``member_ids``
points at users, and a fresh installation has none of the source's — instead
each exported entity carries its members' ``display_name``/``email`` as a
**read-only reference**, so whoever restores the archive knows who to invite.
No ``User`` and no password is ever created by a restore: the one-shot
``POST /setup`` and an OWNER's own ``POST /household/members`` (with its
``temporary_password``) are the only two places an account is ever created
(ADR-0011, ADR-0014) — a restore only requires `Writer`, so letting it create
accounts would let a MEMBER grant themselves or anyone else a login. An
entity whose name already exists in the target household is matched, not
renamed or merged, the same rule every other module's restore already
follows.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import uuid
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core import audit
from app.core.errors import ValidationError
from app.models.household import Entity, User
from app.schemas.household import EntityBackupReport

FORMAT = "finmanager.entities.backup"
VERSION = 1

MANIFEST_NAME = "manifest.json"
COLLECTION_NAME = "entities.json"

#: Guards against a zip bomb: the archive is trusted no more than any upload.
_MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024


def build_archive(db: DbSession, entity_ids: list[uuid.UUID]) -> bytes:
    """Every named entity in the caller's household, as one small zip."""
    rows = list(
        db.scalars(select(Entity).where(Entity.id.in_(entity_ids), Entity.is_deleted.is_(False)))
    )
    member_ids = {member_id for row in rows for member_id in row.member_ids}
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(member_ids)))}
    entities = [
        {
            "name": row.name,
            "color": row.color,
            # Reference only, for whoever restores this to know who to invite
            # (POST /household/members) — never recreated automatically.
            "members": [
                {"display_name": users[member_id].display_name, "email": users[member_id].email}
                for member_id in row.member_ids
                if member_id in users
            ],
        }
        for row in rows
    ]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            COLLECTION_NAME, json.dumps({"entities": entities}, ensure_ascii=False, indent=1)
        )
        archive.writestr(
            MANIFEST_NAME,
            json.dumps(
                {
                    "format": FORMAT,
                    "version": VERSION,
                    "exported_at": dt.datetime.now(dt.UTC).isoformat(),
                    "counts": {"entities": len(entities)},
                },
                ensure_ascii=False,
                indent=1,
            ),
        )
    return buffer.getvalue()


def filename(exported_on: dt.date | None = None) -> str:
    return f"entidades-finmanager-{exported_on or dt.date.today():%Y%m%d}.zip"


def restore_archive(
    db: DbSession,
    payload: bytes,
    *,
    entity_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
) -> EntityBackupReport:
    """Recreate every entity from the archive that this household does not
    already have, by name. ``entity_id`` only locates the target household —
    an entity being restored is not attributed to another entity."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValidationError("O ficheiro não é um arquivo zip válido.") from exc

    with archive:
        if sum(info.file_size for info in archive.infolist()) > _MAX_UNCOMPRESSED_BYTES:
            raise ValidationError("Arquivo demasiado grande.")

        try:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        except KeyError as exc:
            raise ValidationError(f"O arquivo não contém {MANIFEST_NAME}.") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{MANIFEST_NAME} não é JSON válido.") from exc

        if manifest.get("format") != FORMAT:
            raise ValidationError("Este arquivo não é uma cópia de segurança de entidades.")
        if int(manifest.get("version", 0)) > VERSION:
            raise ValidationError("O arquivo foi criado por uma versão mais recente da aplicação.")

        target_entity = db.get(Entity, entity_id)
        if target_entity is None:
            raise ValidationError("Entidade de destino não encontrada.")
        household_id = target_entity.household_id

        try:
            collection = json.loads(archive.read(COLLECTION_NAME))
        except KeyError as exc:
            raise ValidationError(f"O arquivo não contém {COLLECTION_NAME}.") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{COLLECTION_NAME} não é JSON válido.") from exc

        existing = set(
            db.scalars(
                select(Entity.name).where(
                    Entity.household_id == household_id, Entity.is_deleted.is_(False)
                )
            ).all()
        )

        report = EntityBackupReport()
        for row in collection.get("entities", []):
            name = str(row.get("name") or "").strip()
            if not name or name in existing:
                report.skipped_entities += 1
                continue
            entity = Entity(
                household_id=household_id,
                name=name,
                member_ids=[],
                color=row.get("color"),
            )
            db.add(entity)
            db.flush()
            audit.record(
                db,
                action="CREATE",
                table_name="entities",
                record_id=entity.id,
                entity_id=entity.id,
                actor_user_id=actor_user_id,
                after=audit.snapshot(entity),
            )
            existing.add(name)
            report.entities += 1

    return report
