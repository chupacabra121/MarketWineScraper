"""What a German wine is packaged in, and what the Pfand on it is.

This is the filter the whole German study turns on: the brief is PET bottles and
bag-in-box only, so a listing that cannot be placed in a container type has to be
excluded rather than guessed into the sample.

German retailers name the container in the product title far more reliably than
Romanian ones do — Lidl writes "3-l-Bag-in-Box" into the title itself — but the
words are not standardised. Bag-in-box alone appears as *Bag-in-Box*, *Bag in
Box*, *BiB*, *Weinschlauch*, *Weinbox*, *Bordeauxbox*, *Cubi* and *Fasswein im
Karton*. Each spelling below was taken from a listing actually collected.

Two container types are deliberately kept apart from bag-in-box even though they
are also "not glass":

* **Getränkekarton / Tetra Pak** is a carton with no inner bladder and no tap.
  It behaves like bag-in-box for Pfand purposes but is a different product on the
  shelf, at a different size (1 L, not 3 L), so folding the two together would
  blur exactly the price comparison this study exists to make.
* **Standbodenbeutel / Pouch** is a bladder with no box. Same reasoning.

They are classified and carried in the data, and the report keeps them visible as
context while the headline figures stay on PET and bag-in-box.
"""

from __future__ import annotations

import re
import unicodedata

# --- container types ---------------------------------------------------------
BAG_IN_BOX = "bag_in_box"
PET = "pet"
CARTON = "carton"
POUCH = "pouch"
CAN = "can"
GLASS = "glass"
KEG = "keg"
UNKNOWN = "unknown"

#: The two the brief asks for.
IN_SCOPE = (BAG_IN_BOX, PET)

LABELS = {
    BAG_IN_BOX: "Bag-in-Box",
    PET: "PET-Flasche",
    CARTON: "Getränkekarton",
    POUCH: "Standbodenbeutel",
    CAN: "Dose",
    GLASS: "Glasflasche",
    KEG: "Fass",
    UNKNOWN: "unbekannt",
}


def fold(text: str) -> str:
    """Lowercase, strip accents, and normalise the separators packaging words use.

    "Bag-in-Box", "Bag in Box" and "BagInBox" are one word written three ways,
    and Weißwein/Weisswein differ only by an ß a retailer may or may not use.
    """
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = text.replace("ß", "ss")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\s\-_/.]+", " ", text).strip()


# --- patterns ----------------------------------------------------------------
# Ordered by how specific the evidence is; the first match wins in classify().

_BAG_IN_BOX = re.compile(
    r"\bbag in box\b|\bbaginbox\b|\bbib\b|\bwein ?schlauch\b|\bschlauchwein\b"
    # German and English spellings of the same thing, both on German shelves:
    # Combi lists a "Chenin Blanc Wine Box" beside a "Weiß & Süß BIB".
    r"|\bwein ?box\b|\bwine ?box\b|\bbordeaux ?box\b|\bcubi\b|\bvinbox\b"
    r"|\bboxwein\b|\bwein im karton mit (?:zapf|hahn)|\bzapfhahn\b|\bfasswein\b",
)

# "PET" is the label; "Kunststoffflasche" and "Plastikflasche" are what a
# retailer writes when it avoids the acronym. Guard against PET as a word
# fragment (there is no German wine word containing it, but brand names exist)
# by requiring a boundary.
_PET = re.compile(
    r"\bpet\b|\bpet ?flasche\b|\bkunststoff ?flasche\b|\bplastik ?flasche\b"
    r"|\bpolyethylenterephthalat\b",
)

_CARTON = re.compile(
    r"\btetra ?pak\b|\btetra ?brik\b|\bgetranke ?karton\b|\bkarton ?verpackung\b"
    r"|\bcombibloc\b|\bkarton ?flasche\b|\bl packung\b|\bpackung wein\b"
    r"|\bkarton (?:rot|weiss|rose)wein\b|\bweinpackung\b",
)

_POUCH = re.compile(r"\bstandboden ?beutel\b|\bpouch\b|\bbeutel ?wein\b")

_CAN = re.compile(r"\bdose\b|\bdosen\b|\bcan\b(?! ?ada)")

_KEG = re.compile(r"\bfass\b|\bkeg\b|\bpartyfass\b")

# A glass bottle is normally implied rather than stated. These are the words a
# German listing uses when it does state it, plus the bottle shapes that only
# exist in glass (a Bocksbeutel is by definition a glass flask).
#
# Bare "Flasche" belongs here because it is tested *after* PET, carton and
# bag-in-box: a plastic bottle says "PET-Flasche" and matches earlier, so a
# listing still saying only "Flasche" at this point is a glass one. This is what
# keeps Lidl's "6 x 0,75-l-Flasche" Bordeaux cases out of the box sample.
#
# "Literflasche" is the German entry-wine one-litre bottle and the format
# bag-in-box competes with most directly, so it is named here rather than left
# to the bare-Flasche rule, which would miss it for want of a word boundary.
_GLASS = re.compile(
    r"\bglas ?flasche\b|\bflasche\b|\bliterflasche\b|\bklein ?flasche[n]?\b"
    r"|\bminiaturflasche\b|\bbocksbeutel\b|\bmagnum\b|\bdoppelmagnum\b"
    r"|\bjeroboam\b|\bbouteille\b|\bschraubverschluss glas\b",
)

#: A multipack states a per-unit size and a count. Its *total* volume is not a
#: container size, so the size-implies-a-box rule below must not see it: six
#: 0.75 L bottles total 4.5 litres and are still six glass bottles.
_MULTIPACK_HINT = re.compile(r"\b\d{1,2} ?[x×] ?\d|\bpaket\b|\bset\b|\bkiste\b|\bkarton \d")

# At three litres and above, the box is the rule and the bottle the exception.
# Measured on the collected data rather than assumed: of the 216 three-litre
# wines, 191 say bag-in-box outright, 24 name no container at all, and exactly
# one is a bottle — a Prosecco Jeroboam at METRO that writes "3 l Flasche" and
# is caught by the glass rule before the size rule is ever reached. At five and
# ten litres it is 28 of 28 and 8 of 8.
#
# The threshold stops at three. Two-litre wine in Germany is routinely a glass
# bottle — the Greek Imiglykos lines at Globus are the common case — so
# extending the rule downwards would start inventing boxes.
_BOX_FROM_L = 3.0


def classify(name: str, *, description: str = "", volume_l: float | None = None,
             category: str = "") -> str:
    """Which container this listing is sold in.

    Reads the title first, then any description and category the source gives,
    and only then falls back on what the size implies. Returns ``UNKNOWN`` when
    nothing says — which is the common case for an ordinary 0.75 L wine, and is
    reported as such rather than being counted as glass, because "the retailer
    did not say" and "the retailer said glass" are different facts.
    """
    haystack = fold(f"{name} {description} {category}")

    # Explicit statements, most specific first. Bag-in-box outranks PET because
    # a bag-in-box listing may mention the PET tap or inner bladder, but a PET
    # bottle listing never mentions a box.
    if _BAG_IN_BOX.search(haystack):
        return BAG_IN_BOX
    if _CARTON.search(haystack):
        return CARTON
    if _POUCH.search(haystack):
        return POUCH
    if _PET.search(haystack):
        return PET
    if _CAN.search(haystack):
        return CAN
    if _KEG.search(haystack):
        return KEG
    if _GLASS.search(haystack):
        return GLASS

    # Size as a last resort, and only where the size is decisive on its own —
    # which it is not for a multipack, whose stated litres are the case total.
    if (volume_l is not None and volume_l >= _BOX_FROM_L
            and not _MULTIPACK_HINT.search(haystack)):
        return BAG_IN_BOX
    return UNKNOWN


def is_in_scope(packaging: str) -> bool:
    """Whether this container is one of the two the study covers."""
    return packaging in IN_SCOPE


# --- Pfand -------------------------------------------------------------------
# Germany's single-use deposit (Einwegpfand, VerpackG §31) is a flat 0.25 EUR.
# Since 1 January 2022 it applies to *every* single-use plastic beverage bottle
# regardless of what is in it, which is what brought wine in PET into the scheme;
# before that wine was outside it.
AMOUNT = 0.25

#: The scheme covers 0.1 to 3.0 litres inclusive. A 5-litre container is out of
#: it by size alone, whatever it is made of.
MIN_VOLUME_L = 0.1
MAX_VOLUME_L = 3.0

#: Containers VerpackG §31(4) calls "ökologisch vorteilhaft" and exempts:
#: beverage cartons, polyethylene pouches and stand-up foil pouches. A
#: bag-in-box is a carton around a foil bladder and is exempt on both counts.
_PFANDFREI_CONTAINERS = frozenset({BAG_IN_BOX, CARTON, POUCH, KEG})

#: Single-use *glass* carries no deposit in Germany — the 0.25 EUR applies to
#: plastic bottles and metal cans only. Wine in a glass bottle is pfandfrei.
_PFANDFREI_CONTAINERS_GLASS = frozenset({GLASS})


def pfand(packaging: str, volume_l: float | None) -> float | None:
    """Deposit in EUR that a shopper pays on top of the shelf price.

    Returns ``0.0`` for a container the scheme exempts, ``0.25`` for one it
    covers, and ``None`` when the container is unknown — an unknown container
    has an unknown deposit, and defaulting it either way would put a 0.25 EUR
    error into whichever direction the default went.
    """
    if packaging in _PFANDFREI_CONTAINERS or packaging in _PFANDFREI_CONTAINERS_GLASS:
        return 0.0
    if packaging not in (PET, CAN):
        return None
    if volume_l is None:
        return None
    if MIN_VOLUME_L <= volume_l <= MAX_VOLUME_L:
        return AMOUNT
    return 0.0


def price_with_pfand(price: float | None, packaging: str,
                     volume_l: float | None) -> float | None:
    """Shelf price plus the deposit, which is what the till charges.

    On a 1-litre PET at 2.49 EUR the 0.25 deposit is 10% of the price — larger
    than most of the gaps between the wines this study compares — so the
    reports quote both this and the bare shelf price rather than picking one.
    """
    if price is None:
        return None
    dep = pfand(packaging, volume_l)
    if dep is None:
        return None
    return round(price + dep, 2)
