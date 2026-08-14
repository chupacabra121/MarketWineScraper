"""Reading German wine listings: size, colour, sweetness, strength, origin.

The Romanian parser in :mod:`winescraper.normalize` cannot be reused as-is —
its vocabulary is Romanian and its volume grammar assumes "0,75 L" rather than
the "3-l-Bag-in-Box" and "5 Liter" forms German retailers write. What is shared
is the posture: a field that cannot be read with confidence stays ``None``
instead of being guessed, because a guessed litre count silently corrupts every
price-per-litre computed from it.
"""

from __future__ import annotations

import re

from .packaging import fold

# --- volume ------------------------------------------------------------------
# German listings write the size in a handful of shapes, all seen in collected
# data:
#   "3-l-Bag-in-Box"     "3,0 l"      "5 Liter"     "0,75-l-Flasche"
#   "1l"                 "750 ml"     "1,5-l"       "10 L Box"
_VOLUME_L = re.compile(
    r"(?<![\d,.])(\d{1,2}(?:[.,]\d{1,3})?)\s*(?:-\s*)?(?:l\b|liter\b|ltr\b)", re.I)
_VOLUME_ML = re.compile(r"(?<![\d,.])(\d{2,4})\s*(?:-\s*)?ml\b", re.I)
_VOLUME_CL = re.compile(r"(?<![\d,.])(\d{2,3})\s*(?:-\s*)?cl\b", re.I)

#: A multipack states the size per unit and the count: "6 x 0,75-l-Flasche".
#: The pack is not a container size, and treating 6 x 0.75 as 0.75 would make a
#: 6-bottle case look like a single bottle at six times the price.
_MULTIPACK = re.compile(r"(\d{1,2})\s*[x×]\s*(\d{1,2}(?:[.,]\d{1,3})?)\s*-?\s*(l\b|liter\b|ml\b)", re.I)

#: Sizes that are real wine containers. A number followed by "l" can also be an
#: alcohol percentage, a vintage or a bin number, so the result is sanity-checked
#: against the sizes wine is actually sold in rather than accepted outright.
_PLAUSIBLE_L = (0.1, 20.0)


def parse_volume_l(text: str) -> float | None:
    """Container size in litres, or ``None`` when the listing does not say."""
    if not text:
        return None
    raw = str(text)

    match = _MULTIPACK.search(raw)
    if match:
        unit = match.group(3).lower()
        size = float(match.group(2).replace(",", "."))
        if unit.startswith("ml"):
            size /= 1000.0
        return round(size, 4) if _PLAUSIBLE_L[0] <= size <= _PLAUSIBLE_L[1] else None

    for pattern, factor in ((_VOLUME_ML, 0.001), (_VOLUME_CL, 0.01), (_VOLUME_L, 1.0)):
        for found in pattern.finditer(raw):
            value = float(found.group(1).replace(",", ".")) * factor
            if _PLAUSIBLE_L[0] <= value <= _PLAUSIBLE_L[1]:
                return round(value, 4)
    return None


def parse_pack_count(text: str) -> int:
    """How many containers the listing sells at once; 1 unless it says otherwise."""
    match = _MULTIPACK.search(str(text or ""))
    if not match:
        return 1
    count = int(match.group(1))
    return count if 1 <= count <= 24 else 1


# --- colour ------------------------------------------------------------------
_COLOUR_PATTERNS = (
    ("rose", re.compile(r"\bros[eé]\s?wein\b|\bros[eé]\b|\brosado\b|\brosato\b|\bblush\b")),
    ("weiss", re.compile(r"\bweiss ?wein\b|\bwhite\b|\bblanco\b|\bbianco\b|\bblanc\b")),
    ("rot", re.compile(r"\brot ?wein\b|\bred\b|\btinto\b|\brosso\b|\brouge\b")),
)

#: Grapes that fix the colour when the listing never states one. Only varieties
#: with no ambiguity are listed: Pinot Grigio is dropped because it makes both
#: a white and a ramato, and a wrong colour is worse than a missing one.
_WHITE_GRAPES = re.compile(
    r"\briesling\b|\bchardonnay\b|\bsauvignon blanc\b|\bgrauburgunder\b"
    r"|\bweissburgunder\b|\bweisser burgunder\b|\bgrauer burgunder\b|\bsilvaner\b"
    r"|\bmuller thurgau\b|\bgutedel\b|\bkerner\b|\bscheurebe\b|\bbacchus\b"
    r"|\bairen\b|\bverdejo\b|\balbarino\b|\bviognier\b|\bchenin blanc\b"
    r"|\bvermentino\b|\bgruner veltliner\b|\bmoscato\b|\btrebbiano\b")
_RED_GRAPES = re.compile(
    r"\bmerlot\b|\bcabernet sauvignon\b|\bshiraz\b|\bsyrah\b|\btempranillo\b"
    r"|\bprimitivo\b|\bmontepulciano\b|\bsangiovese\b|\bdornfelder\b"
    r"|\bspatburgunder\b|\bpinot noir\b|\bmalbec\b|\bnero d avola\b"
    r"|\bblauer portugieser\b|\bregent\b|\bzweigelt\b|\bbarbera\b|\bnegroamaro\b"
    r"|\bcarmenere\b|\bpinotage\b|\bschwarzriesling\b|\btrollinger\b|\blemberger\b")


def parse_colour(text: str) -> str | None:
    """``rot`` | ``weiss`` | ``rose``, or ``None``.

    Rosé is tested before white and red because "Rosé" appears alongside the
    grape name of a red wine ("Pinot Noir Rosé") and would otherwise be read as
    the red it is made from.
    """
    haystack = fold(text)
    for colour, pattern in _COLOUR_PATTERNS:
        if pattern.search(haystack):
            return colour
    if _WHITE_GRAPES.search(haystack):
        return "weiss"
    if _RED_GRAPES.search(haystack):
        return "rot"
    return None


# --- sweetness ---------------------------------------------------------------
#: German wine law's four still-wine steps plus the sparkling scale and the
#: regional term "feinherb", which is legally halbtrocken but printed instead of
#: it on Riesling in particular.
_SWEETNESS = (
    ("halbtrocken", re.compile(r"\bhalb ?trocken\b|\bfein ?herb\b|\bsemi ?seco\b|\babboccato\b")),
    ("trocken", re.compile(r"\btrocken\b|\bdry\b|\bseco\b|\bsecco\b|\bbrut\b|\bherb\b")),
    ("lieblich", re.compile(r"\blieblich\b|\bsemi ?dulce\b|\bamabile\b|\bmild\b")),
    ("suess", re.compile(r"\bsuss\b|\bsweet\b|\bdulce\b|\bdolce\b|\bedelsuss\b")),
)


def parse_sweetness(text: str) -> str | None:
    """One of ``trocken`` | ``halbtrocken`` | ``lieblich`` | ``suess``.

    ``halbtrocken`` is matched first: it contains "trocken" as a substring, so
    testing dry first would classify every half-dry wine as dry.
    """
    haystack = fold(text)
    for value, pattern in _SWEETNESS:
        if pattern.search(haystack):
            return value
    return None


# --- strength, vintage -------------------------------------------------------
_ABV = re.compile(r"(\d{1,2}(?:[.,]\d)?)\s*(?:%|vol\.?\s*%|%\s*vol)", re.I)
_VINTAGE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def parse_abv(text: str) -> float | None:
    """Alcohol by volume as a percentage."""
    match = _ABV.search(str(text or ""))
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    # Wine sits between 0 (de-alcoholised) and 22% (fortified); anything above
    # is a spirit that landed in the wine aisle, not a misread percentage.
    return value if 0.0 <= value <= 22.0 else None


def parse_vintage(text: str) -> int | None:
    """Vintage year, ignoring years that are part of a size or a percentage."""
    for match in _VINTAGE.finditer(str(text or "")):
        year = int(match.group(1))
        if 1950 <= year <= 2049:
            return year
    return None


# --- origin ------------------------------------------------------------------
_COUNTRIES = {
    "deutschland": "Deutschland", "german": "Deutschland",
    "italien": "Italien", "italy": "Italien", "italia": "Italien",
    "frankreich": "Frankreich", "france": "Frankreich",
    "spanien": "Spanien", "spain": "Spanien", "espana": "Spanien",
    "portugal": "Portugal", "osterreich": "Österreich", "austria": "Österreich",
    "chile": "Chile", "argentinien": "Argentinien", "sudafrika": "Südafrika",
    "australien": "Australien", "neuseeland": "Neuseeland",
    "griechenland": "Griechenland", "ungarn": "Ungarn", "rumanien": "Rumänien",
    "usa": "USA", "kalifornien": "USA", "moldawien": "Moldawien",
}

#: Region names that identify a country on their own. Only used when the country
#: is not stated; a wine that says "Pfalz" is German whether or not it says so.
_REGION_COUNTRY = {
    "pfalz": "Deutschland", "rheinhessen": "Deutschland", "mosel": "Deutschland",
    "rheingau": "Deutschland", "baden": "Deutschland", "franken": "Deutschland",
    "wurttemberg": "Deutschland", "nahe": "Deutschland", "ahr": "Deutschland",
    "saale unstrut": "Deutschland", "sachsen": "Deutschland",
    "mittelrhein": "Deutschland", "hessische bergstrasse": "Deutschland",
    "apulien": "Italien", "puglia": "Italien", "toskana": "Italien",
    "venetien": "Italien", "sizilien": "Italien", "abruzzen": "Italien",
    "piemont": "Italien", "veneto": "Italien",
    "bordeaux": "Frankreich", "languedoc": "Frankreich", "rhone": "Frankreich",
    "provence": "Frankreich", "burgund": "Frankreich", "loire": "Frankreich",
    "pays d oc": "Frankreich", "cotes de gascogne": "Frankreich",
    "rioja": "Spanien", "la mancha": "Spanien", "valencia": "Spanien",
    "kastilien": "Spanien", "alentejano": "Portugal", "douro": "Portugal",
}


def parse_country(text: str) -> str | None:
    """Country of origin, from an explicit name or an unambiguous region."""
    haystack = fold(text)
    for needle, country in _COUNTRIES.items():
        if re.search(rf"\b{re.escape(needle)}", haystack):
            return country
    for needle, country in _REGION_COUNTRY.items():
        if re.search(rf"\b{re.escape(needle)}\b", haystack):
            return country
    return None


def parse_region(text: str) -> str | None:
    """Named growing region, where the listing states one we recognise."""
    haystack = fold(text)
    for needle in _REGION_COUNTRY:
        if re.search(rf"\b{re.escape(needle)}\b", haystack):
            return needle.title()
    return None


# --- grapes ------------------------------------------------------------------
_GRAPE_NAMES = (
    "Riesling", "Chardonnay", "Sauvignon Blanc", "Grauburgunder", "Weißburgunder",
    "Silvaner", "Müller-Thurgau", "Gutedel", "Kerner", "Scheurebe", "Bacchus",
    "Airén", "Verdejo", "Albariño", "Viognier", "Chenin Blanc", "Vermentino",
    "Grüner Veltliner", "Trebbiano", "Pinot Grigio", "Pinot Gris",
    "Merlot", "Cabernet Sauvignon", "Shiraz", "Syrah", "Tempranillo",
    "Primitivo", "Montepulciano", "Sangiovese", "Dornfelder", "Spätburgunder",
    "Pinot Noir", "Malbec", "Zweigelt", "Barbera", "Negroamaro", "Carmenère",
    "Pinotage", "Schwarzriesling", "Trollinger", "Lemberger", "Nero d'Avola",
    "Blauer Portugieser", "Regent", "Grenache", "Garnacha", "Corvina",
)


def parse_grapes(text: str) -> list[str]:
    """Grape varieties named in the listing, in the order they appear.

    Longer names are tested first so "Sauvignon Blanc" is not also counted as
    "Cabernet Sauvignon"'s Sauvignon, and the result is de-duplicated.
    """
    haystack = fold(text)
    found: list[tuple[int, str]] = []
    for grape in sorted(_GRAPE_NAMES, key=len, reverse=True):
        needle = fold(grape)
        position = haystack.find(needle)
        if position >= 0 and not any(
                needle in fold(seen) and needle != fold(seen) for _, seen in found):
            found.append((position, grape))
    # Drop a grape whose name is wholly inside one already found.
    kept: list[tuple[int, str]] = []
    for position, grape in sorted(found):
        if any(fold(grape) in fold(other) and grape != other for _, other in found):
            continue
        kept.append((position, grape))
    return [grape for _, grape in kept]


# --- price -------------------------------------------------------------------
_PRICE = re.compile(r"(\d{1,4})(?:[.\s](\d{3}))?[,.](\d{2})")


def parse_price(value) -> float | None:
    """A EUR price from a number or from German-formatted text ("1.234,56 €")."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if value > 0 else None
    text = str(value).replace("\xa0", " ").strip()
    if not text:
        return None
    match = _PRICE.search(text)
    if match:
        whole = match.group(1) + (match.group(2) or "")
        return round(float(f"{whole}.{match.group(3)}"), 2)
    plain = re.search(r"\b(\d{1,4})\b", text)
    return float(plain.group(1)) if plain else None


# --- is it wine? -------------------------------------------------------------
_NOT_WINE = re.compile(
    r"\bwhisk(?:y|ey)\b|\bgin\b|\brum\b|\bwodka\b|\bvodka\b|\btequila\b"
    r"|\blikor\b|\bschnaps\b|\bkorn\b|\bbrandy\b|\bcognac\b|\bgrappa\b"
    r"|\baperitif ?spirituose\b|\bbier\b|\bradler\b|\bcider\b|\bessig\b"
    r"|\bglaser\b|\bkorkenzieher\b|\bweinregal\b|\bdekanter\b|\bkuhlmanschette\b"
    r"|\bgutschein\b|\bbox(?:en)? \d+ ?l mit deckel\b|\baufbewahrungs\w*\b"
    r"|\bweinpaket\b|\bspirituosenpaket\b|\bwhiskypaket\b|\bmix ?getrank\b"
    # Grape juice is sold in the same 3-litre box as the wine beside it, and
    # WirWinzer files it in the same category. It is not wine.
    r"|\btraubensaft\b|\bapfelsaft\b|\bsaft\b"
    r"|\balkoholfrei\b|\bentalkoholisiert\b|\b0 ?[,.]?0 ?% ?vol\b",
)

_WINE_WORDS = re.compile(
    r"\bwein\b|\brotwein\b|\bweisswein\b|\brosewein\b|\bsekt\b|\bchampagner\b"
    r"|\bprosecco\b|\bspumante\b|\bcava\b|\bcremant\b|\bperlwein\b|\bsecco\b"
    r"|\bqba\b|\bpradikatswein\b|\bdoc\b|\bdocg\b|\bigt\b|\bigp\b|\baoc\b|\bdo\b"
    r"|\bcuvee\b|\brotling\b|\bweissherbst\b|\bsangria\b|\bwinzer\b|\bweingut\b"
    r"|\bbag in box\b|\bweinschlauch\b|\bweinbox\b",
)


# --- what kind of drink -------------------------------------------------------
#: Products that are wine legally and commercially but not comparable on price.
#: Glühwein is sold in the same 3- and 10-litre boxes as the wine beside it, at
#: a third of the price per litre, and a bag-in-box price point that averaged
#: the two would describe neither.
_TYPES = (
    ("gluehwein", re.compile(r"\bgluh ?wein\b|\bwinzergluhwein\b|\bpunsch\b|\bfeuerzangen\b")),
    ("sangria", re.compile(r"\bsangria\b|\btinto de verano\b")),
    ("schorle", re.compile(r"\bschorle\b|\bweinschorle\b|\bspritzer\b")),
    ("sparkling", re.compile(r"\bsekt\b|\bchampagner\b|\bprosecco\b|\bspumante\b"
                             r"|\bcava\b|\bcremant\b|\bperlwein\b|\bsecco\b"
                             r"|\bfrizzante\b|\bschaumwein\b")),
    ("dessert", re.compile(r"\bsusswein\b|\bportwein\b|\bsherry\b|\bmadeira\b"
                           r"|\bsauternes\b|\bbeerenauslese\b|\btrockenbeerenauslese\b")),
)


def parse_product_type(text: str) -> str:
    """``still`` unless the listing is something priced on another scale."""
    haystack = fold(text)
    for value, pattern in _TYPES:
        if pattern.search(haystack):
            return value
    return "still"


def looks_like_wine(name: str, category: str = "") -> bool:
    """Whether a listing from a wine aisle is actually wine.

    German wine aisles carry the same non-wine that Romanian ones do — glasses,
    corkscrews, storage boxes — plus, on Lidl, whole multi-bottle "Weinpaket"
    cases and a spirits range that the wine search returns alongside the wine.
    De-alcoholised wine is excluded too: it is a different product at a
    different price, and including it would drag the entry price point down.

    A named grape counts as evidence in its own right, because German growers
    title a listing by the variety and never say "Wein" at all: "2025
    Grauburgunder, Bag-in-Box, 3 L, Kaiserstuhl" is wine, and a keyword list
    long enough to name every variety would be the grape list twice over.
    """
    haystack = fold(f"{name} {category}")
    if _NOT_WINE.search(haystack):
        return False
    if _WINE_WORDS.search(haystack):
        return True
    # Falls back on the parsers rather than a second vocabulary, so a variety
    # added for attribute reading is recognised by the filter at the same time.
    return bool(parse_grapes(name) or _WHITE_GRAPES.search(haystack)
                or _RED_GRAPES.search(haystack))
