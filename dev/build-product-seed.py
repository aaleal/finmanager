#!/usr/bin/env python
"""Build the product seed workbook from five years of purchase lines.

The year sheets (2021-2026) of `GestaoCasa_03.supermercado_v16.xlsx` are the raw
truth: one row per article bought. Everything here is extrapolated from them.

That workbook's `Produtos` / `Produtos 2` sheets were themselves generated from
those same year sheets, so they are not a second source. They are used for the
one thing they really add: the household's own **alias -> canonical name**
curation, plus the brand it managed to separate from the shop.

Categories resolve against the *current* taxonomy (`categorias-<date>.xlsx`,
sheet `Categorias`), not the one the old sheet used. Matching is on the deepest
name that exists and then **adopts that taxonomy's own parentage**, so a genre
that moved to a different L1 follows it instead of being dropped.

Output is shaped like the bulk product import
(`products_service._PRODUCT_HEADER_ALIASES`). Columns the importer does not know
are ignored by it, so the extra evidence columns cost nothing.

    podman cp <workbook>  finmanager_api_1:/tmp/gc.xlsx
    podman cp <taxonomy>  finmanager_api_1:/tmp/cats.xlsx
    podman cp dev/build-product-seed.py finmanager_api_1:/tmp/build.py
    podman exec -e PYTHONPATH=/app finmanager_api_1 \
        python /tmp/build.py /tmp/gc.xlsx /tmp/cats.xlsx /tmp/produtos-seed.xlsx

Nothing here touches the database.
"""

from __future__ import annotations

import re
import sys
import warnings
from collections import Counter
from decimal import Decimal
from typing import Any

warnings.filterwarnings("ignore")

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from rapidfuzz import fuzz, process

from app.core.errors import ValidationError
from app.services.supermarket import attributes
from app.services.supermarket.catalogue import _combined
from app.services.supermarket.normalize import (
    _MULTIPACK,
    _NOISE_WORDS,
    _SIZE_TOKEN,
    extract_pack_weight_kg,
    normalize_description,
    strip_accents,
)
from app.services.supermarket.products_service import round_to_the_gram

YEAR_SHEETS = ("2021", "2022", "2023", "2024", "2025", "2026")
#: Every year sheet buries its header under a four-row banner of statistics.
YEAR_HEADER_ROW = 4

#: Retailer own-label brands. A bare shop name means "bought here", not "made
#: for here", so only these justify `is_own_brand`.
OWN_LABELS = {
    "CONTINENTE",
    "CONTINENTE EQUILIBRIO",
    "CONTINENTE SELECAO",
    "PINGO DOCE",
    "AUCHAN",
    "DIA",
    "HACENDADO",
    "DELIPLUS",
    "BOSQUE VERDE",
    "MILBONA",
    "FREEWAY",
    "CRIVIT",
    "WELLS",
}

#: Placeholders the sheet uses for "not filed yet". They are not categories.
CATEGORY_JUNK = {"", "A", "NA", "N A", "NAO REPORTADO", "NAO REPORTADA", "OUTROS", "MISC", "-"}

#: The current taxonomy is a restructure, not a respelling: whole L1s were
#: merged and renamed. Fuzzy matching cannot be trusted to guess these, so the
#: renames that changed meaning are declared. Keyed by `ckey`.
L1_RENAMES = {
    "LATICINIOS": "Laticínios & Ovos",
    "PEIXARIA": "Peixaria & Marisco",
    "SAUDE HIGIENE": "Higiene & Beleza",
    "CHARCUTARIA": "Charcutaria & Queijos",
    "CHOCOLATES OUTROS": "Chocolates",
    "CASA LIMPEZA": "Limpeza & Manutenção",
    "BOLACHAS": "Bolachas & Biscoitos",
    "BRINQUEDOS": "Brinquedos & Hobbies",
    "REFEICOES": "Refeições Prontas",
    "ESCRITORIO ESCOLA": "Escola & Escritório",
    "ENLATADOS": "Mercearia",
    "PASTILHAS": "Doces & Guloseimas",
    "GYM": "Mercearia",
    "MISC": "Outros",
    "N A": "Outros",
    "NAO REPORTADO": "Outros",
}

#: Above this a fuzzy category match is taken; the app's own classifier uses the
#: same scorer at 0.70, but it has a merchant section to corroborate with and
#: this has nothing, so the bar is higher.
CATEGORY_MATCH = 0.86

#: Inside a settled L1 there are only a few dozen candidates, so the bar drops to
#: where the app's classifier puts it when a merchant section corroborates.
SCOPED_MATCH = 0.72

#: Sold loose and weighed at the till, so a "pack format" would be invented.
WEIGHED_L1 = {"FRUTA LEGUMES", "TALHO", "PEIXARIA"}

CONSERVATION_BY_L1 = {
    "GELADOS": "CONGELADO",
    "LATICINIOS": "REFRIGERADO",
    "CHARCUTARIA": "REFRIGERADO",
    "TALHO": "REFRIGERADO",
    "PEIXARIA": "REFRIGERADO",
    "FRUTA LEGUMES": "REFRIGERADO",
    "MERCEARIA": "AMBIENTE",
    "ENLATADOS": "AMBIENTE",
    "BOLACHAS": "AMBIENTE",
    "APERITIVOS": "AMBIENTE",
    "PASTILHAS": "AMBIENTE",
}

#: Longest first, so «ultracongelado» is not read as «congelado».
CONSERVATION_WORDS = {
    "ULTRACONGELAD": "CONGELADO",
    "CONGELAD": "CONGELADO",
    "REFRIGERAD": "REFRIGERADO",
    "FRESCO": "REFRIGERADO",
    "FRESCA": "REFRIGERADO",
}

PRESENTATION_WORDS = {
    "LAMINAD": "Laminado",
    "PALITAD": "Palitado",
    "PALITO": "Palitado",
    "RALAD": "Ralado",
    "FATIAD": "Fatiado",
    "FATIAS": "Fatiado",
    "PICAD": "Picado",
    "CUBOS": "Em cubos",
    "TIRAS": "Em tiras",
    "BIFE": "Bife",
    "POSTA": "Posta",
    "FILETE": "Filete",
    "LOMBO": "Lombo",
    "INTEIR": "Inteiro",
    "MOID": "Moído",
    "GRANEL": "Granel",
    "COXA": "Perna",
    "PERNA": "Perna",
    "PEITO": "Peito",
}

DIETARY_WORDS = {
    "BIOLOGIC": "Bio",
    " BIO ": "Bio",
    "VEGAN": "Vegan",
    "VEGETARIAN": "Vegetariano",
    "SEM GLUTEN": "Sem glúten",
    "S/ GLUTEN": "Sem glúten",
    "SEM LACTOSE": "Sem lactose",
    "S/ LACTOSE": "Sem lactose",
    "SEM ACUCAR": "Sem açúcar",
    "S/ ACUCAR": "Sem açúcar",
    "0% ACUCAR": "Sem açúcar",
    "PROTEIC": "Alto teor proteico",
    "PROTEIN": "Alto teor proteico",
    "INTEGRAL": "Integral",
    "LIGHT": "Light",
    "SEM ALCOOL": "Sem álcool",
    "S/ ALCOOL": "Sem álcool",
}

LOWER_WORDS = {"de", "do", "da", "dos", "das", "e", "com", "sem", "em", "no", "na", "a", "o"}


# --- Small helpers -------------------------------------------------------------


def key(value: Any) -> str:
    return strip_accents(str(value or "")).upper().strip()


def ckey(value: Any) -> str:
    """Names through the catalogue's own funnel, so «Pequeno Almoco» and
    «Pequeno-Almoço» stop being two different categories."""
    return normalize_description(str(value or ""))


def clean(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def split_multi(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    return [part.strip() for part in re.split(r"[;|]", str(value)) if part.strip()]


def display_name(raw: str) -> str:
    """A till line turned into something a human would call the product.

    Size tokens go (they are formats, not identity), the merchant's own-brand
    noise goes (`PD`, `CNT`…), and the SHOUTING becomes Title Case.
    """
    text = _MULTIPACK.sub(" ", str(raw))
    text = _SIZE_TOKEN.sub(" ", text)
    text = re.sub(r"[^\w\s%&.-]", " ", text, flags=re.UNICODE)
    words = [w for w in re.split(r"\s+", text) if w and key(w) not in _NOISE_WORDS]
    out: list[str] = []
    for i, word in enumerate(words):
        low = word.lower()
        out.append(low if i and low in LOWER_WORDS else low.capitalize())
    return re.sub(r"\s+", " ", " ".join(out)).strip(" .-")


def read_sheet(wb: Any, sheet: str, header_row: int) -> list[dict[str, Any]]:
    ws = wb[sheet]
    it = ws.iter_rows(values_only=True)
    for _ in range(header_row):
        next(it, None)
    header = [clean(c) for c in (next(it, None) or ())]
    index = {name: i for i, name in enumerate(header) if name}
    rows = []
    for raw in it:
        if not raw or all(v in (None, "") for v in raw):
            continue
        rows.append({name: (raw[i] if i < len(raw) else None) for name, i in index.items()})
    return rows


# --- Taxonomy ------------------------------------------------------------------


class Taxonomy:
    """The current tree, resolved the way the app's own classifier resolves.

    A genre keeps the parentage the *taxonomy* gives it, not the one the old
    sheet remembers — which is the whole reason to re-resolve against it. Exact
    names do most of the work; the rest is fuzzy, because the current tree is a
    restructure of the old one and the two rarely spell a genre the same way.
    """

    def __init__(self, rows: list[tuple[str, str, str]]) -> None:
        self.by_l3: dict[str, tuple[str, ...]] = {}
        self.by_l2: dict[str, tuple[str, ...]] = {}
        self.by_l1: dict[str, tuple[str, ...]] = {}
        self.ambiguous: Counter[str] = Counter()
        #: Leaves and branches indexed *under their L1*, which is what lets the
        #: deep search run at a lower threshold without wandering off-tree.
        self.scoped: dict[str, dict[str, list[tuple[str, tuple[str, ...]]]]] = {}
        for l1, l2, l3 in rows:
            if not l1:
                continue
            self.by_l1.setdefault(ckey(l1), (l1,))
            bucket = self.scoped.setdefault(ckey(l1), {"l2": [], "l3": []})
            if l2:
                self.by_l2.setdefault(ckey(l2), (l1, l2))
                if (ckey(l2), (l1, l2)) not in bucket["l2"]:
                    bucket["l2"].append((ckey(l2), (l1, l2)))
            if l2 and l3:
                token = ckey(l3)
                existing = self.by_l3.get(token)
                if existing is not None and existing != (l1, l2, l3):
                    self.ambiguous[l3] += 1
                self.by_l3.setdefault(token, (l1, l2, l3))
                bucket["l3"].append((token, (l1, l2, l3)))
        self._keys = {"l3": list(self.by_l3), "l2": list(self.by_l2), "l1": list(self.by_l1)}

    def _table(self, level: str) -> dict[str, tuple[str, ...]]:
        return {"l1": self.by_l1, "l2": self.by_l2, "l3": self.by_l3}[level]

    def _near(self, level: str, value: Any) -> tuple[str, ...] | None:
        token = ckey(value)
        if not token or token in CATEGORY_JUNK:
            return None
        table = self._table(level)
        hit = table.get(token)
        if hit:
            return hit
        # Shortlist fast, then re-rank with the scorer the catalogue uses, which
        # notices the words a bare `token_set_ratio` would forgive.
        shortlist = process.extract(token, self._keys[level], scorer=fuzz.token_set_ratio, limit=8)
        if not shortlist:
            return None
        name, score = max(
            ((cand, _combined(token, cand)) for cand, _, _ in shortlist), key=lambda p: p[1]
        )
        return table[name] if score / 100 >= CATEGORY_MATCH else None

    def _deepen(self, l1_key: str, level: str, queries: list[str]) -> tuple[str, ...] | None:
        """Best node of `level` *inside* one L1.

        Scoped, so the bar can sit where the app's own classifier puts it: the L1
        plays the part the merchant's section heading plays there, corroborating
        a match that would be reckless on the open tree.
        """
        bucket = self.scoped.get(l1_key, {}).get(level, [])
        if not bucket:
            return None
        best: tuple[float, tuple[str, ...]] | None = None
        for query in queries:
            token = ckey(query)
            if not token or token in CATEGORY_JUNK:
                continue
            for name, path in bucket:
                score = _combined(token, name) / 100
                if best is None or score > best[0]:
                    best = (score, path)
        return best[1] if best and best[0] >= SCOPED_MATCH else None

    def resolve(self, product: str, l1: Any, l2: Any, l3: Any) -> tuple[tuple[str, ...], str]:
        """Settle the L1 first, then go as deep as the evidence allows inside it.

        Trying to name a leaf on the open tree is what the strict threshold was
        guarding against; once the L1 is fixed there are only a few dozen
        candidates and the old label, the old subcategory and the product's own
        name can all vote.
        """
        renamed = L1_RENAMES.get(ckey(l1))
        root = (
            self.by_l1.get(ckey(renamed))
            if renamed
            else (self._near("l1", l1) or self._near("l1", l2))
        )
        if root is None:
            # No L1 to scope by: only an outright name match is trustworthy.
            for value, label in ((l3, "l3"), (product, "l3_by_name"), (l2, "l2")):
                level = "l2" if label == "l2" else "l3"
                if (hit := self._near(level, value)) is not None:
                    return hit, label
            return (), "none"

        l1_key = ckey(root[0])
        # The old label was assigned by a human and outranks the product's own
        # name, which is only a guess: trusting the name first is what files a
        # tin of varnish under «Material Elétrico».
        for queries, kind in (([l3, l2], "l3"), ([product], "l3_by_name")):
            if (hit := self._deepen(l1_key, "l3", [q for q in queries if q])) is not None:
                return hit, kind
        if (hit := self._deepen(l1_key, "l2", [q for q in (l3, l2, product) if q])) is not None:
            return hit, "l2"
        return root, "l1"


def load_taxonomy(path: str) -> Taxonomy:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = [
        (
            clean(row.get("Nível 1")) or "",
            clean(row.get("Nível 2")) or "",
            clean(row.get("Nível 3")) or "",
        )
        for row in read_sheet(wb, "Categorias", 0)
    ]
    return Taxonomy(rows)


# --- Derivation ----------------------------------------------------------------


def derive_conservation(name: str, l1: str | None) -> str | None:
    haystack = key(name)
    for word, value in sorted(CONSERVATION_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in haystack:
            return value
    return CONSERVATION_BY_L1.get(ckey(l1)) if l1 else None


def derive_presentation(name: str) -> str | None:
    haystack = key(name)
    for word, value in sorted(PRESENTATION_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in haystack:
            return value
    return None


def derive_dietary(name: str) -> list[str]:
    haystack = f" {key(name)} "
    return sorted({value for word, value in DIETARY_WORDS.items() if word in haystack})




#: A grocery pack above this is, in this basket, almost always something else
#: wearing a number: a count of eggs, or a bin bag's capacity in litres. The
#: occasional real 10 kg detergent is a cheaper loss than a poisoned €/kg.
MAX_PACK_KG = Decimal("5")

#: Tokens `_SIZE_TOKEN` accepts that count things instead of measuring them.
COUNT_UNITS = {"UN", "UNI", "UND"}


def printed_mass(description: str) -> bool:
    """Whether the till printed a *mass or volume*, rather than a count.

    `_SIZE_TOKEN` accepts `UN` alongside `KG` and `ML`, so «OVOS CLASSE M 6UN»
    looks like it carries a size when what it carries is a quantity.
    """
    if _MULTIPACK.search(description):
        return True
    return any(
        match.group(2).upper() not in COUNT_UNITS for match in _SIZE_TOKEN.finditer(description)
    )


def plausible_weight(peso: Any, description: str) -> Decimal | None:
    """The `Peso` column holds a *count* for counted goods.

    Eggs are the giveaway: 6, 12 and 18 are dozens, not kilograms, and taken
    literally they make a box of eggs the heaviest thing in the catalogue. A bare
    integer with no mass printed anywhere is read as a count and dropped.
    """
    weight = round_to_the_gram(peso)
    if weight is None or weight > MAX_PACK_KG:
        return None
    if not printed_mass(description) and weight >= 4 and weight == weight.to_integral_value():
        return None
    return weight


def main(source: str, taxonomy_path: str, target: str) -> None:
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    taxonomy = load_taxonomy(taxonomy_path)

    year_rows = {
        sheet: read_sheet(wb, sheet, YEAR_HEADER_ROW)
        for sheet in YEAR_SHEETS
        if sheet in wb.sheetnames
    }

    # Anything that ever appears as a `Supermercado` is a place, not a brand.
    retailers = {
        key(clean(row.get("Supermercado")))
        for rows in year_rows.values()
        for row in rows
        if clean(row.get("Supermercado"))
    }

    def real_brand(raw: Any) -> str | None:
        """The sheet conflates brand and shop in one column
        (`Marca / Supermercado`), and a cell often lists several.

        A brand is only taken when the cell names exactly one non-retailer: a
        cell reading `Aldi; Continente; ISDIN` is a list of shops with one stray
        entry, not evidence that the yogurt is made by ISDIN. Brand is half of
        the identity key, so a wrong one is worse than none.
        """
        candidates = {c for c in split_multi(raw) if key(c) not in retailers}
        if len(candidates) != 1:
            return None
        return next(iter(candidates))

    # --- Pass 1: the household's own alias -> canonical name curation ---------
    canonical: dict[str, str] = {}
    brand_of: dict[str, str] = {}

    def learn(alias: Any, name: str, brand: str | None) -> None:
        token = normalize_description(str(alias or ""))
        if not token:
            return
        canonical.setdefault(token, name)
        if brand:
            brand_of.setdefault(token, brand)

    for sheet, hdr, name_col, alias_col, brand_col in (
        ("Produtos 2", 1, "Name", "Alias", "Brand"),
        ("Produtos", 3, "Produto standard", "Descrições originais", "Marca / Supermercado"),
    ):
        if sheet not in wb.sheetnames:
            continue
        for row in read_sheet(wb, sheet, hdr):
            name = clean(row.get(name_col))
            if not name:
                continue
            pretty = display_name(name) or name
            brand = real_brand(row.get(brand_col))
            learn(name, pretty, brand)
            for alias in split_multi(row.get(alias_col)):
                learn(alias, pretty, brand)

    # --- Pass 2: every purchase line, which is what we extrapolate from -------
    products: dict[str, dict[str, Any]] = {}
    lines_read = 0
    named_by_curation = 0

    for sheet, rows in year_rows.items():
        for row in rows:
            description = clean(row.get("Descrição"))
            if not description:
                continue
            lines_read += 1
            token = normalize_description(description)
            curated = canonical.get(token)
            name = curated or display_name(description)
            if not name:
                continue
            named_by_curation += int(bool(curated))

            entry = products.setdefault(
                normalize_description(name),
                {
                    "name": name,
                    "brands": Counter(),
                    "cats": Counter(),
                    "weights": Counter(),
                    "shops": Counter(),
                    "years": set(),
                    "lines": 0,
                    "spend": Decimal("0"),
                },
            )
            entry["lines"] += 1
            entry["years"].add(sheet)

            brand = brand_of.get(token)
            if brand:
                entry["brands"][brand] += 1
            shop = clean(row.get("Supermercado"))
            if shop:
                entry["shops"][shop] += 1

            cats = (
                clean(row.get("Categoria")),
                clean(row.get("Categoria_2")),
                clean(row.get("Categoria_3")),
            )
            if any(cats):
                entry["cats"][cats] += 1

            # The till prints the pack size inside the description; the `Peso`
            # column is what the household measured. Both funnel to the gram.
            weight = plausible_weight(row.get("Peso"), description) or round_to_the_gram(
                extract_pack_weight_kg(description)
            )
            if weight is not None and weight <= MAX_PACK_KG:
                entry["weights"][weight] += 1

            try:
                entry["spend"] += Decimal(str(row.get("Price_Final") or row.get("Price") or 0))
            except (ArithmeticError, ValueError, TypeError):
                pass

    # --- Emit -----------------------------------------------------------------
    report: Counter[str] = Counter()
    unmatched: Counter[str] = Counter()
    out: list[dict[str, Any]] = []

    for entry in products.values():
        name = entry["name"]
        cats = entry["cats"].most_common(1)[0][0] if entry["cats"] else (None, None, None)
        path, depth = taxonomy.resolve(name, *cats)
        if depth == "none":
            deepest = next((c for c in reversed(cats) if c and ckey(c) not in CATEGORY_JUNK), None)
            if deepest:
                unmatched[deepest] += entry["lines"]

        l1 = path[0] if path else None
        weights = set(entry["weights"])
        sold_by_weight = ckey(l1) in WEIGHED_L1 if l1 else False
        # A weighed item's purchase weights are measurements, not pack formats.
        formats = [] if sold_by_weight else sorted(weights)[:8]

        brand = entry["brands"].most_common(1)[0] if entry["brands"] else None
        # One brand, and it has to account for most of the purchases. Anything
        # less is the sheet's brand/shop conflation leaking through.
        brand = (
            brand[0]
            if brand and len(entry["brands"]) == 1 and brand[1] >= entry["lines"] * 0.6
            else None
        )
        try:
            conservation = attributes.sanitize_conservation(derive_conservation(name, l1))
            presentation = attributes.sanitize_presentation(derive_presentation(name))
            dietary = attributes.sanitize_dietary(derive_dietary(name))
        except ValidationError as exc:  # a derivation rule drifted from the vocabulary
            raise SystemExit(f"derivation produced an unknown value for «{name}»: {exc}") from exc

        report[f"category_{depth}"] += 1
        report["sold_by_weight"] += int(sold_by_weight)
        report["with_brand"] += int(bool(brand))
        report["with_formats"] += int(bool(formats))
        report["with_conservation"] += int(bool(conservation))
        report["with_presentation"] += int(bool(presentation))
        report["with_dietary"] += int(bool(dietary))

        out.append(
            {
                "Nome": name,
                "Marca": brand or "",
                # One level per column: the importer reads `Cat1/Cat2/Cat3` just
                # as happily as a joined path, and a single `L1 › L2 › L3` cell
                # is miserable to correct by hand in Excel.
                "Cat1": path[0] if len(path) > 0 else "",
                "Cat2": path[1] if len(path) > 1 else "",
                "Cat3": path[2] if len(path) > 2 else "",
                "Vendido a peso": "Sim" if sold_by_weight else "",
                "Formatos": "; ".join(str(w) for w in formats),
                "Marca branca": "Sim" if brand and key(brand) in OWN_LABELS else "",
                "Conservação": conservation or "",
                "Corte": presentation or "",
                "Tags": "; ".join(dietary),
                # Evidence, ignored by the importer: it matches columns by name.
                "Compras": entry["lines"],
                "Anos": ", ".join(sorted(entry["years"])),
                "Lojas": ", ".join(s for s, _ in entry["shops"].most_common(3)),
                "Gasto total": float(round(entry["spend"], 2)),
            }
        )

    out.sort(key=lambda row: (-row["Compras"], row["Nome"]))

    book = Workbook()
    sheet = book.active
    sheet.title = "Produtos"
    headers = list(out[0].keys())
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row in out:
        sheet.append([row[h] for h in headers])
    sheet.freeze_panes = "A2"
    for i, header in enumerate(headers, start=1):
        width = max(len(header), *(len(str(r[header])) for r in out)) + 2
        sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = min(width, 46)

    # The importer only ever reads the first worksheet, so this is free context:
    # the shopping list for extending the taxonomy.
    gaps = book.create_sheet("Categorias em falta")
    gaps.append(["Nome na folha", "Linhas afetadas"])
    for cell in gaps[1]:
        cell.font = Font(bold=True)
    for name, count in unmatched.most_common():
        gaps.append([name, count])
    gaps.freeze_panes = "A2"
    gaps.column_dimensions["A"].width = 40

    book.save(target)

    total = len(out)
    print(f"{lines_read} purchase lines -> {total} products -> {target}")
    print(f"taxonomy: {len(taxonomy.by_l1)} L1, {len(taxonomy.by_l2)} L2, {len(taxonomy.by_l3)} L3")
    if taxonomy.ambiguous:
        print(f"  ambiguous L3 names (first parent wins): {len(taxonomy.ambiguous)}")
    print(f"  lines named by the household's curation: {100 * named_by_curation / lines_read:.1f}%")
    for label in (
        "category_l3",
        "category_l3_by_name",
        "category_l2",
        "category_l1",
        "category_none",
        "with_brand",
        "sold_by_weight",
        "with_formats",
        "with_conservation",
        "with_presentation",
        "with_dietary",
    ):
        n = report[label]
        print(f"  {label:20s} {n:5d}  {100 * n / total:5.1f}%")
    print(f"  taxonomy gaps: {len(unmatched)} names, {sum(unmatched.values())} lines")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
