"""Adapter base class and registry."""

from __future__ import annotations

import logging
from typing import Iterable

from ..fetch import Fetcher
from ..models import WineProduct
from ..normalize import clean_name, enrich, looks_like_wine

log = logging.getLogger(__name__)


class SiteUnsupported(Exception):
    """Raised by adapters for retailers with no scrapable online wine catalogue."""


class Adapter:
    """One retailer.

    Subclasses implement :meth:`scrape` and yield ``WineProduct`` objects.
    ``key`` is the CLI name (``--site kaufland``).
    """

    key: str = ""
    label: str = ""
    #: "catalogue" = full shoppable range, "promo" = weekly offers only,
    #: "none" = no online wine listing at all.
    catalogue: str = "catalogue"
    #: Set when the retailer prices per store and we pin one.
    location: str | None = None
    #: Requires a headless browser session.
    needs_browser: bool = False
    #: Short note surfaced by ``list-sites``.
    note: str = ""

    #: Fraction of the retailer's reported total a run must reach to be trusted.
    MIN_COVERAGE = 0.9

    def __init__(self, fetcher: Fetcher, *, limit: int | None = None,
                 browser=None, config: dict | None = None):
        self.fetcher = fetcher
        self.limit = limit
        self.browser = browser
        self.config = config or {}
        #: How many products the retailer says the category holds, when it says.
        self.expected_total: int | None = None

    async def scrape(self) -> list[WineProduct]:  # pragma: no cover - interface
        raise NotImplementedError

    # -- helpers shared by adapters --------------------------------------
    def make_product(self, *, external_id: str, name: str, **kwargs) -> WineProduct:
        """Build a product with the retailer's identity and defaults applied."""
        kwargs.setdefault("location", self.location)
        kwargs.setdefault("offer_type", "promo" if self.catalogue == "promo" else "catalogue")
        product = WineProduct(
            retailer=self.key,
            external_id=str(external_id),
            name=clean_name(name),
            **kwargs,
        )
        enrich(product)
        return product

    def keep_wines(self, products: Iterable[WineProduct]) -> list[WineProduct]:
        """Drop non-wine items and unpriced listings, and de-duplicate by id.

        Wine aisles reliably contain corkscrews, glasses and vinegar, plus a
        long tail of wine-adjacent drinks — alcohol-free "sparkling", ready-to-
        drink spritzes, vermouth, sparkling tea and Wine Chocolate — none of
        which belong in a wine price series.

        Listings with no price are dropped too. They are almost always sold out
        (Auchan's API returns Price=0 with AvailableQuantity=0), and a row with
        no price cannot contribute to a price dataset.
        """
        products = list(products)
        # A failed page is logged and skipped so one bad response cannot lose a
        # whole run — but that also means a run can quietly return two thirds of
        # a catalogue. Comparing against the retailer's own reported total turns
        # that into a visible failure instead of a silent one.
        if (self.expected_total and not self.limit
                and len(products) < self.MIN_COVERAGE * self.expected_total):
            raise RuntimeError(
                f"{self.key}: collected {len(products)} of {self.expected_total} "
                f"listings the retailer reports ("
                f"{len(products) / self.expected_total:.0%}); refusing to publish "
                "a partial run")

        seen: set[str] = set()
        kept: list[WineProduct] = []
        dropped_not_wine = dropped_unpriced = 0
        for product in products:
            if product.external_id in seen:
                continue
            if not looks_like_wine(product.name, product.category_path):
                dropped_not_wine += 1
                log.debug("[%s] not wine: %s", self.key, product.name)
                continue
            if product.price is None:
                dropped_unpriced += 1
                log.debug("[%s] no price: %s", self.key, product.name)
                continue
            seen.add(product.external_id)
            kept.append(product)
            if self.limit and len(kept) >= self.limit:
                break
        if dropped_not_wine or dropped_unpriced:
            log.info("[%s] dropped %d non-wine and %d unpriced listings",
                     self.key, dropped_not_wine, dropped_unpriced)
        return kept


_REGISTRY: dict[str, type[Adapter]] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    if not cls.key:
        raise ValueError(f"{cls.__name__} needs a key")
    _REGISTRY[cls.key] = cls
    return cls


def get_adapter(key: str) -> type[Adapter]:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(f"unknown site '{key}'. Known: {', '.join(sorted(_REGISTRY))}") from None


def all_adapters() -> dict[str, type[Adapter]]:
    return dict(sorted(_REGISTRY.items()))


def scrapable_adapters() -> dict[str, type[Adapter]]:
    """Adapters that can actually return products."""
    return {k: v for k, v in all_adapters().items() if v.catalogue != "none"}
