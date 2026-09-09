"""Local category classification over the household's own pt-PT L3 vocabulary.

Fed by the product description **and** the ``merchant_section`` heading the line
sat under. All four merchants group their lines under headings — ``Mercearia
Salgada``, ``FRUTAS E VEGETAIS``, ``--TUBERCULOS--`` — so that heading is a strong
prior on a brand-new product at no extra cost (Decision #27).

This is the local engine and it ships enabled. A remote classifier may be
registered behind the same call without touching anything that uses it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.core import Category
from app.services.supermarket.normalize import normalize_description

GROCERY = "GROCERY"
AUTO_ASSIGN = Decimal("0.70")


@dataclass(slots=True)
class Classification:
    category_id: uuid.UUID | None
    score: Decimal
    reasons: list[dict[str, Any]]


class CategoryClassifier(Protocol):
    name: str

    def classify(
        self, db: DbSession, *, description: str, merchant_section: str | None
    ) -> Classification: ...


class VocabularyClassifier:
    """Similarity against the display names of the GROCERY tree, deepest first."""

    name = "vocabulary"

    def classify(
        self, db: DbSession, *, description: str, merchant_section: str | None
    ) -> Classification:
        rows = db.execute(
            select(Category.id, Category.display_name_pt, Category.level).where(
                Category.domain == GROCERY, Category.is_deleted.is_(False), Category.level > 1
            )
        ).all()
        if not rows:
            return Classification(
                None,
                Decimal("0.000"),
                [{"rule": "no_taxonomy", "detail": "Árvore de categorias vazia.", "score": None}],
            )

        needle = normalize_description(description)
        section = normalize_description(merchant_section or "")

        best_id: uuid.UUID | None = None
        best_score = 0.0
        for category_id, display_name, level in rows:
            name = normalize_description(display_name)
            candidate = fuzz.token_set_ratio(needle, name) / 100
            if section:
                # The heading corroborates; it never decides on its own.
                candidate = max(
                    candidate,
                    0.65 * candidate + 0.35 * (fuzz.token_set_ratio(section, name) / 100),
                )
            # A deeper node is a more useful answer when the evidence is equal.
            candidate += 0.02 if level == 3 else 0.0
            if candidate > best_score:
                best_id, best_score = category_id, candidate

        score = Decimal(str(round(min(best_score, 1.0), 3)))
        if best_id is None or score < AUTO_ASSIGN:
            return Classification(
                None,
                score,
                [
                    {
                        "rule": "category_unresolved",
                        "detail": "Nenhuma categoria suficientemente próxima; fica por atribuir.",
                        "score": str(score),
                    }
                ],
            )
        return Classification(
            best_id,
            score,
            [
                {
                    "rule": "category_auto",
                    "detail": f"Sugerida pelo vocabulário local ({self.name}).",
                    "score": str(score),
                }
            ],
        )


_classifier: CategoryClassifier = VocabularyClassifier()


def get_classifier() -> CategoryClassifier:
    return _classifier


def register_classifier(classifier: CategoryClassifier) -> None:
    global _classifier
    _classifier = classifier
