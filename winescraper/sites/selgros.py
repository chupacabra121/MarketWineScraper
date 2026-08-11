"""Selgros Cash & Carry — Azure Cognitive Search.

The storefront queries an Azure Search index through a proxy on its own domain,
using a client-side query key. Wine categories are discovered from the
``categoryPath`` facet rather than hardcoded, so a taxonomy change shows up as
fewer categories rather than zero products.

Selgros prices per depot: every document carries a ``markets`` array and a
``prices[].plant`` code, so the configured market id is part of the identity of
a price observation.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import WineProduct
from ..normalize import parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

SEARCH_URL = ("https://www.selgros.ro/proxy/schaufenster/docs/"
              "search.post.search?api-version=2024-07-01")
# Client-side Azure Search query key, shipped in Selgros' own frontend. It DOES
# rotate — the first key here stopped working mid-project, and the proxy reports
# a rejected key as "HTTP 400: Missing product ID", which reads like a malformed
# request rather than an auth failure. The adapter therefore discovers the
# current key from the live page when the configured one is refused.
DEFAULT_API_KEY = "df056f8f4256465aeac1e5502767383f6c1fdf6f7e44947b5ccf01b2d95064ce"
DEFAULT_MARKET = 350          # Bucuresti Berceni
PAGE_SIZE = 50
PRODUCT_URL = "https://www.selgros.ro/exploreaza-sortimentul-selgros/product/{slug}-{pid}"


CATALOGUE_URL = "https://www.selgros.ro/exploreaza-sortimentul-selgros"


@register
class SelgrosAdapter(Adapter):
    key = "selgros"
    label = "Selgros Cash & Carry"
    catalogue = "catalogue"
    location = f"market-{DEFAULT_MARKET}"
    # The WAF fingerprints the TLS handshake: identical headers pass from a
    # browser and are rejected (403) from a Python HTTP client, so queries go
    # through the browser's network stack.
    needs_browser = True
    note = "Azure Search index; prices are per depot (market id configurable)."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._warmed = False
        self._discovered_key: str | None = None

    @property
    def market(self) -> int:
        return int(self.config.get("market", DEFAULT_MARKET))

    @property
    def api_key(self) -> str:
        return str(self._discovered_key or self.config.get("api_key") or DEFAULT_API_KEY)

    async def _discover_api_key(self) -> str | None:
        """Read the current query key off a live search request.

        The key is not in the page HTML or in any statically-linked bundle; the
        search web component supplies it at runtime. Watching the page make its
        own first search is the only reliable way to read it.
        """
        if self.browser is None:
            return None
        found: list[str] = []

        async def on_request(request):
            if "search.post.search" in request.url and not found:
                headers = await request.all_headers()
                key = headers.get("api-key")
                if key:
                    found.append(key)

        self.browser.context.on("request", on_request)
        try:
            await self.browser.page.goto(CATALOGUE_URL, wait_until="domcontentloaded",
                                         timeout=60000)
            for _ in range(20):
                if found:
                    break
                await self.browser.page.wait_for_timeout(1000)
        except Exception as exc:
            log.warning("[selgros] key discovery failed: %s", exc)
        finally:
            self.browser.context.remove_listener("request", on_request)

        if found:
            log.info("[selgros] discovered a fresh api-key from the live page")
            return found[0]
        return None

    def _headers(self) -> dict[str, str]:
        return {"api-key": self.api_key, "Referer": CATALOGUE_URL}

    async def _post(self, payload: dict) -> dict:
        if self.browser is not None:
            return await self.browser.post_json(SEARCH_URL, payload, headers=self._headers())
        return await self.fetcher.post_json(SEARCH_URL, payload, headers=self._headers())

    async def _search(self, payload: dict) -> dict:
        """POST a search, rediscovering the query key if the current one is refused."""
        if self.browser is not None and not self._warmed:
            await self.browser.warm_up(CATALOGUE_URL, wait_ms=4000)
            self._warmed = True
        try:
            return await self._post(payload)
        except Exception as exc:
            if "Missing product ID" not in str(exc) or self._discovered_key:
                raise
            log.warning("[selgros] query key refused; rediscovering it from the page")
            key = await self._discover_api_key()
            if not key:
                raise
            self._discovered_key = key
            self._warmed = False
            if self.browser is not None:
                await self.browser.warm_up(CATALOGUE_URL, wait_ms=4000)
                self._warmed = True
            return await self._post(payload)

    def _market_filter(self) -> str:
        return f"markets/any(m: m eq {self.market})"

    async def _wine_category_paths(self) -> list[str]:
        """Pull the categoryPath facet and keep the wine branches."""
        payload = {
            "facets": ["categoryPath,count:3000"],
            "top": 0,
            "search": "",
            "filter": self._market_filter(),
            "count": True,
        }
        data = await self._search(payload)
        facets = (data.get("@search.facets") or {}).get("categoryPath") or []
        paths = [f["value"] for f in facets
                 if str(f.get("value", "")).lower().startswith("vin")]
        # The facet counts are the index's own tally for those branches, so they
        # are the yardstick for whether a paging error lost part of the range.
        indexed = sum(f["count"] for f in facets if f["value"] in paths)
        self.expected_total = indexed or None
        log.info("[selgros] %d wine category paths, %d products indexed",
                 len(paths), indexed)
        return paths

    @staticmethod
    def _price_from(doc: dict[str, Any]) -> tuple[float | None, float | None, bool]:
        """Return (price, list_price, on_promotion) for one document.

        Selgros models an active offer as ``offerPrice`` alongside the standing
        ``price``; ``bestPrice30`` is the 30-day reference the offer is measured
        against, which is what a shopper sees struck through.
        """
        entries = doc.get("prices") or []
        standing = offer = reference = None
        for entry in entries:
            block = entry.get("price") or {}
            if standing is None:
                standing = parse_price(block.get("grossPrice"))
            offer_block = entry.get("offerPrice") or {}
            if offer_block and offer is None:
                offer = parse_price(offer_block.get("grossPrice"))
                best = offer_block.get("bestPrice30") or {}
                reference = parse_price(best.get("grossPrice"))
        fallback = parse_price(doc.get("filterPrice"))
        if offer is not None:
            return offer, (reference or standing), True
        price = standing if standing is not None else fallback
        return price, None, False

    def _to_product(self, doc: dict[str, Any]) -> WineProduct | None:
        product_id = doc.get("productId")
        title = doc.get("title") or ""
        if not product_id or not title:
            return None
        price, list_price, promo = self._price_from(doc)
        if list_price is not None and price is not None and list_price <= price:
            list_price = None
            promo = False

        images = doc.get("images") or []
        stock = doc.get("stock") or []
        in_stock = bool(stock and stock[0].get("status"))

        slug = "-".join(str(title).lower().split())[:80]
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug).strip("-")

        return self.make_product(
            external_id=product_id,
            name=title,
            url=PRODUCT_URL.format(slug=slug, pid=product_id),
            price=price,
            list_price=list_price,
            on_promotion=promo,
            in_stock=in_stock,
            brand=(doc.get("productBrand") or "").strip() or None,
            category_path=doc.get("categoryPath"),
            image_url=images[0].get("url") if images else None,
            raw={"labels": doc.get("labels"), "market": self.market},
        )

    async def _fetch_path(self, path: str) -> list[dict]:
        """Page one category path with skip/top."""
        # Escape single quotes for the OData string literal.
        literal = path.replace("'", "''")
        docs: list[dict] = []
        skip = 0
        while True:
            payload = {
                "skip": skip,
                "top": PAGE_SIZE,
                "search": "",
                "filter": f"{self._market_filter()} and search.in(categoryPath, '{literal}', '|')",
                "orderby": "weight desc",
                "count": True,
            }
            try:
                data = await self._search(payload)
            except Exception as exc:
                log.warning("[selgros] '%s' skip=%d failed: %s", path, skip, exc)
                break
            batch = data.get("value") or []
            docs.extend(batch)
            total = data.get("@odata.count") or 0
            skip += PAGE_SIZE
            if len(batch) < PAGE_SIZE or skip >= total:
                break
            if self.limit and len(docs) >= self.limit:
                break
        return docs

    async def scrape(self) -> list[WineProduct]:
        paths = await self._wine_category_paths()
        products: list[WineProduct] = []
        for path in paths:
            for doc in await self._fetch_path(path):
                product = self._to_product(doc)
                if product:
                    products.append(product)
            log.info("[selgros] '%s' -> %d products so far", path, len(products))
            if self.limit and len(products) >= self.limit:
                break
        return self.keep_wines(products)
