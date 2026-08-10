"""Mega Image — Hybris behind a GraphQL gateway and Akamai bot protection.

Plain HTTP requests are rejected with 403, so we boot a browser once to pick up
the Akamai cookies and then issue the site's own GraphQL query through the
browser's request context. We send our own query document rather than replaying
Mega Image's persisted-query hash, because that hash changes with every frontend
deploy while the schema is stable.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import WineProduct
from ..normalize import parse_price, parse_unit_price
from .base import Adapter, register

log = logging.getLogger(__name__)

BASE = "https://www.mega-image.ro"
GRAPHQL_URL = f"{BASE}/api/v1/"
CATEGORY_URL = f"{BASE}/Bauturi/Vinuri/c/009002"
WINE_CATEGORY = "009002"
PAGE_SIZE = 50

QUERY = """
query CatSearch($lang: String, $searchQuery: String, $category: String,
                $pageNumber: Int, $pageSize: Int, $filterFlag: Boolean,
                $plainChildCategories: Boolean) {
  categoryProductSearch(lang: $lang, searchQuery: $searchQuery, category: $category,
      pageNumber: $pageNumber, pageSize: $pageSize, filterFlag: $filterFlag,
      plainChildCategories: $plainChildCategories) {
    pagination { currentPage totalResults totalPages }
    products {
      code name url manufacturerName available isWine
      price {
        value formattedValue currencyIso wasPrice
        supplementaryPriceLabel2 discountedPriceFormatted
      }
      images { format url }
      stock { inStock }
    }
  }
}
"""


@register
class MegaImageAdapter(Adapter):
    key = "mega_image"
    label = "Mega Image"
    catalogue = "catalogue"
    needs_browser = True
    location = "online"
    note = "GraphQL API; needs a browser session to clear Akamai."

    def _to_product(self, doc: dict[str, Any]) -> WineProduct | None:
        code = doc.get("code")
        name = doc.get("name")
        if not code or not name:
            return None

        price_block = doc.get("price") or {}
        price = parse_price(price_block.get("value"))
        list_price = parse_price(price_block.get("wasPrice"))
        if list_price is not None and price is not None and list_price <= price:
            list_price = None

        unit_price, unit = parse_unit_price(price_block.get("supplementaryPriceLabel2") or "")

        images = doc.get("images") or []
        image_url = None
        for wanted in ("zoom", "xlarge", "respListGrid", "small"):
            match = next((i for i in images if i.get("format") == wanted), None)
            if match:
                image_url = BASE + match["url"] if match["url"].startswith("/") else match["url"]
                break

        url = doc.get("url")
        stock = doc.get("stock") or {}

        return self.make_product(
            external_id=code,
            name=name,
            url=BASE + url if url and url.startswith("/") else url,
            price=price,
            currency=price_block.get("currencyIso") or "RON",
            list_price=list_price,
            on_promotion=list_price is not None,
            unit_price=unit_price,
            unit_price_unit=unit,
            in_stock=bool(stock.get("inStock")) if stock else doc.get("available"),
            brand=(doc.get("manufacturerName") or "").strip() or None,
            image_url=image_url,
            category_path="Bauturi/Vinuri",
            raw={"isWine": doc.get("isWine")},
        )

    async def scrape(self) -> list[WineProduct]:
        if self.browser is None:
            raise RuntimeError("mega_image requires a browser session")

        await self.browser.warm_up(CATEGORY_URL)

        products: list[WineProduct] = []
        page = 0
        total_pages = 1
        while page < total_pages:
            payload = {
                "operationName": "CatSearch",
                "query": QUERY,
                "variables": {
                    "lang": "ro",
                    "searchQuery": "",
                    "category": WINE_CATEGORY,
                    "pageNumber": page,
                    "pageSize": PAGE_SIZE,
                    "filterFlag": True,
                    "plainChildCategories": True,
                },
            }
            try:
                data = await self.browser.post_json(
                    GRAPHQL_URL, payload,
                    headers={"apollographql-client-name": "ro-mi-web-stores",
                             "referer": CATEGORY_URL})
            except Exception as exc:
                log.warning("[mega_image] page %d failed: %s", page, exc)
                break

            if data.get("errors"):
                log.error("[mega_image] GraphQL error: %s", data["errors"][:1])
                break

            result = (data.get("data") or {}).get("categoryProductSearch") or {}
            pagination = result.get("pagination") or {}
            total_pages = int(pagination.get("totalPages") or 1)
            for doc in result.get("products") or []:
                product = self._to_product(doc)
                if product:
                    products.append(product)
            log.info("[mega_image] page %d/%d -> %d products",
                     page + 1, total_pages, len(products))
            page += 1
            if self.limit and len(products) >= self.limit:
                break
        return self.keep_wines(products)
