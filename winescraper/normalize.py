"""Parsing helpers for Romanian retail product text.

Listing pages give us little more than a title and a price, so most wine
attributes have to be recovered from strings like::

    "Vin rosu sec Feteasca Neagra, Domeniile Samburesti, 0.75 l, 13.5% alc."

Everything here is deliberately conservative: when a value cannot be read with
confidence the function returns ``None`` rather than guessing, because a wrong
vintage or ABV is worse than a missing one.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

__all__ = [
    "fold", "parse_price", "parse_volume_l", "parse_abv", "parse_vintage",
    "parse_colour", "parse_sweetness", "is_sparkling", "parse_grapes",
    "looks_like_wine", "parse_unit_price", "clean_name",
]

# Romanian comma decimals, optional thousands separator, optional currency.
_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,](\d{1,2}))?\s*(?:lei|ron)?", re.I)

_ML_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|cl|l|litri|litru)\b", re.I)
_ABV_RE = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%\s*(?:vol|alc)?", re.I)
_VINTAGE_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

# Grape varieties seen across Romanian retail listings, longest-first so that
# "Cabernet Sauvignon" wins over "Sauvignon".
_GRAPES = [
    "cabernet sauvignon", "sauvignon blanc", "feteasca neagra", "feteasca regala",
    "feteasca alba", "pinot grigio", "pinot gris", "pinot noir", "pinot blanc",
    "chardonnay", "merlot", "shiraz", "syrah", "malbec", "tempranillo",
    "sangiovese", "montepulciano", "primitivo", "zinfandel", "nebbiolo",
    "barbera", "grenache", "carmenere", "riesling", "traminer", "gewurztraminer",
    "muscat ottonel", "tamaioasa romaneasca", "tamaioasa", "busuioaca de bohotin",
    "busuioaca", "grasa de cotnari", "grasa", "zghihara", "negru de dragasani",
    "novac", "cramposie selectionata", "cramposie", "babeasca neagra", "babeasca",
    "mustoasa de maderat", "frincusa", "francusa", "plavaie", "galbena de odobesti",
    "sauvignon", "aligote", "viognier", "verdejo", "albarino", "vermentino",
    "glera", "macabeu", "parellada", "xarel-lo", "trebbiano", "garganega",
    "moscato", "muscat", "prosecco", "corvina", "rondinella",
    "blaufrankisch", "welschriesling", "silvaner", "furmint", "cserszegi",
    "carignan", "mourvedre", "cinsault", "petit verdot", "cabernet franc",
    "touriga nacional", "tinta roriz", "bonarda", "torrontes", "pinotage",
    "chenin blanc", "colombard", "ugni blanc", "marselan", "saperavi",
]
_GRAPES_SORTED = sorted(_GRAPES, key=len, reverse=True)

# Auchan and METRO populate their grape field with blend descriptors rather than
# a variety. They are not grapes and would otherwise rank among the top varieties.
NOT_A_GRAPE = {"cuvee", "cupaj", "blend", "sortiment", "assemblage", "mix", "cotnari"}


def is_grape(value: str) -> bool:
    """Whether a retailer-supplied variety string names an actual grape."""
    return bool(value) and fold(value).strip() not in NOT_A_GRAPE

_SPARKLING_WORDS = [
    "spumant", "spumante", "prosecco", "champagne", "sampanie", "cava",
    "frizzante", "cremant", "lambrusco", "asti", "petnat", "pet nat", "brut",
]

# Listings that sit in the wine aisle but are not wine. Each pattern was taken
# from a real listing found in the collected data; the comment names it.
_NOT_WINE_PATTERNS = [
    # Wine-based drinks that are not wine: "Bautura aromatizata pe baza de vin
    # rosu Wine Chocolate", "Bautura carbogazoasa cu aroma de capsuni Robby Bubble"
    r"bautura (aromatizata|carbogazoasa|racoritoare|spirtoasa)",
    r"pe baza de vin",
    r"wine chocolate",
    r"\bgluhwein\b|\bvin fiert\b|\bmulled\b",
    # Ready-to-drink cocktails: "Spumant Cocktail to Go Zarea Hugo", "Il Spritz
    # Mionetto", "Chandon Garden Spritz"
    r"\bcocteil\b|\bcocktail\b|\bspritz\b|\bhugo\b|\bsangria\b|\bmojito\b",
    r"sex on the beach|\baperol\b",
    # Flavoured fizz sold beside wine: "Bambino Party ... aroma de Piersica"
    r"aroma de (piersic|capsun|ananas|cocos|zmeur|visin|mar\b|fruct|lamai|portocal)",
    # Sparkling tea, sold in the wine aisle at Freshful
    r"\bceai\b|\bsparkling tea\b",
    # Vermouth and aperitifs: "MARTINI BIANCO VERMUT", "CINZANO ROSSO VERMUT"
    r"\bvermut\b|\bvermouth\b|\bcampari\b",
    # Alcohol-free "wine": not wine, and often literally grape juice
    r"fara alcool|dealcool|non-?alcohol|alcohol-?free",
    # A zero-alcohol claim, but not the "0" inside an ordinary "12.0% alcool":
    # the lookbehind stops the pattern matching a decimal place.
    r"(?<![\d.,])0(?:[.,]0)?\s*%(\s*alc)?",
    r"sampanie copii|\bfairies\b",
    # Multipacks and gift sets price a bundle, not a bottle
    # "Pachet vin alb ... (3+1) x 0.75 l" prices a bundle. A single bottle in a
    # gift box is still one bottle, so gift packaging alone is not excluded.
    r"^pachet\b|\bbax\b|\b\d+\s*x\s*\d|\(\d\+\d\)",
    # Food and accessories that mention wine
    r"\botet\b|\bvinete\b|\bvineta\b|\bvinificatie\b",
    r"\bcovrigi\b|\bbiscuit|\bpraline\b|\bbomboane\b|\bgem\b|sos de vin",
    r"\bpahar|\btirbuson\b|\bdecantor\b|\bcarafa\b|\bracitor\b|suport sticl",
    r"\bvitrina\b|\bfrigider\b|vin de gatit|vin fiert praf",
    r"\bvinars\b|\bvinarium accesor",
]
_NOT_WINE_RE = re.compile("|".join(_NOT_WINE_PATTERNS))

# Matched as whole words. Listing them explicitly rather than as a "vin"
# prefix keeps "vintage" (as in "Pepsi carbo vintage") out of the results.
_WINE_WORDS = ["vin", "vinul", "vinuri", "vinurile", "spumant", "spumante",
               "prosecco", "champagne", "sampanie", "cava", "cremant",
               "lambrusco", "sangria", "wine", "vino"]


def fold(text: str) -> str:
    """Lowercase and strip Romanian diacritics for robust matching.

    Retailers are wildly inconsistent about diacritics — the same wine appears
    as "Fetească Neagră", "Feteasca Neagra" and "FETEASCA NEAGRA" — so all
    matching happens on the folded form.
    """
    if not text:
        return ""
    # Normalise the two Unicode encodings of ș/ț (cedilla vs comma-below) first.
    text = text.replace("ş", "s").replace("Ş", "S")
    text = text.replace("ţ", "t").replace("Ţ", "T")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().strip()


def parse_price(value) -> float | None:
    """Parse a Romanian price string such as ``"15,49 Lei"`` or ``"1.234,50"``.

    Handles both comma and dot decimal separators, and the split-span markup
    some sites use (``"39"`` + ``"90"`` -> ``39.90``) once joined by the caller.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Zero is never a real shelf price; treat it as missing, exactly as the
        # string branch below does.
        return round(float(value), 2) if value > 0 else None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^\d.,\s]", " ", text).strip()
    if not text:
        return None
    # "1.234,50" -> dot is a thousands separator; "15.49" -> dot is decimal.
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        # A comma with 1-2 trailing digits is a decimal separator.
        text = re.sub(r",(\d{1,2})\b", r".\1", text).replace(",", "")
    text = text.replace(" ", "")
    try:
        price = float(text)
    except ValueError:
        return None
    if price <= 0 or price > 1_000_000:
        return None
    return round(price, 2)


def parse_volume_l(text: str) -> float | None:
    """Extract bottle volume in litres from a title (``750ml`` -> ``0.75``).

    Falls back to a bare decimal when no unit is present: cash & carry titles
    such as ``"CAII DE LA LETEA ALIGOTE ALB SEC 0,75"`` quote litres with the
    unit left off entirely.
    """
    if not text:
        return None
    folded = fold(text)
    best: float | None = None
    for match in _ML_RE.finditer(folded):
        raw, unit = match.group(1).replace(",", "."), match.group(2).lower()
        try:
            amount = float(raw)
        except ValueError:
            continue
        if unit == "ml":
            litres = amount / 1000
        elif unit == "cl":
            litres = amount / 100
        else:
            litres = amount
        # Ignore nonsense like a "50 l" barrel or a "0 l" typo in a wine title.
        if 0.04 <= litres <= 20:
            # Take the LAST plausible match, not the largest. Kaufland titles
            # carry an internal code that reads like a volume — "SERAFIM MERLOT
            # 12L SEC 13.5% 0.75L" is a 0.75 L bottle, not a 12 L one — and
            # retailers put the real bottle size at the end of the name.
            best = litres
    if best is not None:
        return round(best, 4)

    # No unit anywhere: accept a lone decimal in bottle range. Percentages are
    # excluded by the upper bound (13,5 is not a bottle size) and by requiring
    # that the number is not immediately followed by a '%'.
    for match in re.finditer(r"(?<![\d.,%])(\d{1,2}[.,]\d{1,2})(?!\s*%)(?![\d.,])", folded):
        try:
            candidate = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0.1 <= candidate <= 5.0:
            return round(candidate, 4)
    return None


def parse_abv(text: str) -> float | None:
    """Extract alcohol by volume as a percentage (``"13,5% vol"`` -> ``13.5``)."""
    if not text:
        return None
    for match in _ABV_RE.finditer(fold(text)):
        try:
            abv = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0 < abv <= 25:  # above this it is a spirit, not wine
            return round(abv, 1)
    return None


def parse_vintage(text: str, brand: str | None = None) -> int | None:
    """Extract a plausible vintage year from a title.

    A year that also appears in the brand is part of the label's name, not a
    vintage — "Sarica Niculitel 1958" and Penny's "1958" range are both brands.
    """
    if not text:
        return None
    current = datetime.now().year
    brand_text = brand or ""
    for match in _VINTAGE_RE.finditer(text):
        year = int(match.group(1))
        if year in (int(y) for y in _VINTAGE_RE.findall(brand_text)):
            continue
        if 1950 <= year <= current:
            return year
    return None


def parse_colour(text: str) -> str | None:
    """Classify wine colour as ``alb``, ``rosu`` or ``rose``."""
    folded = fold(text)
    # Check rose first: "vin rose" also contains "ros".
    if re.search(r"\bros[eé]\b|\broze\b", folded):
        return "rose"
    if re.search(r"\bro[sș]u\b|\brosii\b|\bred\b|\brouge\b|\btinto\b", folded):
        return "rosu"
    if re.search(r"\balb\b|\balbe\b|\bwhite\b|\bblanc\b|\bbianco\b|\bblanco\b", folded):
        return "alb"
    return None


def parse_sweetness(text: str) -> str | None:
    """Classify sweetness. Order matters: ``demidulce`` must beat ``dulce``."""
    folded = fold(text)
    for term, label in (
        ("demidulce", "demidulce"), ("demi-dulce", "demidulce"),
        ("demisec", "demisec"), ("demi-sec", "demisec"),
        # Abbreviations used on shelf labels. Bare "DS" is deliberately absent:
        # retailers use it for both demisec and demidulce.
        ("dmd", "demidulce"), ("dd", "demidulce"), ("dms", "demisec"),
        ("dulce", "dulce"), ("sec", "sec"),
        ("brut nature", "sec"), ("extra brut", "sec"), ("brut", "sec"),
        ("semi-dry", "demisec"), ("dry", "sec"), ("sweet", "dulce"),
    ):
        if re.search(rf"\b{re.escape(term)}\b", folded):
            return label
    return None


def is_sparkling(text: str) -> bool:
    folded = fold(text)
    return any(re.search(rf"\b{re.escape(w)}\b", folded) for w in _SPARKLING_WORDS)


def parse_grapes(text: str) -> list[str]:
    """Extract grape varieties mentioned in a title, longest match first."""
    if not text:
        return []
    folded = fold(text)
    found: list[str] = []
    consumed = folded
    for grape in _GRAPES_SORTED:
        if re.search(rf"\b{re.escape(grape)}\b", consumed):
            found.append(grape.title())
            # Blank the match so shorter substrings do not also fire.
            consumed = re.sub(rf"\b{re.escape(grape)}\b", " ", consumed)
    return found


def looks_like_wine(text: str, category_path: str | None = None) -> bool:
    """Filter out non-wine items that live in or near wine categories.

    Wine aisles routinely contain vinegar, glassware and corkscrews, and search
    endpoints match "vin" inside "vinete" (aubergines).
    """
    folded = fold(text)
    if _NOT_WINE_RE.search(folded):
        return False
    haystack = folded + " " + fold(category_path or "")
    return any(re.search(rf"\b{re.escape(w)}\b", haystack) for w in _WINE_WORDS)


def parse_unit_price(text: str) -> tuple[float | None, str | None]:
    """Parse an advertised unit price such as ``"20.65 Lei/L"``."""
    if not text:
        return None, None
    folded = fold(text)
    match = re.search(r"([\d.,]+)\s*(?:lei|ron)?\s*/\s*(l|litru|kg|buc|ml)\b", folded)
    if not match:
        return None, None
    return parse_price(match.group(1)), match.group(2)


def clean_name(text: str) -> str:
    """Collapse whitespace and strip retailer noise from a product name."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    # Trailing deposit-scheme markers add nothing and hurt cross-retailer matching.
    text = re.sub(r"\s*[-,]?\s*\bSGR\b\.?$", "", text, flags=re.I)
    return text.strip(" ,-")


def enrich(product) -> None:
    """Fill in any wine attributes still missing on a ``WineProduct``.

    Adapters set whatever the site gives them structurally; this recovers the
    rest from the title so every retailer ends up with comparable columns.
    """
    # Only the leaf category is usable context. Parent categories are named for
    # the whole aisle ("Vinuri si Spumante", "Vin si Sampanie"), which would
    # mark every still wine underneath them as sparkling.
    leaf = (product.category_path or "").rstrip("/").split("/")[-1]
    text = " ".join(filter(None, [product.name, leaf]))
    if product.volume_l is None:
        product.volume_l = parse_volume_l(product.name)
    if product.abv is None:
        product.abv = parse_abv(product.name)
    if product.vintage is None:
        product.vintage = parse_vintage(product.name, product.brand)
    if product.colour is None:
        product.colour = parse_colour(text)
    if product.sweetness is None:
        product.sweetness = parse_sweetness(text)
    if product.sparkling is None:
        product.sparkling = is_sparkling(text)
    if product.grape_varieties:
        product.grape_varieties = [g for g in product.grape_varieties if is_grape(g)]
    if not product.grape_varieties:
        product.grape_varieties = parse_grapes(product.name)
    if product.unit_price is None and product.price and product.volume_l:
        product.unit_price = round(product.price / product.volume_l, 2)
        product.unit_price_unit = "l"
