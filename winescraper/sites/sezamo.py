"""Sezamo — online-only grocery on the Rohlik Group platform.

Sezamo splits one product across four JSON endpoints, all reachable over plain
HTTP and none of them disallowed by robots.txt:

* ``/api/v1/categories/normal/{id}/products`` — the product ids in a category
* ``/api/v1/products``                        — names, brands, package text
* ``/api/v1/products/prices``                 — price, price per unit, active sales
* ``/api/v1/products/stock``                  — availability and package size

The ids call returns the whole category in one request, so the crawl is a
handful of batched lookups rather than page-by-page scraping. Package size comes
back structurally (``packageInfo``), which is more reliable than reading litres
out of the title.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from ..models import WineProduct
from ..normalize import parse_price, parse_volume_l
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.sezamo.ro"
WINE_CATEGORY_ID = 1233
CATEGORY_URL = f"{BASE}/c{WINE_CATEGORY_ID}-vin"
IDS_URL = (f"{BASE}/api/v1/categories/normal/{{category}}/products"
           "?page={page}&size={size}&sort=recommended&filter=")
DETAIL_URL = f"{BASE}/api/v1/products?{{query}}"
PRICES_URL = f"{BASE}/api/v1/products/prices?{{query}}"
STOCK_URL = f"{BASE}/api/v1/products/stock?{{query}}"

IDS_PAGE_SIZE = 500
BATCH_SIZE = 100
MAX_PAGES = 20

# Sezamo returns only a numeric mainCategoryId per product. Naming the wine
# branches gives the normaliser useful leaf context (a product in "Vin spumant"
# is sparkling even when its title never says so).
SUBCATEGORIES = {
    1608: "Vin alb",
    1609: "Vin rosu",
    1610: "Vin rose",
    1611: "Vin spumant",
    1613: "Bauturi cu vin",
    1615: "Vin bag-in-box",
    1616: "Vin",
    2596: "Vinuri fara alcool",
}


def _query(ids: Iterable[int]) -> str:
    return "&".join(f"products={i}" for i in ids)


@register
class SezamoAdapter(Adapter):
    key = "sezamo"
    label = "Sezamo"
    catalogue = "catalogue"
    location = "online"
    note = "Rohlik-platform JSON API, no bot protection; ~440 wines."

    async def _product_ids(self) -> list[int]:
        """Collect every product id in the wine category."""
        ids: list[int] = []
        for page in range(MAX_PAGES):
            url = IDS_URL.format(category=WINE_CATEGORY_ID, page=page, size=IDS_PAGE_SIZE)
            data = await self.fetcher.get_json(url, headers={"Referer": CATEGORY_URL})
            batch = data.get("productIds") or []
            ids.extend(batch)
            if len(batch) < IDS_PAGE_SIZE:
                break
        # Preserve order but drop any repeats across pages.
        seen: set[int] = set()
        unique = [i for i in ids if not (i in seen or seen.add(i))]
        log.info("[sezamo] %d product ids in the wine category", len(unique))
        return unique

    async def _batch(self, url_template: str, ids: list[int], label: str) -> list[dict]:
        records: list[dict] = []
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start:start + BATCH_SIZE]
            url = url_template.format(query=_query(chunk))
            try:
                data = await self.fetcher.get_json(url, headers={"Referer": CATEGORY_URL})
            except Exception as exc:
                log.warning("[sezamo] %s batch at %d failed: %s", label, start, exc)
                continue
            if isinstance(data, list):
                records.extend(data)
        return records

    @staticmethod
    def _price_from(price_doc: dict[str, Any]) -> tuple[float | None, float | None, bool, float | None]:
        """Return (price, list_price, on_promotion, price_per_unit).

        An active entry in ``sales`` replaces the standing price and carries the
        pre-discount figure in ``originalPrice``.
        """
        base = parse_price((price_doc.get("price") or {}).get("amount"))
        per_unit = parse_price((price_doc.get("pricePerUnit") or {}).get("amount"))
        for sale in price_doc.get("sales") or []:
            if not sale.get("active"):
                continue
            sale_price = parse_price((sale.get("price") or {}).get("amount"))
            if sale_price is None:
                continue
            original = parse_price((sale.get("originalPrice") or {}).get("amount")) or base
            sale_per_unit = parse_price((sale.get("pricePerUnit") or {}).get("amount"))
            if original is not None and original <= sale_price:
                original = None
            return sale_price, original, True, (sale_per_unit or per_unit)
        return base, None, False, per_unit

    @staticmethod
    def _volume_from(stock_doc: dict[str, Any], detail: dict[str, Any]) -> float | None:
        """Prefer the structural package size over parsing the title."""
        package = (stock_doc or {}).get("packageInfo") or {}
        amount, unit = package.get("amount"), (package.get("unit") or "").lower()
        if isinstance(amount, (int, float)) and amount > 0:
            if unit == "l":
                return round(float(amount), 4)
            if unit == "ml":
                return round(float(amount) / 1000, 4)
        return parse_volume_l(detail.get("textualAmount") or detail.get("name") or "")

    def _to_product(self, detail: dict, price_doc: dict, stock_doc: dict) -> WineProduct | None:
        product_id = detail.get("id")
        name = detail.get("name")
        if not product_id or not name:
            return None

        price, list_price, promo, per_unit = self._price_from(price_doc or {})
        images = detail.get("images") or []
        slug = detail.get("slug")
        leaf = SUBCATEGORIES.get(detail.get("mainCategoryId"))

        in_stock = None
        if stock_doc:
            in_stock = bool(stock_doc.get("inStock"))

        return self.make_product(
            external_id=product_id,
            name=name,
            url=f"{BASE}/{product_id}-{slug}" if slug else CATEGORY_URL,
            price=price,
            currency=((price_doc or {}).get("price") or {}).get("currency") or "RON",
            list_price=list_price,
            on_promotion=promo,
            unit_price=per_unit,
            unit_price_unit=(detail.get("unit") or "").lower() or None,
            in_stock=in_stock,
            brand=(detail.get("brand") or "").strip() or None,
            volume_l=self._volume_from(stock_doc, detail),
            category_path=f"Bauturi/Vin/{leaf}" if leaf else "Bauturi/Vin",
            image_url=images[0] if images else None,
            raw={"mainCategoryId": detail.get("mainCategoryId"),
                 "textualAmount": detail.get("textualAmount")},
        )

    async def scrape(self) -> list[WineProduct]:
        ids = await self._product_ids()
        if self.limit:
            ids = ids[:self.limit]
        if not ids:
            return []

        details = await self._batch(DETAIL_URL, ids, "details")
        prices = await self._batch(PRICES_URL, ids, "prices")
        stock = await self._batch(STOCK_URL, ids, "stock")
        log.info("[sezamo] %d details, %d prices, %d stock records",
                 len(details), len(prices), len(stock))

        by_price = {d.get("productId"): d for d in prices}
        by_stock = {d.get("productId"): d for d in stock}

        products: list[WineProduct] = []
        for detail in details:
            product = self._to_product(
                detail, by_price.get(detail.get("id")), by_stock.get(detail.get("id")))
            if product:
                products.append(product)
        return self.keep_wines(products)
