"""Glovo storefronts — third-party delivery catalogue for brick retailers.

Glovo is the only route into Profi (~1,700 stores, no web shop, own site rejects
bots) and into Supeco. Its store pages are server-rendered and embed everything
an adapter needs: the ``stores/{id}/addresses/{id}`` pair and the section slugs
of the wine categories. Product tiles then come from the public
``content/partial`` API — plain HTTP, no login, ``robots.txt`` allows it.

Same third-party caveats as Bolt Food, plus one measured quirk of Glovo's:
comparing Penny's Glovo listing against penny.ro showed Glovo **folds the
0.50-lei SGR bottle deposit into the displayed price**, so rows here run ~0.50
above shelf even before any platform margin. Prices are recorded as displayed,
with the caveat documented rather than "corrected" — every row names the
platform in ``location`` and ``raw.source``.
"""

from __future__ import annotations

import logging
import re

from ..models import WineProduct
from ..normalize import parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

API = "https://api.glovoapp.com"
PAGE = "https://glovoapp.com/ro/ro/{city}/stores/{slug}"

_IDS_RE = re.compile(r"stores/(\d+)/addresses/(\d+)")
# Section slugs like "vin-alb-romania-s.57624334" in the SSR payload. The
# list-item/sublist/tab- variants repeat the same ids for navigation chrome.
_SECTION_RE = re.compile(r"(?<![a-z-])([a-z0-9-]*(?:vin|spumant|sampanie)[a-z0-9-]*)-s\.(\d+)")

HEADERS = {
    "glovo-api-version": "14",
    "glovo-app-platform": "web",
    "glovo-app-type": "customer",
    "glovo-language-code": "ro",
    "Origin": "https://glovoapp.com",
}


class GlovoStoreAdapter(Adapter):
    """One retailer's store on Glovo. Subclasses set slug and city."""

    store_slug: str = ""
    city_path: str = "bucharest"      # path segment of the store page URL
    city_code: str = "buc"            # glovo-location-city-code header

    @property
    def _slug(self) -> str:
        return str(self.config.get("store_slug", self.store_slug))

    @property
    def _city(self) -> str:
        return str(self.config.get("city_path", self.city_path))

    def _headers(self) -> dict[str, str]:
        return {**HEADERS,
                "glovo-location-city-code": str(self.config.get("city_code", self.city_code))}

    async def _store_page(self) -> tuple[str, str, dict[str, str]]:
        """Resolve (store_id, address_id, {section_id: slug}) from the SSR page."""
        html = await self.fetcher.get_text(PAGE.format(city=self._city, slug=self._slug))
        ids = _IDS_RE.search(html)
        if not ids:
            raise RuntimeError(f"no store/address ids on the Glovo page for {self._slug}")
        sections: dict[str, str] = {}
        for slug, section_id in _SECTION_RE.findall(html):
            if slug.startswith(("list-item-", "sublist-", "tab-")):
                continue
            sections[section_id] = slug
        return ids.group(1), ids.group(2), sections

    def _to_product(self, tile: dict, section_title: str | None) -> WineProduct | None:
        external_id = tile.get("externalId") or tile.get("storeProductId") or tile.get("id")
        name = (tile.get("name") or "").strip()
        if not external_id or not name:
            return None
        price_info = tile.get("priceInfo") or {}
        description = tile.get("description") or ""
        return self.make_product(
            external_id=external_id,
            name=name,
            url=PAGE.format(city=self._city, slug=self._slug),
            price=parse_price(tile.get("price") if tile.get("price") is not None
                              else price_info.get("amount")),
            currency=price_info.get("currencyCode") or "RON",
            on_promotion=bool(tile.get("promotions")),
            category_path=f"Vin/{section_title}" if section_title else "Vin",
            image_url=tile.get("imageUrl") or None,
            raw={"source": "glovo", "description": description[:300] or None,
                 "restricted": tile.get("restricted")},
        )

    async def scrape(self) -> list[WineProduct]:
        store_id, address_id, sections = await self._store_page()
        log.info("[%s] store %s/%s, %d wine sections",
                 self.key, store_id, address_id, len(sections))
        products: list[WineProduct] = []
        for section_id, slug in sections.items():
            url = (f"{API}/v4/stores/{store_id}/addresses/{address_id}"
                   f"/content/partial?component=section&id={section_id}")
            try:
                data = await self.fetcher.get_json(url, headers=self._headers())
            except Exception as exc:
                log.warning("[%s] section %s (%s) failed: %s", self.key, section_id, slug, exc)
                continue
            payload = data.get("data") or {}
            title = payload.get("title")
            count = 0
            for grid in payload.get("body") or []:
                for element in (grid.get("data") or {}).get("elements") or []:
                    if element.get("type") != "PRODUCT_TILE":
                        continue
                    product = self._to_product(element.get("data") or {}, title)
                    if product:
                        products.append(product)
                        count += 1
            log.debug("[%s] %s -> %d tiles", self.key, slug, count)
            if self.limit and len(products) >= self.limit:
                break
        # Sections overlap (a wine can sit in both a varietal and a promo
        # section); keep_wines de-duplicates on external id.
        return self.keep_wines(products)


@register
class ProfiGlovoAdapter(GlovoStoreAdapter):
    key = "profi_glovo"
    label = "Profi via Glovo"
    catalogue = "catalogue"
    store_slug = "profi-buc"
    location = "glovo/profi-buc-bucuresti"
    note = ("Only data route into Profi (own site rejects bots; ~1,700 stores). "
            "~70 wines. Glovo prices include the 0.50-lei SGR deposit.")


@register
class SupecoGlovoAdapter(GlovoStoreAdapter):
    key = "supeco_glovo"
    label = "Supeco via Glovo"
    catalogue = "catalogue"
    store_slug = "supeco-scv"
    city_path = "suceava"
    city_code = "scv"
    location = "glovo/supeco-scv-suceava"
    note = ("Only data route into Supeco (own site blocked at the edge). "
            "Suceava store — the single Supeco on any delivery platform.")
