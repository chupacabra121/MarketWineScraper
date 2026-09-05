"""Prices read off a shelf by a person, for the shops no scraper can reach.

Seven Romanian chains publish no wine catalogue anywhere — Lidl, La Cocoș, Froo,
Unicarm, Annabella, La Doi Pași and Atac — and no delivery platform carries them
either. Their prices exist only in the aisle. This loads them from a CSV that
someone fills in by hand, so a photographed price rail can become a row like any
other instead of living in a chat message.

A capture is not a scrape and the file says so on every row: ``captured_by`` and
``note`` travel into ``raw``, the run is recorded with ``status='capture'``, and
nothing here is ever overwritten by a scrape, because these retailers have none.

The price written down is the shelf price, deposit excluded — that is what
Romanian price rails show, and it puts a capture on the same footing as every
online source, so :mod:`winescraper.deposit` adds the SGR the same way.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .models import WineProduct
from .normalize import enrich

#: Written by hand, so the reader is forgiving about which columns are present.
COLUMNS = ("observed_at", "retailer", "location", "name", "brand", "volume_l",
           "price", "list_price", "captured_by", "note")

REQUIRED = ("retailer", "name", "price")


def _float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def read(path: str | Path) -> list[WineProduct]:
    """Parse a capture file into products, skipping blank and comment rows."""
    path = Path(path)
    if not path.exists():
        return []
    products: list[WineProduct] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            if not row or (row.get("retailer") or "").startswith("#"):
                continue
            if any(not (row.get(field) or "").strip() for field in REQUIRED):
                continue
            price = _float(row.get("price"))
            if price is None:
                raise ValueError(f"{path}:{line}: price is not a number")
            list_price = _float(row.get("list_price"))
            name = row["name"].strip()
            # The identity of a hand-typed row is the name, so the id has to be
            # stable across edits to anything else. Retyping the name makes a
            # new product, which is correct: it is a different line on the rail.
            external_id = f"capture-{abs(hash((row['retailer'], name))) % 10**10}"
            product = WineProduct(
                retailer=row["retailer"].strip(),
                external_id=external_id,
                name=name,
                price=price,
                list_price=list_price if list_price and list_price > price else None,
                on_promotion=bool(list_price and list_price > price),
                brand=(row.get("brand") or "").strip() or None,
                volume_l=_float(row.get("volume_l")),
                location=(row.get("location") or "").strip() or None,
                offer_type="catalogue",
                in_stock=True,
                raw={"source": "shelf capture",
                     "captured_by": (row.get("captured_by") or "").strip() or None,
                     "note": (row.get("note") or "").strip() or None},
            )
            stamped = (row.get("observed_at") or "").strip()
            if stamped:
                product.scraped_at = datetime.fromisoformat(stamped)
                if product.scraped_at.tzinfo is None:
                    product.scraped_at = product.scraped_at.replace(tzinfo=timezone.utc)
            enrich(product)
            products.append(product)
    return products


def template(path: str | Path) -> Path:
    """Write an empty capture file with the columns and an example row."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerow(["2026-08-12", "froo", "froo-bucuresti", "Babanu Vin rosu demidulce",
                         "Babanu", "2", "16.99", "", "", "pret de raft, fara SGR"])
    return path
