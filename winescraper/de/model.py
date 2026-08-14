"""One German wine listing, as collected.

Kept separate from :class:`winescraper.models.WineProduct` rather than extending
it. That model carries Romanian vocabulary in its values (``colour`` is
``alb``/``rosu``, the deposit field means SGR) and none of what this study turns
on: which container the wine is in, and what the Pfand on that container is.
Bending it to hold both would leave every field ambiguous about which market it
described.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import packaging as pkg


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Listing:
    """One wine, at one German retailer, at one point in time."""

    # --- identity ---------------------------------------------------------
    retailer: str
    retailer_label: str
    channel: str                     # discounter | supermarkt | fachhandel | c&c
    external_id: str
    name: str
    url: str | None = None
    #: The four-way trade format German retail is reported in — cash & carry,
    #: hypermarket, discounter, supermarket/convenience — plus "specialist" for
    #: the wine shops those four do not cover. Declared here rather than beside
    #: ``channel`` because it carries a default and the fields above do not.
    trade_format: str = "specialist"

    # --- commercial -------------------------------------------------------
    price: float | None = None       # shelf price as published, EUR
    currency: str = "EUR"
    list_price: float | None = None  # pre-discount price where advertised
    unit_price: float | None = None  # EUR/litre as the retailer advertises it
    on_promotion: bool = False
    in_stock: bool | None = None
    price_basis: str = "gross"       # gross = VAT included; net = ex-VAT (B2B)

    # --- packaging: what this study is about ------------------------------
    packaging: str = pkg.UNKNOWN
    packaging_evidence: str = ""     # which words in the listing decided it
    volume_l: float | None = None
    pack_count: int = 1

    # --- wine attributes --------------------------------------------------
    #: still | sparkling | gluehwein | sangria | schorle | dessert. Kept because
    #: a bag-in-box aisle mixes drinks that are not priced on the same scale —
    #: Glühwein runs at a third of the litre price of the wine beside it.
    product_type: str = "still"
    brand: str | None = None
    colour: str | None = None        # rot | weiss | rose
    sweetness: str | None = None     # trocken | halbtrocken | lieblich | suess
    abv: float | None = None
    vintage: int | None = None
    country: str | None = None
    region: str | None = None
    grape_varieties: list[str] = field(default_factory=list)

    # --- provenance -------------------------------------------------------
    category_path: str | None = None
    image_url: str | None = None
    scraped_at: datetime = field(default_factory=_utcnow)
    raw: dict[str, Any] | None = None

    # --- derived ----------------------------------------------------------
    @property
    def pfand(self) -> float | None:
        """Deposit charged at the till, EUR. ``None`` where undecidable."""
        return pkg.pfand(self.packaging, self.volume_l)

    @property
    def price_incl_pfand(self) -> float | None:
        """What the shopper actually hands over."""
        return pkg.price_with_pfand(self.price, self.packaging, self.volume_l)

    @property
    def price_per_litre(self) -> float | None:
        """Shelf price per litre — the only figure comparable across formats.

        Computed from our own price and volume rather than taken from the
        retailer's advertised unit price, because retailers differ on whether
        theirs includes the deposit. ``unit_price`` keeps theirs for checking.
        """
        if self.price is None or not self.volume_l:
            return None
        return round(self.price / (self.volume_l * max(self.pack_count, 1)), 2)

    @property
    def price_per_litre_incl_pfand(self) -> float | None:
        """Per-litre price with the deposit added, for a like-for-like total."""
        total = self.price_incl_pfand
        if total is None or not self.volume_l:
            return None
        return round(total / (self.volume_l * max(self.pack_count, 1)), 2)

    @property
    def packaging_label(self) -> str:
        return pkg.LABELS.get(self.packaging, self.packaging)

    @property
    def is_pack(self) -> bool:
        """Whether this listing sells several containers at once.

        The distinction matters to the format tables: a 9-litre "BiB-Paket" is
        three boxes, not a nine-litre container, and counting it as a container
        size would invent a gebinde no producer fills.
        """
        if self.pack_count > 1:
            return True
        # "paket" without a leading boundary, because German compounds it:
        # NORMA's cheapest box of all is an "Aktionspaket", and requiring a word
        # boundary would have ranked a bundle as its cheapest single wine.
        #
        # The bottle count is limited to two digits so that a German vintage
        # written the German way — "2024er Riesling" — is not read as a pack.
        return bool(re.search(r"paket\b|\bset\b|\b\d{1,2}er\b|\bkiste\b",
                              self.name or "", re.I))

    @property
    def bottle_equivalent_price(self) -> float | None:
        """What this wine would cost at 0.75 L — the size shoppers price against.

        A 3-litre box at 9.99 EUR is 2.50 EUR per standard bottle, and that
        comparison is the whole commercial argument for the format.

        Computed from price and volume rather than from ``price_per_litre``,
        which is already rounded: the 4.99 EUR entry box is 1.2475 EUR per
        bottle, and rounding twice turns that into 1.24 instead of 1.25.
        """
        if self.price is None or not self.volume_l:
            return None
        litres = self.volume_l * max(self.pack_count, 1)
        return round(self.price / litres * 0.75, 2)

    def to_row(self) -> dict[str, Any]:
        """Flatten for CSV/Excel, with the derived figures materialised."""
        row = dataclasses.asdict(self)
        row["grape_varieties"] = ", ".join(self.grape_varieties) or None
        row["scraped_at"] = self.scraped_at.isoformat()
        row["packaging_label"] = self.packaging_label
        row["pfand"] = self.pfand
        row["price_incl_pfand"] = self.price_incl_pfand
        row["price_per_litre"] = self.price_per_litre
        row["price_per_litre_incl_pfand"] = self.price_per_litre_incl_pfand
        row["bottle_equivalent_price"] = self.bottle_equivalent_price
        row["is_pack"] = self.is_pack
        row.pop("raw", None)
        return row


#: Column order shared by the CSV export and the workbook's data sheet.
EXPORT_COLUMNS = [
    "retailer", "retailer_label", "channel", "trade_format",
    "external_id", "name", "brand",
    "packaging", "packaging_label", "volume_l", "pack_count", "is_pack",
    "price", "currency", "price_basis", "pfand", "price_incl_pfand",
    "price_per_litre", "price_per_litre_incl_pfand", "bottle_equivalent_price",
    "unit_price", "list_price", "on_promotion", "in_stock", "product_type",
    "colour", "sweetness", "abv", "vintage", "country", "region",
    "grape_varieties", "category_path", "packaging_evidence", "url", "image_url",
    "scraped_at",
]
