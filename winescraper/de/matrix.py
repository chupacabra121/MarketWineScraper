"""One row per wine, one column per store — the brand × retailer price matrix.

The point of this shape is that it makes two different things visible at once:
what each store charges, and *where the same wine costs different money*. A
per-store ranking cannot show the second, because it lists each shop separately.
Here Grand Sud Merlot occupies one row and shows 3.33 at Lidl against 5.16 at
Combi — the identical 3-litre box, 55% apart.

That only works if the same wine can be recognised across shops, which is the
whole difficulty: no retailer publishes a barcode on its listing, and every one
writes the name its own way. "MAYBACH Grauer Burgunder 3-l-Bag-in-Box trocken,
Weißwein 2025" at Lidl, "Maybach Grauer Burgunder trocken 12,9 % vol 3 Liter Bag
in Box" at Netto and "Maybach Grauer Burgunder QbA, trocken, 2024, Bag-in-Box,
3,0l" at Schäpers are one product written three ways.

:func:`line_key` reduces a title to the three things that identify the wine and
survive rewording — the brand line, the grape (or failing that the colour), and
the container size. Anything else in a title is vintage, sweetness, ABV or
packaging wording, and all of those move between shops for the same wine.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from . import packaging as pkg
from .model import Listing

#: Brand lines seen on German bag-in-box. Matched longest-first so that
#: "chenin blanc wine box" is not read as the "wine box" of another producer.
LINES = (
    "cerro de la cruz", "chenin blanc wine box", "winzerglühwein", "vinho verde",
    "grand sud", "stony cape", "terra molino", "hauswein", "winebox", "altobello",
    "adventure", "biqueirao", "trevenezie", "cimarosa", "liebfraumilch",
    "bib tinto", "bib blanco", "vino tinto", "vino blanco", "vino rosado",
    "maybach", "mertes", "batuta", "miluna", "bree", "käfer", "kafer",
    "weiss & suss", "tres reyes", "almocreve",
)

#: Grape varieties, again longest-first: "sauvignon blanc" must not be split
#: into the "sauvignon" of a Cabernet Sauvignon.
GRAPES = (
    "cabernet sauvignon", "grauer burgunder", "weisser burgunder", "sauvignon blanc",
    "muller thurgau", "weissburgunder", "chenin blanc", "pinot grigio", "spatburgunder",
    "grauburgunder", "rotweincuvee", "tempranillo", "montepulciano", "primitivo",
    "chardonnay", "dornfelder", "pinot noir", "garganega", "riesling", "silvaner",
    "macabeo", "gutedel", "corvina", "shiraz", "merlot", "airen",
)


def fold(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", (text or "").lower()).replace("ß", "ss")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip()


def line_key(listing: Listing) -> tuple[str | None, str, float | None]:
    """(brand line, grape or colour, litres) — what identifies a wine across shops.

    Returns ``None`` for the line when no known brand is present, which is the
    signal not to merge the row with anything: an unbranded listing cannot be
    matched to another shop's unbranded listing on grape and size alone, since
    "3-litre Chardonnay" describes a dozen different wines.
    """
    folded = fold(listing.name)
    line = next((l for l in LINES if fold(l) in folded), None)
    grape = next((g for g in GRAPES if g in folded), None)
    return line, grape or (listing.colour or ""), listing.volume_l


@dataclass
class MatrixRow:
    """One wine, with a price for every store that sells it."""

    packaging_label: str
    #: Brand owner, or "Private label" where the shop owns it.
    brand: str
    product: str
    #: retailer label -> EUR per litre.
    prices: dict[str, float] = field(default_factory=dict)
    #: Ranking position where this wine placed, per store.
    ranks: dict[str, int] = field(default_factory=dict)
    private_label: bool | None = None

    @property
    def stores(self) -> int:
        return len(self.prices)

    @property
    def spread(self) -> float | None:
        """Dearest over cheapest, where more than one store sells it."""
        if len(self.prices) < 2:
            return None
        values = list(self.prices.values())
        return round(max(values) / min(values), 2)


#: German and Spanish company forms and trade words. Stripped so column two
#: reads as a name — "Peter Mertes", not "Weinkellerei Peter Mertes KG".
#:
#: Deliberately excludes "Adega" and "Cooperativa": they look like company
#: forms but they carry the name here, and removing them left the Portuguese
#: co-operative reading as "de Carvoeira".
_COMPANY_NOISE = re.compile(
    r"(&\s*Co\.?|\bGmbH\b|\bKG\b|\bAG\b|\bS\.?\s?L\.?\b|\bWeinkellerei\b"
    r"|\bWeinhandel\b|\bCantine\b|\bBodegas\b)", re.I)

#: A parenthetical in the evidence explains the verdict — "(Spanish producer
#: brand)" — and is prose, not part of the name.
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def _brand_label(listing: Listing, evidence) -> str:
    """Column two: the producer's name, or "Private label" when the shop owns it."""
    if evidence is None or evidence.private_label is None:
        return "not established"
    if evidence.private_label is True:
        return "Private label"
    owner = evidence.brand_owner
    # Some entries record an absence rather than an owner — Liebfraumilch is a
    # protected designation any producer may use, so it has no brand at all.
    if owner.lower().startswith("no brand"):
        return "no brand (designation)"
    owner = _COMPANY_NOISE.sub(" ", _PARENTHETICAL.sub("", owner).split(",")[0])
    # Fall back on the untouched name if the trimming ate it: a short result is
    # a sign the rules matched the name rather than the company form.
    trimmed = re.sub(r"\s+", " ", owner).strip(" &-.")
    return trimmed if len(trimmed) >= 4 else evidence.brand_owner.split(",")[0]


def build(ranked: list[tuple[str, Listing]], everything: list[Listing],
          language: str = "en") -> list[MatrixRow]:
    """Build the matrix from the ranked wines, priced across every store.

    ``ranked`` supplies the rows — the three cheapest boxes per store — and
    ``everything`` supplies the prices, so a wine that ranks at one shop still
    shows what the others charge for it even where it did not place there.
    """
    from . import brands

    by_line: dict[tuple, list[Listing]] = {}
    for listing in everything:
        if listing.packaging != pkg.BAG_IN_BOX or listing.price_per_litre is None:
            continue
        by_line.setdefault(line_key(listing), []).append(listing)

    rows: list[MatrixRow] = []
    seen: set[tuple] = set()
    for label, listing in ranked:
        key = line_key(listing)
        # Unbranded rows are never merged, so key them by their own identity.
        merge_key = key if key[0] else (id(listing),)
        if merge_key in seen:
            for row in rows:
                if row.product == listing.name:
                    row.ranks.setdefault(label, 0)
            continue
        seen.add(merge_key)

        evidence = brands.lookup(listing.retailer, listing.name)
        row = MatrixRow(
            packaging_label="BiB",
            brand=_brand_label(listing, evidence),
            product=listing.name,
            private_label=evidence.private_label if evidence else None,
        )
        matches = by_line.get(key, [listing]) if key[0] else [listing]
        for other in matches:
            price = other.price_per_litre
            # Cheapest wins where a shop lists the same wine twice — a vintage
            # changeover puts both on the shelf at once.
            if price is not None and price < row.prices.get(other.retailer_label, 1e9):
                row.prices[other.retailer_label] = price
        rows.append(row)

    # Widest-selling first, then cheapest: the rows that carry information about
    # more than one shop are the ones worth reading first.
    rows.sort(key=lambda r: (-r.stores, min(r.prices.values()) if r.prices else 0))
    return rows


def rank_key(listing: Listing) -> tuple:
    """Sort order for the cheapest-first ranking.

    Ties on price per litre are the normal case rather than the exception —
    Lidl prices three colours of its own-brand box identically, and Schäpers
    five — so the tie-break has to be deterministic or the ranking reshuffles
    between runs for no reason. Cheapest per litre first, then the smaller pack
    price, then the name.
    """
    return (listing.price_per_litre, listing.price or 0.0, listing.name)


def top_per_store(scope: list[Listing], per_store: int = 3
                  ) -> list[tuple[str, Listing]]:
    """The cheapest still-wine single boxes at each store, cheapest first.

    Shared by the workbook and the CSV export so the two cannot disagree about
    which wines the study is talking about.
    """
    boxes = [x for x in scope
             if x.packaging == pkg.BAG_IN_BOX and x.price_per_litre is not None]
    eligible = {id(x) for x in boxes
                if x.product_type == "still" and not x.is_pack}
    grouped: dict[str, list[Listing]] = {}
    for listing in boxes:
        grouped.setdefault(listing.retailer_label, []).append(listing)
    out: list[tuple[str, Listing]] = []
    for label, group in sorted(grouped.items()):
        ranked = sorted([x for x in group if id(x) in eligible], key=rank_key)
        out.extend((label, x) for x in ranked[:per_store])
    return out


def stores_in(scope: list[Listing]) -> list[str]:
    return sorted({x.retailer_label for x in scope
                   if x.packaging == pkg.BAG_IN_BOX})


def to_csv_rows(rows: list[MatrixRow], stores: list[str]) -> list[list]:
    """Flatten to the layout of the source spreadsheet: 0 where not sold."""
    out = [["", "", ""] + stores]
    for row in rows:
        out.append([row.packaging_label, row.brand, row.product]
                   + [row.prices.get(store, 0) for store in stores])
    return out
