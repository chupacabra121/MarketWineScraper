"""Freshful — online-only grocery (Ahold Delhaize), Next.js storefront.

Freshful serves its catalogue as JSON with no bot protection at all, which makes
it the cleanest source of the lot. Two routes expose the same data:

* the category page itself, which embeds page 1 in ``__NEXT_DATA__``
* ``/api/v2/shop/categories/...``, which is the only route that paginates

``robots.txt`` disallows ``/api/v2/shop`` while allowing the category pages.
This build follows the configured posture of treating robots as advisory, so the
API is used by default; setting ``respect_robots`` in the site config restricts
the adapter to the embedded first page instead.

Like Penny, Freshful quotes a loyalty ("Genius") price alongside the shelf price.
The shelf price is what gets recorded, so figures stay comparable.
"""

from __future__ import annotations

import json
import logging
import re

from ..models import WineProduct
from ..normalize import parse_price, parse_unit_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.freshful.ro"
# "Vinuri / Toate produsele" — the parent of the white/red/rose/sparkling/eco
# children, so one crawl covers the whole wine range.
WINE_CATEGORY = "705-vinuri"
CATEGORY_URL = f"{BASE}/c/7-bauturi-si-tutun/{WINE_CATEGORY}"
API_URL = f"{BASE}/api/v2/shop/categories/{{category}}?page={{page}}&itemsPerPage={{size}}"
PAGE_SIZE = 60
MAX_PAGES = 60

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


@register
class FreshfulAdapter(Adapter):
    key = "freshful"
    label = "Freshful by eMAG"
    catalogue = "catalogue"
    location = "online"
    note = "Next.js JSON catalogue, no bot protection; ~930 wines."

    @property
    def respect_robots(self) -> bool:
        """When set, stay on the robots-allowed category page (first 60 wines)."""
        return bool(self.config.get("respect_robots", False))

    @staticmethod
    def _payload_from_html(html: str) -> dict:
        """Pull the category payload out of the page's embedded Next.js state."""
        match = _NEXT_DATA_RE.search(html)
        if not match:
            raise ValueError("no __NEXT_DATA__ block on the Freshful category page")
        data = json.loads(match.group(1))
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
        for query in queries:
            key = query.get("queryKey") or []
            if key and key[0] == "category":
                return query["state"]["data"]["payload"]
        raise ValueError("no category query in the Freshful page state")

    def _to_product(self, item: dict) -> WineProduct | None:
        code = item.get("code") or item.get("sku")
        name = item.get("name")
        if not code or not name:
            return None

        price = parse_price(item.get("price"))
        # A live discount shows as promotionalPrice below price, with the
        # pre-discount figure in originalPrice.
        promotional = parse_price(item.get("promotionalPrice"))
        list_price = parse_price(item.get("originalPrice"))
        if promotional is not None and price is not None and promotional < price:
            list_price = list_price or price
            price = promotional
        if list_price is not None and price is not None and list_price <= price:
            list_price = None

        unit_price, unit = parse_unit_price(item.get("unitPriceLabel") or "")

        image = item.get("image") or {}
        image_url = None
        for size in ("large", "extralarge", "thumbnail"):
            block = image.get(size) or {}
            if block.get("default"):
                image_url = block["default"]
                break

        # The last breadcrumb is the product itself; the rest are the category.
        crumbs = [c.get("name") for c in (item.get("breadcrumbs") or [])[:-1]]
        category_path = "/".join(c for c in crumbs if c) or None

        slug = item.get("slug")
        quantity = item.get("maxAvailableQuantity")

        return self.make_product(
            external_id=code,
            name=name,
            url=f"{BASE}/p/{slug}" if slug else None,
            price=price,
            currency=item.get("currencyCode") or "RON",
            list_price=list_price,
            on_promotion=list_price is not None,
            unit_price=unit_price,
            unit_price_unit=unit,
            in_stock=bool(item.get("isAvailable")) and (quantity is None or quantity > 0),
            brand=(item.get("brand") or "").strip() or None,
            category_path=category_path,
            image_url=image_url,
            raw={"genius_price": parse_price(item.get("geniusPrice")),
                 "sgr": next((t.get("text") for t in (item.get("taxes") or [])
                              if t.get("type") == "sgr"), None)},
        )

    async def _first_page(self) -> dict:
        html = await self.fetcher.get_text(CATEGORY_URL)
        return self._payload_from_html(html)

    async def _api_page(self, page: int) -> dict:
        url = API_URL.format(category=WINE_CATEGORY, page=page, size=PAGE_SIZE)
        data = await self.fetcher.get_json(url, headers={"Referer": CATEGORY_URL})
        return data.get("payload") or data

    async def scrape(self) -> list[WineProduct]:
        payload = await self._first_page()
        total = payload.get("total") or 0
        pages = min(int(payload.get("pages") or 1), MAX_PAGES)
        log.info("[freshful] %d wines across %d pages", total, pages)

        products: list[WineProduct] = []

        def harvest(items: list[dict]) -> None:
            for item in items:
                product = self._to_product(item)
                if product:
                    products.append(product)

        harvest(payload.get("items") or [])

        if self.respect_robots:
            log.info("[freshful] respect_robots set — stopping after the embedded first page")
            return self.keep_wines(products)

        for page in range(2, pages + 1):
            if self.limit and len(products) >= self.limit:
                break
            try:
                page_payload = await self._api_page(page)
            except Exception as exc:
                log.warning("[freshful] page %d failed: %s", page, exc)
                continue
            items = page_payload.get("items") or []
            if not items:
                break
            harvest(items)
            log.debug("[freshful] page %d -> %d products", page, len(products))
        return self.keep_wines(products)
