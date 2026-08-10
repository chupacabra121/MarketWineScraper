"""Carrefour Romania — Magento 2, server-rendered listing pages.

Carrefour renders product tiles into the category HTML, so a plain HTTP client
is enough. Prices live in ``data-price-amount`` on the price box; the sibling
``<meta itemprop="price">`` carries the undiscounted price, which is how we spot
promotions.
"""

from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from ..models import WineProduct
from ..normalize import parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://carrefour.ro"
WINE_CATEGORY = "/bacanie-carrefour/vinuri-romanesti-si-internationale"
PAGE_SIZE = 48       # the category toolbar offers 24 or 48
MAX_PAGES = 60


@register
class CarrefourAdapter(Adapter):
    key = "carrefour"
    label = "Carrefour Romania"
    catalogue = "catalogue"
    note = "Magento category pages, server-rendered."

    def _page_url(self, page: int) -> str:
        return f"{BASE}{WINE_CATEGORY}?product_list_limit={PAGE_SIZE}&p={page}"

    @staticmethod
    def _total_pages(tree: HTMLParser) -> int:
        """Read the highest ``?p=N`` in the pager, defaulting to a single page."""
        pages = {1}
        for node in tree.css("a[href]"):
            match = re.search(r"[?&]p=(\d+)", node.attributes.get("href") or "")
            if match:
                pages.add(int(match.group(1)))
        return min(max(pages), MAX_PAGES)

    def _parse_tile(self, tile) -> WineProduct | None:
        product_id = tile.attributes.get("data-product-id")
        if not product_id:
            return None

        name_link = tile.css_first("div.productItem-name a")
        name = (name_link.text(strip=True) if name_link else "") or ""
        url = name_link.attributes.get("href") if name_link else None
        if not name:
            image = tile.css_first("img.product-image-photo")
            name = (image.attributes.get("alt") or "") if image else ""
        if not name:
            return None

        price = None
        price_node = tile.css_first("[data-price-amount]")
        if price_node:
            price = parse_price(price_node.attributes.get("data-price-amount"))

        # Carrefour listing tiles carry no strikethrough price: the only other
        # figure is <meta itemprop="price">, which sits a rounding step above the
        # displayed price on 96% of wines (median +1.3%) and is not a former
        # price. Treating it as one flagged nearly the whole catalogue as
        # discounted, so promotions are simply not detectable from listings here.
        list_price = None

        # The add-to-cart button carries the analytics payload: sku, brand, path.
        button = tile.css_first("button.tocart") or tile.css_first("[data-brand]")
        sku = brand = category = availability = None
        if button:
            attrs = button.attributes
            sku = attrs.get("data-id")
            brand = (attrs.get("data-brand") or "").strip() or None
            category = attrs.get("data-category")
            availability = attrs.get("data-dimension10")

        image = tile.css_first("img.product-image-photo")
        image_url = None
        if image:
            image_url = image.attributes.get("data-src") or image.attributes.get("src")
            if image_url and "lazyload" in image_url:
                image_url = image.attributes.get("data-src")

        return self.make_product(
            external_id=sku or product_id,
            name=name,
            url=url,
            price=price,
            list_price=list_price,
            on_promotion=list_price is not None,
            in_stock=(availability == "available") if availability else None,
            brand=brand,
            category_path=category,
            image_url=image_url,
            raw={"magento_id": product_id},
        )

    async def scrape(self) -> list[WineProduct]:
        first_html = await self.fetcher.get_text(self._page_url(1))
        tree = HTMLParser(first_html)
        total_pages = self._total_pages(tree)
        log.info("[carrefour] %d pages of up to %d products", total_pages, PAGE_SIZE)

        products: list[WineProduct] = []

        def harvest(parsed: HTMLParser) -> int:
            before = len(products)
            for tile in parsed.css("li.product[data-product-id]"):
                product = self._parse_tile(tile)
                if product:
                    products.append(product)
            return len(products) - before

        harvest(tree)
        for page in range(2, total_pages + 1):
            if self.limit and len(products) >= self.limit:
                break
            try:
                html = await self.fetcher.get_text(self._page_url(page))
            except Exception as exc:
                log.warning("[carrefour] page %d failed: %s", page, exc)
                continue
            found = harvest(HTMLParser(html))
            log.debug("[carrefour] page %d -> %d tiles (%d total)", page, found, len(products))
            if found == 0:
                break
        return self.keep_wines(products)
