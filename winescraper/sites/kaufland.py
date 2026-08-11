"""Kaufland Romania — weekly offers only.

Kaufland does not run a shoppable grocery catalogue in Romania; its site
publishes the weekly leaflet as structured HTML. That yields real wines with
real prices, but only those on promotion that week, so every row is tagged
``offer_type='promo'`` and the retailer is reported as promo-only.

Tiles carry no product id, so the identifier is taken from the article number
embedded in the media URL, falling back to a slug of the title.
"""

from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from ..models import WineProduct
from ..normalize import fold, parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.kaufland.ro"
# The beverages slice of the weekly offer overview.
OFFERS_URL = f"{BASE}/oferte/prezentare-generala-oferte.html?kloffer-category=10_B%C4%83uturi"
_ARTICLE_RE = re.compile(r"/image/schwarz/(\d+)")


@register
class KauflandAdapter(Adapter):
    key = "kaufland"
    label = "Kaufland Romania"
    catalogue = "promo"
    location = "national-leaflet"
    note = "Weekly offer leaflet only — Kaufland RO has no shoppable wine catalogue."

    @staticmethod
    def _external_id(tile, name: str) -> str:
        image = tile.css_first("img")
        if image:
            for attr in ("src", "srcset"):
                match = _ARTICLE_RE.search(image.attributes.get(attr) or "")
                if match:
                    return match.group(1)
        slug = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")
        return f"slug-{slug}"[:80]

    def _parse_tile(self, tile) -> WineProduct | None:
        title_node = tile.css_first(".k-product-tile__title")
        if not title_node:
            return None
        title = title_node.text(strip=True)
        subtitle_node = tile.css_first(".k-product-tile__subtitle")
        subtitle = subtitle_node.text(strip=True) if subtitle_node else ""
        name = " ".join(part for part in (title, subtitle) if part).strip()
        if not name:
            return None

        price_node = tile.css_first(".k-price-tag__price")
        price = parse_price(price_node.text(strip=True)) if price_node else None

        old_node = tile.css_first(".k-price-tag__old-price-line-through")
        list_price = parse_price(old_node.text(strip=True)) if old_node else None
        if list_price is not None and price is not None and list_price <= price:
            list_price = None

        unit_node = tile.css_first(".k-product-tile__unit-price")
        base_node = tile.css_first(".k-product-tile__base-price")
        unit_text = base_node.text(strip=True) if base_node else ""

        image = tile.css_first("img")
        image_url = image.attributes.get("src") if image else None

        return self.make_product(
            external_id=self._external_id(tile, name),
            name=name,
            url=OFFERS_URL,
            price=price,
            list_price=list_price,
            on_promotion=True,
            category_path="Oferte/Bauturi",
            image_url=image_url,
            raw={"unit": unit_node.text(strip=True) if unit_node else None,
                 "base_price_text": unit_text},
        )

    async def scrape(self) -> list[WineProduct]:
        html = await self.fetcher.get_text(OFFERS_URL)
        tree = HTMLParser(html)
        tiles = tree.css("a.k-product-tile")
        log.info("[kaufland] %d offer tiles in the beverages section", len(tiles))
        products: list[WineProduct] = []
        for tile in tiles:
            product = self._parse_tile(tile)
            if product:
                products.append(product)
        # The beverages section covers everything from water to spirits, so the
        # wine filter does most of the work here.
        return self.keep_wines(products)
