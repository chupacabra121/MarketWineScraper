"""Bolt Food storefronts — third-party delivery catalogue for brick retailers.

Some retailers with no own web shop (Kaufland first among them) list their full
range on Bolt Food. Bolt's web app talks to endpoints that are literally routed
under ``/deliveryClient/public/`` — no login, no bot wall — and one
``getMenuDishes`` call on a category returns every product in it, with price,
availability and stock quantity.

Two honest caveats, baked into how the data is recorded:

* **These are delivery-platform prices, not shelf prices.** Platforms and
  retailers commonly add a margin to in-store prices, so rows from here must
  never be silently mixed with a retailer's own shelf data. That is why this is
  a separate retailer key (``kaufland_bolt``, not ``kaufland``) and why every
  row's ``location`` names the platform and the store.
* **Assortment and prices are per store.** The default is one Bucharest store;
  ``provider_id``/``city_id`` are configurable.

The base class is store-agnostic: registering another Bolt-listed retailer is a
subclass with a different provider id.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..models import WineProduct
from ..normalize import fold, parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

API = "https://deliveryuser.live.boltsvc.net/deliveryClient/public"
# Static client identity params the API expects on every call.
CLIENT = ("version=FW.1.115&language=ro-RO&deviceType=web&device_name=web"
          "&device_os_version=web&deviceId=00000000-0000-4000-8000-000000000001")

_WINE_CATEGORY = re.compile(r"\b(vin|vinuri|spumant|spumante|sampanie|prosecco)\b")
# Fallback roots for stores whose menu buries wine inside a generic drinks
# category (Penny) instead of a top-level wine one (Kaufland).
_DRINKS_CATEGORY = re.compile(r"\b(bauturi|alcool)\w*\b")
# Kaufland's internal titles glue the deposit marker onto the volume
# ("0.75LSGR"), which defeats both the volume parser and clean_name.
_GLUED_SGR = re.compile(r"\s*SGR\s*$", re.I)


class BoltFoodStoreAdapter(Adapter):
    """One retailer's store on Bolt Food. Subclasses set the provider."""

    provider_id: int = 0
    city_id: int = 325                # Bucharest
    # Delivery point the prices are quoted for; central Bucharest by default.
    lat: float = 44.426767
    lng: float = 26.102538
    store_slug: str = ""

    @property
    def _provider(self) -> int:
        return int(self.config.get("provider_id", self.provider_id))

    def _params(self) -> str:
        lat = self.config.get("lat", self.lat)
        lng = self.config.get("lng", self.lng)
        return f"delivery_lat={lat}&delivery_lng={lng}&{CLIENT}"

    async def _get(self, endpoint: str, **params) -> dict:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{API}/{endpoint}?{query}&{self._params()}"
        data = await self.fetcher.get_json(url, headers={"Origin": "https://food.bolt.eu",
                                                         "Referer": "https://food.bolt.eu/"})
        if data.get("code") != 0:
            raise RuntimeError(f"Bolt {endpoint} -> code {data.get('code')}: "
                               f"{str(data.get('message'))[:120]}")
        return data.get("data") or {}

    @staticmethod
    def _name_of(node: dict) -> str:
        name = node.get("name")
        if isinstance(name, dict):
            name = name.get("value")
        return str(name or "").strip()

    async def _fetch_roots(self) -> list[tuple[int, bool]]:
        """Menu categories to fetch, as ``(id, is_wine_root)``.

        Prefer categories named for wine; when a store has none (Penny files
        wine under a generic "Băuturi"), fall back to drinks-named categories
        and let the per-dish leaf filter pick the wine out of them.
        """
        data = await self._get("getMenuCategories", provider_id=self._provider)
        items = data.get("items") or {}
        wine: list[int] = []
        drinks: list[int] = []
        for node in items.values():
            if node.get("type") != "category" and node.get("type") is not None:
                continue
            name = fold(self._name_of(node))
            if _WINE_CATEGORY.search(name):
                wine.append(int(node["id"]))
            elif _DRINKS_CATEGORY.search(name):
                drinks.append(int(node["id"]))
        # Keep only the topmost matches: a matched child of a matched parent
        # would be fetched twice, since getMenuDishes returns whole subtrees.
        wine_set = set(wine)
        topmost = [i for i in wine
                   if int((items.get(str(i)) or {}).get("parent_id") or 0) not in wine_set]
        if topmost:
            log.info("[%s] %d wine categories on the Bolt menu", self.key, len(topmost))
            return [(i, True) for i in topmost]
        log.info("[%s] no wine category; scanning %d drinks categories",
                 self.key, len(drinks))
        return [(i, False) for i in drinks]

    @staticmethod
    def _keep_leaf(root_is_wine: bool, leaf_name: str | None) -> bool:
        """Whether dishes under this leaf belong to the wine crawl."""
        if root_is_wine:
            return True
        return bool(leaf_name and _WINE_CATEGORY.search(fold(leaf_name)))

    def _to_product(self, dish: dict[str, Any], category_path: str | None) -> WineProduct | None:
        product_id = dish.get("product_id") or dish.get("id")
        raw_name = self._name_of(dish)
        if not product_id or not raw_name:
            return None
        name = _GLUED_SGR.sub("", raw_name).strip()

        price_block = dish.get("price") or {}
        price = parse_price(price_block.get("value"))

        images = dish.get("images") or {}
        image_url = None
        for variant in images.values():
            ratios = (variant or {}).get("aspect_ratio_map", {}).get("original", {})
            image_url = next((u for u in ratios.values() if u), None)
            if image_url:
                break

        return self.make_product(
            external_id=product_id,
            name=name,
            url=(f"https://food.bolt.eu/ro-ro/{self.city_id}-bucharest/p/"
                 f"{self._provider}-{self.store_slug}/"),
            price=price,
            currency=(price_block.get("currency") or "ron").upper(),
            in_stock=dish.get("availability") == "in_stock",
            category_path=category_path,
            image_url=image_url,
            raw={"source": "bolt-food", "bolt_menu_id": dish.get("id"),
                 "available_quantity": dish.get("available_quantity"),
                 "deposit_key": dish.get("fee_info_key")},
        )

    async def scrape(self) -> list[WineProduct]:
        products: list[WineProduct] = []
        for category_id, is_wine_root in await self._fetch_roots():
            try:
                data = await self._get("getMenuDishes",
                                       provider_id=self._provider, category_id=category_id)
            except Exception as exc:
                log.warning("[%s] category %s failed: %s", self.key, category_id, exc)
                continue
            items = data.get("items") or {}
            # Leaf category names give the normaliser its context ("Vin spumant"
            # marks sparkling wines whose titles never say so).
            category_names = {int(v["id"]): self._name_of(v)
                              for v in items.values() if v.get("type") == "category"}
            for node in items.values():
                if node.get("type") != "dish":
                    continue
                leaf = category_names.get(int(node.get("parent_id") or 0))
                if not self._keep_leaf(is_wine_root, leaf):
                    continue
                path = f"Vin/{leaf}" if leaf and fold(leaf) != "vin" else "Vin"
                product = self._to_product(node, path)
                if product:
                    products.append(product)
            log.info("[%s] category %s -> %d products so far",
                     self.key, category_id, len(products))
            if self.limit and len(products) >= self.limit:
                break
        return self.keep_wines(products)


@register
class KauflandBoltAdapter(BoltFoodStoreAdapter):
    key = "kaufland_bolt"
    label = "Kaufland via Bolt Food"
    catalogue = "catalogue"
    provider_id = 170782              # Kaufland Tei (2600), Bucharest
    store_slug = "kaufland-tei-2600"
    location = "bolt-food/kaufland-tei-2600"
    note = ("Full Kaufland range (~700 wines) through Bolt Food. Delivery-platform "
            "prices — typically at or above shelf; kept separate from 'kaufland'.")


@register
class PennyBoltAdapter(BoltFoodStoreAdapter):
    key = "penny_bolt"
    label = "Penny via Bolt Food"
    catalogue = "catalogue"
    provider_id = 138503              # PENNY Nasaud (4343), Bucharest
    store_slug = "penny-nasaud-4343"
    location = "bolt-food/penny-nasaud-4343"
    note = ("~70 wines vs ~36 on penny.ro. Measured against penny.ro shelf "
            "prices: identical on most overlapping wines (median +0.0%), so this "
            "mainly buys assortment; differences reflect promo timing.")
