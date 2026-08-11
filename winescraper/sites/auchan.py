"""Auchan Romania — VTEX.

Auchan runs on VTEX, whose public catalog API returns the full product document
including the wine attributes Auchan fills in per product (grape variety, ABV,
country, region, producer). That makes it by far the richest of the Romanian
retailers, and no browser is needed.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import WineProduct
from ..normalize import parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.auchan.ro"
TREE_URL = f"{BASE}/api/catalog_system/pub/category/tree/3"
SEARCH_URL = f"{BASE}/api/catalog_system/pub/products/search"
PAGE_SIZE = 50
# VTEX refuses offsets past ~2500 on the public endpoint, so we page per
# subcategory rather than hammering the parent category.
MAX_OFFSET = 2450

WINE_ROOT = "vin si sampanie"


@register
class AuchanAdapter(Adapter):
    key = "auchan"
    label = "Auchan Romania"
    catalogue = "catalogue"
    location = "online"
    note = "VTEX public catalog API; richest attribute coverage of all sites."

    async def _wine_category_paths(self) -> list[str]:
        """Discover the wine category and its children from the live tree.

        VTEX filters on the full id path (``C:/5000000/5080000/5080100/``), not
        the leaf id alone, so the ancestry is carried down the walk. Hardcoding
        ids would break silently the next time Auchan reorganises its taxonomy.
        """
        tree = await self.fetcher.get_json(TREE_URL)
        paths: list[str] = []

        def walk(nodes: list[dict], ancestry: list[str]) -> None:
            for node in nodes:
                trail = ancestry + [str(node["id"])]
                if str(node.get("name", "")).strip().lower() == WINE_ROOT:
                    collect(node, trail)
                else:
                    walk(node.get("children") or [], trail)

        def collect(node: dict, trail: list[str]) -> None:
            children = node.get("children") or []
            if children:
                for child in children:
                    collect(child, trail + [str(child["id"])])
            else:
                paths.append("/".join(trail))

        walk(tree, [])
        if not paths:
            log.warning("[auchan] wine category not found in tree; falling back to defaults")
            paths = ["5000000/5080000"]
        return paths

    async def _fetch_category(self, category_path: str) -> list[dict]:
        """Page through one category until VTEX stops returning products."""
        products: list[dict] = []
        offset = 0
        while offset <= MAX_OFFSET:
            url = (f"{SEARCH_URL}?fq=C:/{category_path}/"
                   f"&_from={offset}&_to={offset + PAGE_SIZE - 1}")
            # VTEX has no total to check a run against, so a swallowed error
            # here would silently truncate the category at this offset with
            # nothing downstream able to notice. Fail the run instead.
            page = await self.fetcher.get_json(url)
            if not page:
                break
            products.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            if self.limit and len(products) >= self.limit:
                break
        return products

    @staticmethod
    def _first(raw: dict, key: str) -> str | None:
        value = raw.get(key)
        if isinstance(value, list) and value:
            return str(value[0]).strip() or None
        if isinstance(value, str):
            return value.strip() or None
        return None

    def _to_product(self, raw: dict[str, Any]) -> WineProduct | None:
        items = raw.get("items") or []
        if not items:
            return None
        item = items[0]
        sellers = item.get("sellers") or []
        offer = (sellers[0].get("commertialOffer") if sellers else None) or {}

        price = parse_price(offer.get("Price"))
        list_price = parse_price(offer.get("ListPrice"))
        # VTEX repeats the selling price in ListPrice when nothing is discounted.
        if list_price is not None and price is not None and list_price <= price:
            list_price = None

        images = item.get("images") or []
        categories = raw.get("categories") or []

        volume = self._first(raw, "Volum (l)")
        abv = self._first(raw, "Concentratie alcoolica")
        grapes = raw.get("Soi struguri") or []

        return self.make_product(
            external_id=raw.get("productId") or item.get("itemId"),
            name=raw.get("productName") or item.get("nameComplete") or "",
            url=raw.get("link"),
            price=price,
            list_price=list_price,
            on_promotion=list_price is not None,
            in_stock=bool(offer.get("IsAvailable")) and (offer.get("AvailableQuantity") or 0) > 0,
            brand=(raw.get("brand") or "").strip() or None,
            producer=self._first(raw, "Nume producator"),
            volume_l=parse_price(volume) if volume else None,
            abv=float(abv.replace(",", ".")) if abv and abv.replace(",", ".").replace(".", "").isdigit() else None,
            sweetness=(self._first(raw, "Nivel de dulceata") or "").lower() or None,
            country=self._first(raw, "Tara de origine"),
            region=self._first(raw, "Zona"),
            grape_varieties=[str(g).strip() for g in grapes if str(g).strip()],
            category_path=categories[0].strip("/") if categories else None,
            image_url=images[0].get("imageUrl") if images else None,
            raw={"productReference": raw.get("productReference"),
                 "tip": self._first(raw, "Tip Produs")},
        )

    async def scrape(self) -> list[WineProduct]:
        category_paths = await self._wine_category_paths()
        log.info("[auchan] %d wine categories", len(category_paths))
        products: list[WineProduct] = []
        for category_path in category_paths:
            for raw in await self._fetch_category(category_path):
                product = self._to_product(raw)
                if product:
                    products.append(product)
            log.info("[auchan] category %s -> %d products so far",
                     category_path, len(products))
            if self.limit and len(products) >= self.limit:
                break
        return self.keep_wines(products)
