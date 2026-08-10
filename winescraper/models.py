"""Data model for a single scraped wine listing."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class WineProduct:
    """One wine as listed by one retailer at one point in time.

    Only ``retailer``, ``external_id`` and ``name`` are strictly required; every
    site exposes a different subset of the rest, and missing values stay ``None``
    rather than being guessed.
    """

    # --- identity -------------------------------------------------------
    retailer: str
    external_id: str
    name: str
    url: str | None = None

    # --- commercial -----------------------------------------------------
    price: float | None = None
    currency: str = "RON"
    # Pre-discount price, when the site advertises one.
    list_price: float | None = None
    # Price per litre as advertised by the retailer, when given.
    unit_price: float | None = None
    unit_price_unit: str | None = None
    on_promotion: bool = False
    # "catalogue" for a permanently listed product, "promo" for weekly-offer-only listings.
    offer_type: str = "catalogue"
    in_stock: bool | None = None

    # --- wine attributes -------------------------------------------------
    brand: str | None = None
    producer: str | None = None
    volume_l: float | None = None
    abv: float | None = None
    vintage: int | None = None
    colour: str | None = None          # alb | rosu | rose
    sweetness: str | None = None       # sec | demisec | demidulce | dulce
    sparkling: bool | None = None
    country: str | None = None
    region: str | None = None
    grape_varieties: list[str] = field(default_factory=list)

    # --- provenance ------------------------------------------------------
    category_path: str | None = None
    image_url: str | None = None
    # Which store/city the price belongs to; retailers price per store.
    location: str | None = None
    scraped_at: datetime = field(default_factory=_utcnow)
    raw: dict[str, Any] | None = None

    @property
    def price_per_litre(self) -> float | None:
        """Price per litre computed from price and volume.

        Preferred over ``unit_price`` only when the retailer gives no unit price
        of its own, since retailers occasionally advertise per-litre figures that
        include deposit fees.
        """
        if self.price is None or not self.volume_l:
            return None
        return round(self.price / self.volume_l, 2)

    def to_row(self) -> dict[str, Any]:
        """Flatten to a dict suitable for CSV/JSONL export and DB insertion."""
        d = dataclasses.asdict(self)
        d["grape_varieties"] = ", ".join(self.grape_varieties) if self.grape_varieties else None
        d["scraped_at"] = self.scraped_at.isoformat()
        d["price_per_litre"] = self.price_per_litre
        d["raw"] = json.dumps(self.raw, ensure_ascii=False) if self.raw else None
        return d


# Column order used consistently by the CSV exporter and the SQLite schema.
EXPORT_COLUMNS = [
    "retailer", "external_id", "name", "brand", "producer",
    "price", "currency", "list_price", "on_promotion", "offer_type",
    "unit_price", "unit_price_unit", "price_per_litre",
    "volume_l", "abv", "vintage", "colour", "sweetness", "sparkling",
    "country", "region", "grape_varieties",
    "in_stock", "category_path", "url", "image_url", "location", "scraped_at",
]
