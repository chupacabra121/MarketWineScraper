"""One class per German retailer.

Each source knows how to reach its own catalogue and how to read a listing out
of it; everything after that — packaging, Pfand, per-litre — is shared and lives
in :mod:`.packaging`, :mod:`.parse` and :mod:`.model`.

**Why these retailers.** The brief is PET and bag-in-box wine in German stores,
so every chain on Wikipedia's *List of supermarket chains in Germany* was
checked one by one, plus the beverage chains and wine specialists that list the
formats. The sources below are the ones that publish a price to an anonymous
visitor.

The rest are in :data:`UNAVAILABLE` with the reason, because three quite
different facts all look like an empty row otherwise. Kaufland and REWE have
catalogues and refuse datacentre addresses. Getränke Hoffmann, trinkgut and
Fristo — where bag-in-box sells hardest — publish no prices anywhere on the web.
And most of the rest, ALDI Nord and Penny and tegut and famila among them, run a
store finder and a weekly leaflet and have no online catalogue at all. That last
group is the majority, and it is a finding about German grocery retail rather
than an obstacle to scraping it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable
from urllib.parse import quote, urljoin

from selectolax.parser import HTMLParser

from . import packaging as pkg
from . import parse as P
from .fetch import Fetcher
from .model import Listing

log = logging.getLogger(__name__)

#: Distinguishes "the source passed no volume" from "the source passed None".
_UNSET = object()

_REGISTRY: dict[str, type["Source"]] = {}


def register(cls: type["Source"]) -> type["Source"]:
    _REGISTRY[cls.key] = cls
    return cls


def all_sources() -> dict[str, type["Source"]]:
    return dict(sorted(_REGISTRY.items()))


#: Every chain on Wikipedia's *List of supermarket chains in Germany* that
#: yields no data, and why. Carried into the workbook so a reader can tell "does
#: not stock the format" from "does not publish prices" from "blocked us" —
#: three different facts that all look like an empty row otherwise.
#:
#: The dominant reason is not bot protection. Most German grocery chains simply
#: have no online catalogue at all: they run a store finder and a weekly leaflet,
#: and the price exists only on the shelf. That is the finding, not the obstacle.
UNAVAILABLE = [
    # --- blocked: catalogue exists, refuses datacentre addresses -------------
    ("kaufland", "Kaufland", "supermarkt", "blockiert",
     "kaufland.de answers HTTP 403 'Zugriff blockiert' to datacentre addresses, "
     "over plain HTTP and through a real Chromium alike. Carries a wide "
     "bag-in-box range in store."),
    ("rewe", "REWE", "supermarkt", "blockiert",
     "shop.rewe.de answers HTTP 403 to datacentre addresses. Lists bag-in-box "
     "under Wein > Weinschlauch in its delivery shop."),
    ("marktkauf", "Marktkauf", "supermarkt", "blockiert",
     "HTTP 403 to datacentre addresses on every path below the homepage."),
    ("aldi_sued", "ALDI SÜD", "discounter", "blockiert",
     "aldi-sued.de answers HTTP 403 to datacentre addresses."),
    ("hawesko", "Hawesko", "fachhandel", "blockiert",
     "HTTP 403 to datacentre addresses. Runs a dedicated /baginbox/ range."),
    ("vinatis", "Vinatis", "fachhandel", "blockiert",
     "HTTP 403 to datacentre addresses."),

    # --- no online prices at all --------------------------------------------
    ("aldi_nord", "ALDI Nord", "discounter", "keine Preise online",
     "Site reachable and lists the assortment by category, but publishes no "
     "product prices outside the weekly leaflet."),
    ("penny", "Penny", "discounter", "keine Preise online",
     "penny.de serves offers and a store finder; the assortment pages carry no "
     "prices and no wine catalogue."),
    ("tegut", "tegut…", "supermarkt", "keine Preise online",
     "Product pages are editorial. No shoppable wine range."),
    ("hit", "HIT (Dohle)", "supermarkt", "keine Preise online",
     "Assortment pages are editorial; prices appear only in the leaflet."),
    ("famila", "famila", "supermarkt", "keine Preise online",
     "Both famila Nordost and Nordwest run store-finder sites. Sister format to "
     "Combi, whose shop is in the study and carries the group's range."),
    ("selgros", "Selgros", "cash_and_carry", "keine Preise online",
     "Assortment described editorially; no anonymous price display, unlike "
     "METRO."),
    ("netto_salling", "Netto (Salling, schwarz-gelb)", "discounter",
     "keine Preise online",
     "Leaflet and store finder only."),
    ("norma_stores", "NORMA (Filialen)", "discounter", "keine Preise online",
     "norma-online.de shows the weekly leaflet; the shoppable range is the "
     "separate norma24.de, which is in the study."),
    ("alnatura", "Alnatura", "bio", "keine Preise online",
     "Product pages describe the range without prices; sold through partner "
     "retailers."),
    ("biocompany", "Bio Company", "bio", "keine Preise online",
     "Store finder and editorial assortment pages."),
    ("cap", "CAP Markets", "supermarkt", "keine Preise online",
     "Store finder; no catalogue."),
    ("nahkauf", "nahkauf", "supermarkt", "keine Preise online",
     "REWE-owned franchise banner; store finder only."),
    ("nah_und_gut", "nah & gut", "supermarkt", "keine Preise online",
     "EDEKA franchise banner; the domain serves a redirect stub."),
    ("nah_und_frisch", "nah & frisch", "supermarkt", "keine Preise online",
     "Bela-owned banner; market picker, no catalogue."),
    ("spar_express", "SPAR express", "convenience", "nicht erreichbar",
     "spar.de did not resolve through the egress proxy."),
    ("getraenke_hoffmann", "Getränke Hoffmann", "getraenkemarkt",
     "keine Preise online",
     "Store-locator site with a weekly leaflet; no shoppable catalogue and no "
     "prices on the web at all."),
    ("trinkgut", "trinkgut (EDEKA)", "getraenkemarkt", "keine Preise online",
     "Store-locator site, no online prices. Its search returns no products."),
    ("fristo", "Fristo Getränkemarkt", "getraenkemarkt", "keine Preise online",
     "Leaflet-only site, no product catalogue."),

    # --- reachable, but the prices are not in the response -------------------
    ("vinello", "Vinello", "fachhandel", "Preise clientseitig",
     "Category page lists 59 bag-in-box wines but server-renders a price for "
     "only 3 of them; product pages answer HTTP 410 Gone. A 3-of-59 sample is "
     "not a price point, so the shop is left out rather than part-counted."),
    ("amazon", "Amazon.de", "online", "Preise clientseitig",
     "Search returns the products but strips every price from the response to "
     "an unauthenticated client."),
    ("mueller", "Müller", "drogerie", "Preise clientseitig",
     "Carries bag-in-box; the listing renders its prices client-side and the "
     "HTML holds none."),
]


class Source:
    """One retailer's catalogue."""

    key: str = ""
    label: str = ""
    #: Where in German retail this sits — the axis price points differ along.
    channel: str = "fachhandel"
    #: gross = VAT-inclusive consumer price; net = ex-VAT trade price.
    price_basis: str = "gross"
    note: str = ""

    def __init__(self, fetcher: Fetcher, *, limit: int | None = None):
        self.fetcher = fetcher
        self.limit = limit

    async def scrape(self) -> list[Listing]:      # pragma: no cover - interface
        raise NotImplementedError

    # -- shared helpers ---------------------------------------------------
    def build(self, *, external_id: str, name: str, description: str = "",
              category: str = "", **kwargs) -> Listing:
        """Assemble a listing and derive everything readable from its text.

        Packaging is classified from title, description and category together,
        because the sources disagree about where they put the word: Lidl puts
        "Bag-in-Box" in the title but names its cartons only in the image alt
        text, and Schäpers repeats the format in the description.
        """
        text = f"{name} {description}"
        # A source that names the field is believed, even when its answer is
        # None. Re-deriving on None cannot tell "did not look" from "looked and
        # found nothing", and the difference is a wrong number: Combi mistypes
        # one listing's size as "750 l", which is correctly rejected, and the
        # fallback then read the "/1 l" of the unit price as a one-litre bottle.
        volume = kwargs.pop("volume_l", _UNSET)
        if volume is _UNSET:
            volume = P.parse_volume_l(text)
        container = kwargs.pop("packaging", None)
        if container is None:
            container = pkg.classify(name, description=description,
                                     volume_l=volume, category=category)
        listing = Listing(
            retailer=self.key,
            retailer_label=self.label,
            channel=self.channel,
            price_basis=self.price_basis,
            external_id=str(external_id),
            name=re.sub(r"\s+", " ", name).strip(),
            packaging=container,
            packaging_evidence=self._evidence(text, category),
            volume_l=volume,
            pack_count=kwargs.pop("pack_count", None) or P.parse_pack_count(text),
            category_path=category or None,
            **kwargs,
        )
        listing.product_type = P.parse_product_type(text)
        listing.colour = listing.colour or P.parse_colour(text)
        listing.sweetness = listing.sweetness or P.parse_sweetness(text)
        listing.abv = listing.abv if listing.abv is not None else P.parse_abv(text)
        listing.vintage = listing.vintage or P.parse_vintage(name)
        listing.country = listing.country or P.parse_country(text)
        listing.region = listing.region or P.parse_region(text)
        listing.grape_varieties = listing.grape_varieties or P.parse_grapes(text)
        return listing

    @staticmethod
    def _evidence(text: str, category: str) -> str:
        """The packaging words actually present, so a classification is auditable."""
        folded = pkg.fold(f"{text} {category}")
        words = ("bag in box", "bib", "wein schlauch", "weinschlauch", "wein box",
                 "bordeaux box", "cubi", "pet", "kunststoff flasche",
                 "plastik flasche", "tetra pak", "getranke karton", "beutel",
                 "dose", "glas flasche", "bocksbeutel", "zapfhahn", "fasswein")
        return ", ".join(w for w in words if w in folded)

    def keep_wines(self, listings: Iterable[Listing]) -> list[Listing]:
        """Drop non-wine and unpriced rows, and de-duplicate by id."""
        seen: set[str] = set()
        kept: list[Listing] = []
        dropped_not_wine = dropped_unpriced = 0
        for listing in listings:
            if listing.external_id in seen:
                continue
            if not P.looks_like_wine(listing.name, listing.category_path or ""):
                dropped_not_wine += 1
                continue
            if listing.price is None:
                dropped_unpriced += 1
                continue
            seen.add(listing.external_id)
            kept.append(listing)
        if dropped_not_wine or dropped_unpriced:
            log.info("[%s] dropped %d non-wine, %d unpriced",
                     self.key, dropped_not_wine, dropped_unpriced)
        return kept


# --------------------------------------------------------------------------
# Lidl — the reference discounter
# --------------------------------------------------------------------------
@register
class LidlSource(Source):
    """Lidl Deutschland, via the public search API behind lidl.de/q.

    The API is anonymous and complete, but it answers only over HTTP/2 with
    browser headers — see :mod:`.fetch`. Two things make it the best source in
    this study: it states the container in the product title itself
    ("3-l-Bag-in-Box"), and it publishes its own price per litre, which gives an
    independent check on every volume parsed out of a title.

    The catalogue is reached by union rather than by one call. A plain
    ``q=wein`` sweep returns 862 products but its relevance ranking drops most
    of the boxes past the first few hundred, so the size facet
    (``Flaschengröße``) is queried directly for the large formats and the
    packaging words are searched for by name. Whatever the route, each product
    arrives with the same payload and is de-duplicated on its ``code``.
    """

    key = "lidl"
    label = "Lidl"
    channel = "discounter"
    note = "Public search API; container stated in the product title."

    BASE = "https://www.lidl.de/q/api/search"
    COMMON = {"assortment": "DE", "locale": "de_DE", "version": "2.0.0"}
    PAGE = 100

    #: Searched by name — these bring back the containers the study is about.
    QUERIES = ("bag in box wein", "weinschlauch", "wein bag-in-box",
               "wein pet flasche", "wein tetra pak", "wein karton",
               "sangria bag in box", "wein 3 liter", "wein 5 liter",
               "wein 1 liter", "wein")

    #: Queried as a facet on top of a plain wine search: the large formats are
    #: where bag-in-box lives, and the facet reaches them regardless of ranking.
    SIZES = ("1,0 Liter", "1,5 Liter", "3,0 Liter", "5,0 Liter")

    async def _search(self, params: dict) -> list[dict]:
        """One query, paged to exhaustion."""
        out: list[dict] = []
        offset = 0
        while True:
            query = {**self.COMMON, **params, "offset": offset, "fetchsize": self.PAGE}
            try:
                data = await self.fetcher.get_json(
                    self.BASE, params=query, referer="https://www.lidl.de/")
            except Exception as exc:                      # noqa: BLE001
                log.warning("[lidl] %s failed: %s", params, exc)
                break
            items = data.get("items") or []
            out.extend(items)
            total = data.get("numFound") or 0
            offset += self.PAGE
            # The API caps a result set at 1000 and returns fewer rows per page
            # than asked for when variants collapse, so stop on either signal.
            if not items or offset >= min(total, 1000):
                break
        return out

    async def scrape(self) -> list[Listing]:
        raw: dict[str, dict] = {}
        for query in self.QUERIES:
            for item in await self._search({"q": query}):
                code = item.get("code")
                if code:
                    raw.setdefault(str(code), item)
            if self.limit and len(raw) >= self.limit * 4:
                break
        for size in self.SIZES:
            for item in await self._search({"q": "wein", "Flaschengröße": size}):
                code = item.get("code")
                if code:
                    raw.setdefault(str(code), item)

        log.info("[lidl] %d distinct products across %d queries",
                 len(raw), len(self.QUERIES) + len(self.SIZES))
        return self.keep_wines(self._to_listing(c, i) for c, i in raw.items())

    def _to_listing(self, code: str, item: dict) -> Listing:
        data = (item.get("gridbox") or {}).get("data") or {}
        price = data.get("price") or {}
        keyfacts = data.get("keyfacts") or {}

        title = data.get("fullTitle") or data.get("title") or ""

        # Lidl states the pack size structurally, which beats reading it off the
        # title — "3-l-Bag-in-Box" and "6 x 0,75-l-Flasche" both parse, but the
        # structural field is right on the handful that word it unusually.
        #
        # It is the size of the whole *pack*, though: a six-bottle Bordeaux case
        # comes back as 4.5 litres. Dividing by the pack count is what keeps that
        # case out of the large-format sample and its price per litre honest.
        packaging_field = price.get("packaging") or {}
        pack_count = P.parse_pack_count(title)
        volume = None
        if str(packaging_field.get("unit") or "").lower() == "l":
            amount = packaging_field.get("amount")
            if isinstance(amount, (int, float)) and 0.1 <= amount <= 20:
                volume = round(float(amount) / max(pack_count, 1), 4)

        base = price.get("basePrice") or {}
        unit_price = base.get("price") if str(base.get("unit") or "").lower() == "l" else None

        # The image's accessibility text is the only place Lidl names the
        # container for its carton wines — the title says "1,5-l-Packung" and
        # the alt text says "Eine Karton Rosewein". Folded into the description
        # so the classifier sees it; the title still decides where both speak.
        alt = " ".join(
            str((image or {}).get("accessibility") or "")
            for image in (data.get("imageList_V1") or []))
        description = " ".join((
            re.sub(r"<[^>]+>", " ", keyfacts.get("supplementalDescription") or ""),
            alt,
        )).strip()
        path = data.get("canonicalPath") or ""

        return self.build(
            external_id=code,
            name=title,
            description=description,
            category=data.get("category") or "",
            url=urljoin("https://www.lidl.de", path) if path else None,
            price=P.parse_price(price.get("price")),
            unit_price=P.parse_price(unit_price),
            volume_l=volume,
            pack_count=pack_count,
            brand=(data.get("brand") or {}).get("id") or None,
            in_stock=bool(data.get("havingPrice")),
            image_url=data.get("image") or None,
            raw={"erp": data.get("erpNumber"), "category": data.get("category")},
        )


# --------------------------------------------------------------------------
# Shopware storefronts
# --------------------------------------------------------------------------
class ShopwareSource(Source):
    """Shared scaffolding for the Shopware shops.

    Shopware 5 and 6 differ in their class names but not in their shape: a
    listing page holds a repeated product box carrying a title, a link, a price
    and — for wine, near-universally — a per-litre reference price. Subclasses
    supply the selectors and the page URL; everything else is common.
    """

    START_URL: str = ""
    #: Several category URLs, for shops that split wine by colour. Overrides
    #: START_URL when set.
    START_URLS: tuple[str, ...] = ()
    PAGES: int = 6
    BOX_SELECTOR: str = ""
    PAGE_PARAM: str = "p"

    def categories(self) -> tuple[str, ...]:
        return self.START_URLS or ((self.START_URL,) if self.START_URL else ())

    def page_url(self, base: str, page: int) -> str:
        joiner = "&" if "?" in base else "?"
        return f"{base}{joiner}{self.PAGE_PARAM}={page}"

    async def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_titles: set[str] = set()
        for base in self.categories():
            for page in range(1, self.PAGES + 1):
                try:
                    html = await self.fetcher.get_text(self.page_url(base, page))
                except Exception as exc:                  # noqa: BLE001
                    log.warning("[%s] %s page %d failed: %s", self.key, base, page, exc)
                    break
                boxes = HTMLParser(html).css(self.BOX_SELECTOR)
                if not boxes:
                    break
                fresh = 0
                for box in boxes:
                    listing = self.read_box(box)
                    if listing is None:
                        continue
                    # Shopware answers an out-of-range page with the last one
                    # again, so a page that adds nothing new is the end of the
                    # listing — and the only reliable stop signal, since the
                    # shops do not all publish a page count.
                    if listing.name in seen_titles:
                        continue
                    seen_titles.add(listing.name)
                    listings.append(listing)
                    fresh += 1
                if page == 1 or not fresh or page % 10 == 0:
                    log.info("[%s] %s page %d: %d boxes, %d new",
                             self.key, base.rsplit("/", 2)[-2] if "/" in base else base,
                             page, len(boxes), fresh)
                if not fresh:
                    break
                if self.limit and len(listings) >= self.limit:
                    break
            if self.limit and len(listings) >= self.limit:
                break
        return self.keep_wines(listings)

    def read_box(self, box) -> Listing | None:  # pragma: no cover - interface
        raise NotImplementedError

    # -- text helpers -----------------------------------------------------
    @staticmethod
    def text_of(node) -> str:
        return re.sub(r"\s+", " ", node.text(separator=" ")).strip() if node else ""

    #: "3,66 € * / 1 l", "3,46 €/L", "(3,66 € / 1 Liter)" — one figure written
    #: several ways, and the only independent check on a parsed volume.
    _PER_LITRE = re.compile(
        r"(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*\*?\s*/\s*(?:1\s*)?(?:l\b|liter\b)", re.I)

    @classmethod
    def per_litre(cls, text: str) -> float | None:
        match = cls._PER_LITRE.search(text.replace("\xa0", " "))
        return float(match.group(1).replace(",", ".")) if match else None

    #: The first price in a block is the current one; a struck-through original
    #: may precede it, so the *last* two-decimal figure before the euro sign is
    #: not safe to take — the layout order is.
    _PRICE = re.compile(r"(\d{1,4}(?:[.\s]\d{3})?,\d{2})\s*€")

    @classmethod
    def prices_in(cls, text: str) -> list[float]:
        return [float(m.replace(".", "").replace(" ", "").replace(",", "."))
                for m in cls._PRICE.findall(text.replace("\xa0", " "))]


class Shopware6Source(ShopwareSource):
    """The stock Shopware 6 listing box, which several of these shops ship as-is.

    Its markup is worth stating once because the price layout is a trap: the
    price and the per-litre reference sit in separate sibling elements, and
    reading the cheaper number out of the combined block silently records a
    3-litre box at its litre price. Each is read from its own element, and the
    size comes from ``.price-unit-content`` ("Inhalt: 3 Liter") rather than
    from the title.
    """

    BOX_SELECTOR = "div.product-box, .card.product-box"
    CATEGORY = ""

    def read_box(self, box) -> Listing | None:
        anchor = box.css_first("a.product-name") or box.css_first(".product-name a")
        name = ((anchor.attributes.get("title") if anchor else None)
                or self.text_of(box.css_first(".product-name"))).strip()
        if not name:
            return None
        prices = self.prices_in(self.text_of(box.css_first(".product-price")))
        if not prices:
            return None
        # The per-litre reference lives in .price-unit-reference on some builds
        # and only in the enclosing .product-price-unit on others — Globus
        # renders the outer element and leaves the inner one empty. Falling back
        # matters more than it looks: the reference is the only independent
        # check on a parsed price, and without it the largest source in the
        # study would go unverified.
        reference = (self.text_of(box.css_first(".price-unit-reference"))
                     or self.text_of(box.css_first(".product-price-unit")))
        unit_price = self.per_litre(reference)
        # ".price-unit-content" holds "Inhalt: 3 Liter"; Globus writes the size
        # into the same element as the reference, so read that as a fallback.
        volume = (P.parse_volume_l(self.text_of(box.css_first(".price-unit-content")))
                  or P.parse_volume_l(reference.split("(")[0]))

        price, was = self._current_price(prices, unit_price, volume)
        if was is None:
            explicit = self.prices_in(self.text_of(box.css_first(".product-list-price")))
            was = explicit[0] if explicit and explicit[0] > price else None

        link = anchor.attributes.get("href") if anchor else None
        if not link:
            image_link = box.css_first("a.product-image-link")
            link = image_link.attributes.get("href") if image_link else None

        return self.build(
            external_id=link or name,
            name=name,
            description=self.text_of(box)[:400],
            category=self.CATEGORY,
            url=link,
            price=price,
            list_price=was,
            on_promotion=was is not None,
            unit_price=unit_price,
            volume_l=volume,
            # Shopware's "Inhalt" is the whole pack — a six-bottle case reads
            # 4,5 l — so the pack count must not divide it a second time. The
            # name still says "6x 0,750", which is what marks the row as a pack
            # on the format sheet.
            pack_count=1,
        )

    @staticmethod
    def _current_price(prices: list[float], unit_price: float | None,
                       volume_l: float | None) -> tuple[float, float | None]:
        """Which of the prices in the block is the one being charged.

        A discounted Globus listing renders both numbers inside a single
        ``.product-price`` — "3,49 € 2,49 €", struck-through first — so taking
        the first is wrong on exactly the rows where being wrong matters most.

        Rather than trusting the order, the retailer's own price per litre
        decides: the current price is the one that reproduces it. That is the
        same figure the data checks use to verify the result, so a row that
        passes here passes for a reason rather than by construction. Where the
        shop publishes no reference, the order is the fallback — Shopware puts
        the former price first.
        """
        if len(prices) == 1:
            return prices[0], None
        if unit_price and volume_l:
            current = min(prices, key=lambda p: abs(p / volume_l - unit_price))
        else:
            current = prices[-1]
        higher = [p for p in prices if p > current]
        return current, max(higher) if higher else None


@register
class GlobusSource(Shopware6Source):
    """Globus — hypermarket chain, full wine catalogue on Shopware 6.

    The largest single source in the study and the only full supermarket
    catalogue reachable: roughly 2,900 wines across four colour categories,
    every one with a price and a per-litre reference. It is also the only
    retailer here whose bag-in-box range has to be found rather than filtered
    for — Globus files boxes in the ordinary colour categories and marks them
    only by writing "BIB" into the product name, so the whole catalogue is
    paged and the classifier picks them out.

    The site's own search is not usable: a query for "bag-in-box" comes back
    with a coconut drink. Paging the categories is both more reliable and what
    gives the study its denominator — how much of a real supermarket wine
    range is in a box.
    """

    key = "globus"
    label = "Globus"
    channel = "supermarkt"
    note = ("Full wine catalogue (~2,900 wines) on Shopware 6; boxes marked "
            "'BIB' in the product name.")

    BASE = "https://produkte.globus.de/getraenke"
    START_URLS = (
        f"{BASE}/wein/rotwein/",
        f"{BASE}/wein/weisswein/",
        f"{BASE}/wein/rosewein/",
        f"{BASE}/wein/sonstige-weine/",
        # Boxes of Glühwein sit outside the wine tree, under Fruchtwein.
        f"{BASE}/fruchtwein/gluehwein-punsch/",
    )
    # 24 products a page, and the biggest category holds 1,636.
    PAGES = 80
    CATEGORY = "getraenke/wein"


@register
class SchaepersSource(Shopware6Source):
    """Wein Schäpers — Shopware 6, bag-in-box category, 48 per page."""

    key = "schaepers"
    label = "Wein Schäpers"
    channel = "fachhandel"
    note = "Bag-in-Box category; description repeats the format."

    START_URL = "https://wein-schaepers.de/bag-in-box/?limit=48"
    PAGES = 5
    BOX_SELECTOR = "div.product-box"
    CATEGORY = "bag-in-box"


@register
class WirWinzerSource(ShopwareSource):
    """WirWinzer — direct-from-grower marketplace, bag-in-box category.

    Sells boxes in multi-packs ("4er Paket Riesling Bag-in-Box", 12 L total), so
    the pack count matters here more than anywhere else: the advertised price is
    for the pack, and dividing it by one box's volume would overstate the price
    per litre fourfold. ``data-bottle-count`` gives the count structurally.
    """

    key = "wirwinzer"
    label = "WirWinzer"
    channel = "fachhandel"
    note = "Winery-direct marketplace; boxes sold in multi-packs."

    START_URL = "https://wirwinzer.de/weine/bag-in-box-weinschlauch"
    PAGES = 6
    BOX_SELECTOR = "div.product-box"

    def read_box(self, box) -> Listing | None:
        name = self.text_of(box.css_first(".ww-wine-name"))
        if not name:
            return None
        price_text = self.text_of(box.css_first(".ww-wine-price-container")) or self.text_of(box)
        current = self.text_of(box.css_first(".ww-wine-current-price"))
        prices = self.prices_in(current) or self.prices_in(price_text)
        if not prices:
            return None
        original = self.prices_in(self.text_of(box.css_first(".ww-wine-original-price")))

        # data-bottle-count sits on the quantity selector inside the card, not
        # on the card itself. Read off the card it is always absent, every pack
        # counts as one container, and a "4er Paket ... 12 L" is recorded as a
        # twelve-litre box that does not exist.
        counter = (box.css_first("[data-bottle-count]")
                   if box.attributes.get("data-bottle-count") is None else box)
        count = counter.attributes.get("data-bottle-count") if counter else None
        stated_count = int(count) if count and count.isdigit() else 1

        # The per-litre figure is printed alongside the total volume — "3,46 €/L
        # (12 L)" — so a single box is that total over the number of boxes.
        total_volume = None
        volume_match = re.search(r"\((\d{1,3}(?:[.,]\d)?)\s*L\)", price_text, re.I)
        if volume_match:
            total_volume = float(volume_match.group(1).replace(",", "."))

        # But the field counts *bottles*, not always boxes, and which one it
        # means varies by listing: "4er Paket ... (12 L)" reports 4, giving a
        # 3-litre box, while "BiB-Paket ... (9 L)" reports 12, which is 9 litres
        # expressed in 0.75-litre bottle equivalents. Dividing blindly turns the
        # second into a 0.75-litre bag-in-box, which does not exist.
        #
        # So the count is trusted only when it divides out to something that
        # could be a box. When it does not, the split is unknown: the pack is
        # recorded whole, which keeps the price per litre exact and leaves the
        # container size unclaimed rather than invented.
        volume, pack_count = total_volume, 1
        if total_volume and stated_count > 1:
            candidate = round(total_volume / stated_count, 4)
            if candidate >= 1.0:
                volume, pack_count = candidate, stated_count
        if volume is None:
            volume = P.parse_volume_l(name)

        anchor = box.css_first("a.ww-wine-stretched-link") or box.css_first("a")
        link = anchor.attributes.get("href") if anchor else None

        return self.build(
            external_id=box.attributes.get("data-product-number") or name,
            name=name,
            category="bag-in-box",
            url=urljoin("https://wirwinzer.de", link) if link else None,
            price=prices[0],
            list_price=original[0] if original and original[0] > prices[0] else None,
            on_promotion=bool(original and original[0] > prices[0]),
            unit_price=self.per_litre(price_text),
            volume_l=volume,
            pack_count=pack_count,
            packaging=pkg.BAG_IN_BOX,
        )


@register
class NormaSource(ShopwareSource):
    """NORMA, through its online shop norma24.de.

    The second discounter in the study, and the one that makes Lidl's numbers
    mean something: two discounters agreeing on where the entry price sits is
    an observation, one is an anecdote.

    Its listing carries schema.org microdata, so the price comes from
    ``itemprop="price"`` as a machine-readable decimal rather than out of
    rendered text — the only source here that needs no currency parsing at all.
    """

    key = "norma"
    label = "NORMA (norma24)"
    channel = "discounter"
    note = "Online shop; schema.org microdata gives price and SKU structurally."

    START_URL = "https://www.norma24.de/de/c/weine-1926"
    PAGE_PARAM = "page"
    PAGES = 12
    BOX_SELECTOR = "article.product-item__container"

    def read_box(self, box) -> Listing | None:
        name = self.text_of(box.css_first(".js-product-item__name"))
        if not name:
            return None

        def _prop(prop: str) -> str | None:
            node = box.css_first(f'[itemprop="{prop}"]')
            if node is None:
                return None
            return node.attributes.get("content") or self.text_of(node) or None

        price = P.parse_price(_prop("price"))
        if price is None:
            return None

        # "Inhalt: 0,75 Liter (3,32* / Liter)" — size and unit price together.
        unit_text = self.text_of(box.css_first(".product-item__unit-base-price"))
        volume = P.parse_volume_l(unit_text)
        unit_match = re.search(r"\(\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*\*?\s*/\s*Liter",
                               unit_text, re.I)
        unit_price = float(unit_match.group(1).replace(",", ".")) if unit_match else None

        link = box.parent.attributes.get("data-url") if box.parent else None
        if not link:
            anchor = box.css_first("a")
            link = anchor.attributes.get("href") if anchor else None

        return self.build(
            external_id=_prop("sku") or link or name,
            name=name,
            description=self.text_of(box)[:400],
            category="weine",
            url=urljoin("https://www.norma24.de", link) if link else None,
            price=price,
            unit_price=unit_price,
            volume_l=volume,
        )


@register
class NettoSource(ShopwareSource):
    """Netto Marken-Discount, through its Intershop catalogue endpoint.

    Reaching it took two steps that are worth recording, because the obvious
    reading of either would have written Netto off. Every path under
    netto-online.de answers HTTP 403 to a cold request, but the homepage does
    not: it sets six cookies, and with those in hand the catalogue opens
    normally. And the wine category renders only 58 of its 305 products, paging
    the rest through an Intershop ``ViewMMPStandardCatalog-Browse`` call that
    the page embeds — which accepts ``PageSize=500`` and returns the whole
    category in one response.

    Prices are split across spans in the markup ("11" and "49" in separate
    elements) so the text has its whitespace stripped before parsing rather
    than being read as written.
    """

    key = "netto"
    label = "Netto Marken-Discount"
    channel = "discounter"
    note = ("Intershop catalogue endpoint, whole wine category in one call. "
            "Needs the homepage's session cookies first.")

    HOME = "https://www.netto-online.de/"
    CATEGORY_URL = "https://www.netto-online.de/alle-weine/c-S010604"
    BROWSE = ("https://www.netto-online.de/INTERSHOP/web/WFS/Plus-NettoDE-Site/"
              "de_DE/-/EUR/ViewMMPStandardCatalog-Browse")
    #: The "alle Weine" node and the context UUID the storefront passes with it.
    CATEGORY = "S010604"
    CONTEXT_UUID = "Ib6sEClWJUcAAAFbLbJb7V0A"
    PAGE_SIZE = 500
    BOX_SELECTOR = "div.product"

    def catalogue_url(self) -> str:
        parameter = f"&@QueryTerm=*&ContextCategoryUUID={self.CONTEXT_UUID}"
        return (f"{self.BROWSE}?PageSize={self.PAGE_SIZE}&SortingAttribute="
                f"&CategoryName={self.CATEGORY}"
                f"&SearchParameter={quote(parameter, safe='')}&CatalogID=Basis")

    async def scrape(self) -> list[Listing]:
        # The homepage is fetched for its cookies, not its content; without it
        # the catalogue call is a 403.
        try:
            await self.fetcher.get_text(self.HOME)
        except Exception as exc:                          # noqa: BLE001
            log.warning("[netto] homepage failed, continuing: %s", exc)
        try:
            html = await self.fetcher.get_text(
                self.catalogue_url(), headers={"Referer": self.CATEGORY_URL,
                                               "Sec-Fetch-Site": "same-origin"})
        except Exception as exc:                          # noqa: BLE001
            log.error("[netto] catalogue failed: %s", exc)
            return []
        boxes = HTMLParser(html).css(self.BOX_SELECTOR)
        log.info("[netto] %d product boxes in one catalogue call", len(boxes))
        listings = [self.read_box(box) for box in boxes]
        return self.keep_wines(x for x in listings if x is not None)

    #: "11" and "49" arrive in separate spans, so the rendered text reads
    #: "11. 49" — collapse the whitespace before looking for a number.
    _SPLIT_PRICE = re.compile(r"(\d{1,4})[.,](\d{2})")

    @classmethod
    def _price(cls, text: str) -> float | None:
        match = cls._SPLIT_PRICE.search(re.sub(r"\s+", "", text or ""))
        return float(f"{match.group(1)}.{match.group(2)}") if match else None

    def read_box(self, box) -> Listing | None:
        heading = box.css_first("h4") or box.css_first(".product__title")
        name = self.text_of(heading)
        if not name:
            return None
        price = self._price(self.text_of(box.css_first(".product__current-price")))
        if price is None:
            return None
        was = self._price(self.text_of(box.css_first(".product__strike-price")))

        base = self.text_of(box.css_first(".product-property__base-price"))
        unit_price = (self._price(base)
                      if re.search(r"/\s*l\b", base, re.I) else None)

        anchor = box.css_first("a.product__link") or box.css_first("a")
        link = anchor.attributes.get("href") if anchor else None

        return self.build(
            external_id=link or name,
            name=name,
            description=self.text_of(box)[:300],
            category="weine",
            url=link,
            price=price,
            list_price=was if was and was > price else None,
            on_promotion=bool(was and was > price),
            unit_price=unit_price,
        )


@register
class Edeka24Source(ShopwareSource):
    """EDEKA, through edeka24.de — the group's national online shop.

    EDEKA is Germany's largest grocer, so its range belongs in the study even
    though what is reachable is a slice of it: the category pages render 30
    products and load the rest by scrolling, with no page parameter that works
    (``?p=``, ``?page=`` and ``?seite=`` all return page one). What comes back
    is therefore the first 30 of each wine category, and the row count on the
    method sheet says so rather than implying a full catalogue.

    The regional EDEKA delivery shops carry the wider range, but each is a
    separate per-region shop behind a store picker.
    """

    key = "edeka24"
    label = "EDEKA (edeka24)"
    channel = "supermarkt"
    note = ("National online shop. Category pages render 30 products and page "
            "by scrolling, so coverage is the first 30 per wine category.")

    BASE = "https://www.edeka24.de"
    START_URLS = (
        f"{BASE}/Getraenke/Weinsorten/Rotwein/",
        f"{BASE}/Getraenke/Weinsorten/Weisswein/",
        f"{BASE}/Getraenke/Weinsorten/Ros-weine/",
        f"{BASE}/Getraenke/Weinsorten/Frucht-Spritz/",
    )
    # One page each: the shop repeats page one for every paging parameter, and
    # the loop's "nothing new" rule stops it after the second request anyway.
    PAGES = 2
    BOX_SELECTOR = "div.product-item"

    def read_box(self, box) -> Listing | None:
        anchor = box.css_first("a.title")
        name = ((anchor.attributes.get("title") if anchor else None)
                or self.text_of(box.css_first("h2"))).strip()
        if not name:
            return None
        prices = self.prices_in(self.text_of(box.css_first(".price.salesprice"))
                                or self.text_of(box.css_first(".price")))
        if not prices:
            return None
        # "7,32 €/l" sits in a price-note next to the "Niedrigster Preis" note,
        # so the per-litre pattern picks it out rather than the first number.
        notes = " ".join(self.text_of(n) for n in box.css(".price-note"))
        link = anchor.attributes.get("href") if anchor else None

        return self.build(
            external_id=link or name,
            name=name,
            description=notes[:300],
            category="getraenke/weinsorten",
            url=link,
            price=prices[0],
            unit_price=self.per_litre(notes),
        )


@register
class CombiSource(ShopwareSource):
    """Combi — Bartels-Langness hypermarkets, via their delivery shop.

    A full supermarket wine aisle priced for a household rather than a wine
    buyer: 1,114 products across beer, wine and spirits, of which the wine
    categories are paged here. Sister format to famila, whose own site carries
    no catalogue, so Combi stands in for the Bünting/Bela group.

    Each card states the pack size and the retailer's own price per litre in
    its description line — "750 ml 5,29 € 7,05 €/1 l" — which is both where the
    size comes from and what the price is checked against.
    """

    key = "combi"
    label = "Combi"
    channel = "supermarkt"
    note = "Bartels-Langness delivery shop; full beer/wine/spirits aisle."

    BASE = "https://www.combi.de"
    START_URLS = (
        f"{BASE}/rotwein_210002719.html",
        f"{BASE}/wei%c3%9fwein_210002720.html",
        f"{BASE}/ros%c3%a9wein_210002721.html",
        f"{BASE}/perlwein_210007412.html",
        f"{BASE}/fruchtwein_und_bowle_210002765.html",
    )
    PAGE_PARAM = "page"
    PAGES = 12
    BOX_SELECTOR = ".product-card"

    def read_box(self, box) -> Listing | None:
        name = self.text_of(box.css_first(".product-card__name"))
        if not name:
            return None
        price_text = self.text_of(box.css_first(".product-card__price--current"))
        prices = self.prices_in(price_text) or self.prices_in(
            self.text_of(box.css_first(".product-card__price")))
        if not prices:
            return None

        # The description line repeats name, size, price and unit price, in that
        # order: "… 750 ml 5,29 € 7,05 €/1 l". Only the part before the first
        # euro sign is the size, and cutting there matters because the unit
        # price ends in "/1 l": on a listing where Combi mistyped the size as
        # "750 l" — outside any plausible range and correctly rejected — the
        # parser went on to read that trailing "1 l" as a one-litre bottle.
        description = self.text_of(box.css_first(".product-card__description"))
        size_part = description.split("€")[0].replace(name, " ", 1)
        volume = P.parse_volume_l(size_part)
        unit_match = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*€\s*/\s*1?\s*l\b",
                               description, re.I)
        unit_price = float(unit_match.group(1).replace(",", ".")) if unit_match else None

        anchor = box.css_first("a.product-card__name__link") or box.css_first("a")
        link = anchor.attributes.get("href") if anchor else None

        return self.build(
            external_id=link or name,
            name=name,
            description=description[:400],
            # Just "wein", not the shop's own "bier-wein-spirituosen": the
            # category is fed to the non-wine filter, and a path with "Bier" in
            # it rejects the entire aisle it is meant to describe.
            category="wein",
            url=urljoin(self.BASE, link) if link else None,
            price=min(prices),
            unit_price=unit_price,
            volume_l=volume,
        )


@register
class WeinfreundeSource(Source):
    """Weinfreunde — Hawesko group's volume shop, bag-in-box category.

    Its own parent hawesko.de refuses datacentre addresses; weinfreunde.de does
    not, and carries the same kind of range, so it stands in for the group.
    """

    key = "weinfreunde"
    label = "Weinfreunde"
    channel = "fachhandel"
    note = "Hawesko group; Bag-in-Box category page."

    START_URL = "https://www.weinfreunde.de/c/weine/bag-in-box/"

    async def scrape(self) -> list[Listing]:
        listings: list[Listing] = []
        for page in range(1, 5):
            url = self.START_URL if page == 1 else f"{self.START_URL}?page={page}"
            try:
                html = await self.fetcher.get_text(url)
            except Exception as exc:                      # noqa: BLE001
                log.warning("[weinfreunde] page %d failed: %s", page, exc)
                break
            tiles = HTMLParser(html).css('[data-testid="product-tile"]')
            if not tiles:
                break
            before = len(listings)
            for tile in tiles:
                listing = self._read_tile(tile)
                if listing is not None:
                    listings.append(listing)
            if len(listings) == before:
                break
        return self.keep_wines(listings)

    def _read_tile(self, tile) -> Listing | None:
        text = re.sub(r"\s+", " ", tile.text(separator=" ")).strip()
        anchor = tile.css_first("a")
        link = anchor.attributes.get("href") if anchor else None
        name = (anchor.attributes.get("title") if anchor else None) or ""
        if not name:
            # The tile's own heading, when the anchor carries no title.
            heading = tile.css_first("h2") or tile.css_first("h3")
            name = re.sub(r"\s+", " ", heading.text()).strip() if heading else ""
        if not name:
            return None
        price_node = tile.css_first('[data-testid="tile-price"]')
        price_text = re.sub(r"\s+", " ", price_node.text(separator=" ")) if price_node else text
        prices = ShopwareSource.prices_in(price_text)
        if not prices:
            return None
        return self.build(
            external_id=link or name,
            name=name,
            description=text[:300],
            category="bag-in-box",
            url=urljoin("https://www.weinfreunde.de", link) if link else None,
            price=min(prices),
            unit_price=ShopwareSource.per_litre(text),
        )


# --------------------------------------------------------------------------
# METRO — the trade reference
# --------------------------------------------------------------------------
@register
class MetroSource(Source):
    """METRO Deutschland cash & carry.

    Included because it is the wholesale reference the retail prices sit above,
    and because METRO's own product world advertises bag-in-box as a range. Two
    caveats are recorded on every row rather than smoothed over:

    * **Prices are net of VAT.** METRO is a B2B business and shows trade prices;
      unlike its Romanian sibling, the German site returns ``sellingPriceInfo:
      null`` to an anonymous caller, so the only figure available is the search
      response's net price. ``price_basis`` says ``net`` on every row and the
      report never mixes these with the consumer prices.
    * **Assortment is per store.** Store 00015 carries the widest wine range of
      the 53 that answered, and is the one used.
    """

    key = "metro"
    label = "METRO Deutschland"
    channel = "cash_and_carry"
    price_basis = "net"
    note = "Trade prices, net of VAT. Store 00015 (widest wine assortment)."

    SEARCH = "https://produkte.metro.de/searchdiscover/articlesearch/search"
    DETAIL = "https://produkte.metro.de/evaluate.article.v1/betty-variants"
    STORE = "00015"
    BATCH = 40
    QUERIES = ("bag in box wein", "weinschlauch", "wein bag-in-box", "wein 3 liter",
               "wein 5 liter", "wein 10 liter", "wein pet")

    async def _ids(self, query: str) -> list[str]:
        params = {"storeId": self.STORE, "language": "de-DE", "country": "DE",
                  "query": query, "rows": 200, "page": 1,
                  "facets": "false", "categories": "false"}
        try:
            data = await self.fetcher.get_json(self.SEARCH, params=params,
                                               referer="https://produkte.metro.de/shop")
        except Exception as exc:                          # noqa: BLE001
            log.warning("[metro] search %r failed: %s", query, exc)
            return []
        # The search response carries the net price per id; keep it, because the
        # detail endpoint will not give us a price at all.
        self._prices.update({k: (v or {}).get("price")
                             for k, v in (data.get("results") or {}).items()})
        return [str(i) for i in (data.get("resultIds") or [])]

    async def _hydrate(self, ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for start in range(0, len(ids), self.BATCH):
            chunk = ids[start:start + self.BATCH]
            params = [("storeIds", self.STORE), ("country", "DE"),
                      ("locale", "de-DE"), ("details", "true")]
            params += [("ids", i) for i in chunk]
            try:
                data = await self.fetcher.get_json(
                    self.DETAIL, params=params,
                    referer="https://produkte.metro.de/shop")
            except Exception as exc:                      # noqa: BLE001
                log.warning("[metro] detail batch at %d failed: %s", start, exc)
                continue
            for article_no, article in (data.get("result") or {}).items():
                for variant in (article.get("variants") or {}).values():
                    variant_id = ((variant.get("bettyVariantId") or {})
                                  .get("bettyVariantId"))
                    for bundle in (variant.get("bundles") or {}).values():
                        out[str(variant_id)] = {"article": article_no, "bundle": bundle,
                                                "variant": variant}
                        break
        return out

    async def scrape(self) -> list[Listing]:
        self._prices: dict[str, float | None] = {}
        ids: list[str] = []
        for query in self.QUERIES:
            for identifier in await self._ids(query):
                if identifier not in ids:
                    ids.append(identifier)
        log.info("[metro] %d distinct ids across %d queries", len(ids), len(self.QUERIES))
        hydrated = await self._hydrate(ids)
        return self.keep_wines(
            self._to_listing(vid, blob) for vid, blob in hydrated.items())

    def _to_listing(self, variant_id: str, blob: dict) -> Listing | None:
        bundle = blob["bundle"]
        name = (bundle.get("description") or "").strip()
        if not name:
            return None
        content = (bundle.get("contentData") or {}).get("netContentVolume") or {}
        volume = None
        factor = {"ML": 0.001, "CL": 0.01, "L": 1.0}.get(str(content.get("uom") or "").upper())
        if factor and isinstance(content.get("value"), (int, float)):
            volume = round(content["value"] * factor, 4)

        categories = bundle.get("categories") or blob["variant"].get("categories") or []
        category = categories[0].get("name") if categories and isinstance(categories[0], dict) else ""

        return self.build(
            external_id=variant_id,
            name=name,
            description=(bundle.get("longDescription") or "")[:400],
            category=category or "",
            url=f"https://produkte.metro.de/shop/pv/{blob['article']}",
            price=P.parse_price(self._prices.get(variant_id)),
            volume_l=volume,
            brand=(bundle.get("brandName") or "").strip() or None,
            image_url=bundle.get("imageUrl") or None,
            raw={"store": self.STORE, "min_order": bundle.get("minOrderQuantity")},
        )
