"""METRO Cash & Carry Romania — searchdiscover + betty-variants APIs.

METRO's shop (produse.metro.ro) serves an empty SPA shell to plain HTTP, but its
JSON APIs are anonymous and unprotected: one search call per wine subcategory
returns every variant id, and ``betty-variants`` hydrates them 40 at a time with
prices, characteristics and stock. No login and no browser needed — METRO gates
*ordering* behind its business accounts, not price display.

Three price traps, all verified against the rendered product page:

* The search response's ``price`` is **net (ex-VAT)** and occasionally stale —
  never use it. The detail call's ``finalPricesInfo.articleGross`` is the
  VAT-inclusive shelf price a shopper sees.
* ``sellingPriceInfo.grossPrice`` **includes the SGR bottle deposit**;
  ``articleGross`` excludes it. Using the former inflates METRO by ~0.50 lei
  per bottle against every other retailer.
* The detail endpoint intermittently returns HTTP 200 with a null
  ``sellingPriceInfo`` for an *entire* batch; an immediate retry of the same ids
  succeeds. Without the retry, ~25% of prices silently vanish on a bad run.

Prices are national (verified identical across stores), but assortment is per
store; the default store carries ~95% of the national range. METRO often sets a
minimum order of 6 bottles — kept in ``raw`` since it matters when comparing
against supermarkets. ABV and EAN are simply not published.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

from ..models import WineProduct
from ..normalize import fold, parse_colour, parse_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://produse.metro.ro"
SEARCH_URL = f"{BASE}/searchdiscover/articlesearch/search"
DETAIL_URL = f"{BASE}/evaluate.article.v1/betty-variants"

DEFAULT_STORE = "00032"           # METRO Baneasa, Bucharest — widest assortment
BATCH_SIZE = 40                   # server-enforced hard cap
BATCH_RETRIES = 3
# Wine subcategories, keyed by urlCategoryPath. The API's categoryId keys are
# scrambled against their display names (its "wines" id is soft drinks), so
# only these path strings are safe to key off.
WINE_CATEGORIES = {
    "vinuri-albe": "alb",
    "vinuri-rosii": "rosu",
    "vinuri-roze": "rose",
    "vinuri-spumante": None,      # colour varies; sparkling comes from the path
}
CATEGORY_PREFIX = "alimentare/bauturi-alcoolice-vinuri-bere"

# characteristicsTable row labels, matched after diacritic folding because the
# live labels mix U+0163/U+021B forms and a CMS edit would silently zero a field.
CH_GRAPES = "soiul de vita de vie"
CH_COUNTRY = "tara de origine"
CH_REGION = "regiunea viticola"
CH_SWEETNESS = "clasificare"
CH_VINTAGE = "an productie"
CH_PRODUCER = "crama"
CH_COLOUR = "culoare"

SWEETNESS_MAP = {
    "sec": "sec", "demisec": "demisec", "demidulce": "demidulce", "dulce": "dulce",
    "brut": "sec", "extra brut": "sec", "extra sec": "sec", "brut nature": "sec",
}


@register
class MetroAdapter(Adapter):
    key = "metro"
    label = "METRO Cash & Carry"
    catalogue = "catalogue"
    note = ("Anonymous JSON APIs, ~1,040 wines. National pricing, per-store "
            "assortment; many wines carry a 6-bottle minimum order.")

    @property
    def store_id(self) -> str:
        return str(self.config.get("store_id", DEFAULT_STORE))

    @property
    def location_name(self) -> str:
        if self.store_id == DEFAULT_STORE:
            return "metro-baneasa-00032"
        return f"metro-store-{self.store_id}"

    # ------------------------------------------------------------------ search
    async def _search_category(self, path: str) -> list[str]:
        """All variant ids in one wine subcategory."""
        ids: list[str] = []
        page = 1                                          # page=0 is an HTTP 500
        while True:
            query = urlencode({
                "storeId": self.store_id, "language": "ro-RO", "country": "RO",
                "query": "*", "rows": 1000, "page": page,
                "filter": f"category:{CATEGORY_PREFIX}/{path}",
                "facets": "false", "categories": "false",
            })
            data = await self.fetcher.get_json(f"{SEARCH_URL}?{query}")
            batch = data.get("resultIds") or []
            ids.extend(batch)
            if not batch or data.get("nextPage") is None:
                break
            page += 1
        return ids

    # ------------------------------------------------------------------ detail
    def _detail_url(self, ids: list[str]) -> str:
        params = [("storeIds", self.store_id), ("country", "RO"),
                  ("locale", "ro-RO"), ("details", "true")]
        params += [("ids", i) for i in ids]
        return f"{DETAIL_URL}?{urlencode(params)}"

    def _extract(self, data: dict) -> tuple[dict[str, tuple], list[str]]:
        """Walk a betty-variants response.

        The response is keyed by *article* number even when queried by variant
        id, so the wanted id is read back from each variant. Returns
        ``{variant_id: (article_no, variant, bundle, selling_price_info)}`` plus
        the variant ids whose price came back null and need a retry.
        """
        merged: dict[str, tuple] = {}
        null_price: list[str] = []
        for article_no, article in (data.get("result") or {}).items():
            for variant in (article.get("variants") or {}).values():
                variant_id = ((variant.get("bettyVariantId") or {})
                              .get("bettyVariantId"))
                if not variant_id:
                    continue
                for bundle in (variant.get("bundles") or {}).values():
                    store = (bundle.get("stores") or {}).get(self.store_id) or {}
                    spi = store.get("sellingPriceInfo")
                    if spi is None:
                        null_price.append(variant_id)
                    else:
                        merged[variant_id] = (article_no, variant, bundle, spi)
                    break                                  # bundles are 1:1 today
        return merged, null_price

    async def _hydrate(self, ids: list[str]) -> dict[str, tuple]:
        """Batch-fetch details, retrying the transient null-price batches."""
        merged: dict[str, tuple] = {}
        for start in range(0, len(ids), BATCH_SIZE):
            pending = ids[start:start + BATCH_SIZE]
            for attempt in range(BATCH_RETRIES):
                try:
                    # cache=False: retries must hit the server, and a cached
                    # null-price response would defeat them across runs too.
                    data = await self.fetcher.get_json(
                        self._detail_url(pending), cache=False)
                except Exception as exc:
                    log.warning("[metro] batch at %d failed: %s", start, exc)
                    break
                got, nulls = self._extract(data)
                merged.update(got)
                if not nulls:
                    break
                pending = sorted(set(nulls))
                log.info("[metro] %d null prices in batch at %d, retry %d",
                         len(pending), start, attempt + 1)
        return merged

    # ----------------------------------------------------------------- mapping
    @staticmethod
    def _characteristics(bundle: dict) -> dict[str, str]:
        table = ((bundle.get("details") or {}).get("characteristicsTable") or {})
        out: dict[str, str] = {}
        for row in table.get("rows") or []:
            label = fold(str(row.get("rowLabel") or ""))
            cells = row.get("cells") or []
            value = str((cells[0] or {}).get("value") or "").strip() if cells else ""
            if label and value and value != "-":
                out[label] = value
        return out

    @staticmethod
    def _volume_l(bundle: dict) -> float | None:
        content = (bundle.get("contentData") or {}).get("netContentVolume") or {}
        value, uom = content.get("value"), str(content.get("uom") or "").upper()
        if not isinstance(value, (int, float)) or value <= 0:
            return None
        factor = {"ML": 0.001, "CL": 0.01, "L": 1.0}.get(uom)
        return round(value * factor, 4) if factor else None

    def _to_product(self, article_no: str, variant: dict, bundle: dict,
                    spi: dict[str, Any], category: str) -> WineProduct | None:
        name = (bundle.get("description") or variant.get("description") or "").strip()
        if not name:
            return None

        final = spi.get("finalPricesInfo") or {}
        # articleGross = VAT-inclusive, deposit-exclusive: the shelf-comparable
        # figure. spi["grossPrice"] folds the deposit in — do not use it.
        price = parse_price(final.get("articleGross"))
        list_price = parse_price(spi.get("listGrossPrice"))
        if list_price is not None and price is not None and list_price <= price:
            list_price = None

        ch = self._characteristics(bundle)
        # Both the category and the Culoare characteristic carry real errors in
        # opposite directions (~1.5% of rows); the title is the most reliable
        # signal, then the category, then the characteristic.
        colour = (parse_colour(name) or WINE_CATEGORIES.get(category)
                  or ({"alb": "alb", "rosu": "rosu", "rose": "rose"}
                      .get(fold(ch.get(CH_COLOUR, "")))))
        sweetness = SWEETNESS_MAP.get(fold(ch.get(CH_SWEETNESS, "")))
        vintage = None
        if (ch.get(CH_VINTAGE) or "").strip().isdigit():
            year = int(ch[CH_VINTAGE])
            if 1950 <= year <= 2049:
                vintage = year
        grapes = [g.strip() for g in (ch.get(CH_GRAPES) or "").split(",") if g.strip()]

        availability = str(variant.get("availability")
                           or bundle.get("customerAvailability") or "")
        cats = variant.get("categories") or []
        category_path = (cats[0].get("name") if cats and isinstance(cats[0], dict)
                         else None) or f"{CATEGORY_PREFIX}/{category}"

        variant_no = next(iter(variant.get("bundles") or {"": None}))
        slug = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")[:80]

        return self.make_product(
            external_id=article_no,
            name=name,
            url=f"{BASE}/shop/pv/{article_no}/{variant_no}/"
                f"{bundle.get('bundleNumber') or '0021'}/{slug}",
            price=price,
            currency=spi.get("currency") or "RON",
            list_price=list_price,
            on_promotion=list_price is not None,
            in_stock=availability in ("AVAILABLE", "LIMITED") if availability else None,
            brand=(bundle.get("brandName") or "").strip() or None,
            producer=(ch.get(CH_PRODUCER) or "").strip() or None,
            volume_l=self._volume_l(bundle),
            colour=colour,
            sweetness=sweetness,
            # The search category is authoritative for sparkling; for the still
            # categories the title decides (enrich), since e.g. frizzante whites
            # live under vinuri-albe.
            sparkling=True if category == "vinuri-spumante" else None,
            vintage=vintage,
            country=(ch.get(CH_COUNTRY) or "").strip() or None,
            region=(ch.get(CH_REGION) or "").strip() or None,
            grape_varieties=grapes,
            category_path=category_path,
            image_url=bundle.get("imageUrl") or None,
            raw={"price_net": parse_price(final.get("articleNet")),
                 "deposit": parse_price(final.get("emptiesGross")),
                 "min_order_qty": bundle.get("minOrderQuantity"),
                 "store_id": self.store_id,
                 "customer_display_id": bundle.get("customerDisplayId")},
        )

    # ------------------------------------------------------------------ scrape
    async def scrape(self) -> list[WineProduct]:
        products: list[WineProduct] = []
        total_ids = 0
        for category in WINE_CATEGORIES:
            try:
                ids = await self._search_category(category)
            except Exception as exc:
                log.warning("[metro] search '%s' failed: %s", category, exc)
                continue
            if self.limit:
                ids = ids[:max(self.limit - len(products), 0)]
            total_ids += len(ids)
            merged = await self._hydrate(ids)
            for variant_id, (article_no, variant, bundle, spi) in merged.items():
                product = self._to_product(article_no, variant, bundle, spi, category)
                if product:
                    products.append(product)
            log.info("[metro] %s: %d ids -> %d products (total %d)",
                     category, len(ids), len(merged), len(products))
            if self.limit and len(products) >= self.limit:
                break

        # A whole batch can also drop out of _hydrate on a network error, which
        # loses products rather than prices; the search ids are the yardstick.
        self.expected_total = total_ids or None

        # The null-price transient is non-deterministic; publishing a mostly
        # price-less run would poison the history, so fail loudly instead.
        priced = sum(1 for p in products if p.price is not None)
        if total_ids and priced < 0.9 * total_ids and not self.limit:
            raise RuntimeError(
                f"only {priced}/{total_ids} wines have prices after retries — "
                "aborting rather than publishing a degraded run")
        return self.keep_wines(products)
