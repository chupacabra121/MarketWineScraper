"""Penny (REWE Romania) — server-rendered Vue storefront.

Penny quotes two prices per product: the shelf price and a lower PENNY-card
price. We record the shelf price as ``price`` so figures stay comparable with
retailers that have no loyalty scheme, and keep the card price alongside it.
"""

from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from ..models import WineProduct
from ..normalize import fold, parse_price, parse_unit_price, parse_volume_l
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.penny.ro"
CATEGORIES = ["/categorie/vin-5732", "/categorie/sampanie-prosecco-5733"]
MAX_PAGES = 20
_ID_RE = re.compile(r"-(rr\d+)$", re.I)


@register
class PennyAdapter(Adapter):
    key = "penny"
    label = "Penny (REWE Romania)"
    catalogue = "catalogue"
    note = "Small permanent wine range; shelf price recorded, PENNY-card price kept in raw."

    def _parse_tile(self, tile) -> WineProduct | None:
        slug = tile.attributes.get("data-product-slug") or ""
        if not slug:
            return None
        match = _ID_RE.search(slug)
        external_id = match.group(1) if match else slug

        title_node = tile.css_first('[data-test="product-title"]')
        name = title_node.text(strip=True) if title_node else (
            tile.attributes.get("data-teaser-name") or "")
        if not name:
            return None
        # Deposit-scheme text is appended to the title on bottled drinks.
        name = re.sub(r"\s*GARANTIE\s+SGR[^|]*$", "", name, flags=re.I)
        name = name.rstrip(" +,-").strip()

        link = tile.css_first('[data-test="product-tile-link"]')
        url = link.attributes.get("href") if link else f"/products/{slug}"
        if url and url.startswith("/"):
            url = BASE + url.split("?")[0]

        # "750 ml" lives in the piece-description list, which is more reliable
        # than the title for volume.
        volume = None
        desc = tile.css_first('[data-test="product-information-piece-description"]')
        if desc:
            volume = parse_volume_l(desc.text(separator=" ", strip=True))

        # Penny renders two tile shapes. Loyalty products get one labelled block
        # per price ("preț fără/cu PENNY card"). Plain discounts get a single
        # unlabelled block holding the current price plus the struck-through one,
        # so the value node must be read part by part rather than as flat text.
        shelf_price = card_price = struck_price = None
        unit_price = unit = None
        for block in tile.css('[data-test="product-price-type"]'):
            label_node = block.css_first(".ws-product-price-type__price-label")
            main_node = block.css_first(".ws-product-price-value__main")
            if main_node is None:
                continue
            value = parse_price(main_node.text(strip=True))
            if value is None:
                continue
            label = fold(label_node.text(strip=True) if label_node else "")
            if "cu penny card" in label:
                card_price = value
                continue
            if shelf_price is not None:
                continue
            shelf_price = value
            after_node = block.css_first(".ws-product-price-value__after")
            if after_node:
                struck_price = parse_price(after_node.text(strip=True))
            unit_node = block.css_first('[data-test="product-price-type-label"]')
            if unit_node:
                unit_price, unit = parse_unit_price(unit_node.text(strip=True))
        if shelf_price is None:
            shelf_price = card_price
            card_price = None
        # Only treat the second figure as a former price when it is higher.
        if struck_price is not None and shelf_price is not None and struck_price <= shelf_price:
            struck_price = None

        image_node = tile.css_first("img.ws-product-image")
        image_url = None
        if image_node:
            candidate = image_node.attributes.get("src") or ""
            image_url = candidate if candidate.startswith("http") else None

        return self.make_product(
            external_id=external_id,
            name=name,
            url=url,
            price=shelf_price,
            list_price=struck_price,
            on_promotion=bool(struck_price) or (
                card_price is not None and shelf_price is not None and card_price < shelf_price),
            unit_price=unit_price,
            unit_price_unit=unit,
            volume_l=volume,
            category_path="Bauturi/Vin",
            image_url=image_url,
            raw={"loyalty_price": card_price, "slug": slug},
        )

    async def scrape(self) -> list[WineProduct]:
        products: list[WineProduct] = []
        for category in CATEGORIES:
            page = 1
            while page <= MAX_PAGES:
                url = f"{BASE}{category}" + (f"?page={page}" if page > 1 else "")
                try:
                    html = await self.fetcher.get_text(url)
                except Exception as exc:
                    log.warning("[penny] %s page %d failed: %s", category, page, exc)
                    break
                tree = HTMLParser(html)
                tiles = tree.css('[data-test="product-tile"]')
                if not tiles:
                    break
                for tile in tiles:
                    product = self._parse_tile(tile)
                    if product:
                        products.append(product)
                # Stop when the pager offers no higher page number.
                has_next = any(
                    f"page={page + 1}" in (a.attributes.get("href") or "")
                    for a in tree.css("a[href]")
                )
                log.debug("[penny] %s page %d -> %d tiles", category, page, len(tiles))
                if not has_next:
                    break
                page += 1
            if self.limit and len(products) >= self.limit:
                break
        return self.keep_wines(products)
