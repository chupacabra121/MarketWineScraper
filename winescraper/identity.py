"""Give the same wine one identity across retailers.

Thirteen retailers write the same bottle thirteen ways. Purcari's Chardonnay is
listed by nine of them as "Vin alb sec Purcari Chardonnay", "PURCARI CHARDONNAY
SEC 0,75", "PURCARI 1827 Chardonnay de Purcari Vin Alb Sec SGR 0,75 L",
"Purcari chardonnay Vin alb sec 750 ml" and five more. Nothing in the source
data connects them: no retailer publishes a barcode, and product ids are
per-retailer.

The identity is therefore reconstructed from the title, in three steps.

**Normalise.** Cash & carry titles are abbreviated to the point of being a
different language — "CAB SAUV", "FET N", "TAM ROM", "PIN GRIG" — so known
abbreviations are expanded before anything else. Deposit markers, appellation
codes, ABV, volume and packaging words carry no identity and are dropped.

**Separate what identifies from what describes.** What is left splits into the
*anchor* (the producer's name for this wine — "Negru", "Vintage", "Premium")
and attributes that are recorded in their own right (grape, colour, sweetness,
volume). This matters because retailers disagree about which attributes to
print, not about the anchor.

**Resolve the gaps.** Auchan calls it "Negru de Purcari, Cabernet Sauvignon";
the other five just say "Negru de Purcari". An unstated attribute is treated as
unknown rather than as absent, and is resolved against the other listings of the
same anchor — but only when they agree. If the anchor covers a Chardonnay and a
Merlot, a listing that names neither cannot be placed, and keeps its own
identity instead of being guessed into one of them.

The result is a ``wine_key``: a readable, deterministic slug that is the same in
every run for the same wine, so price history survives a re-scrape.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .normalize import NOT_A_GRAPE, fold, parse_colour, parse_grapes, parse_sweetness

# ---------------------------------------------------------------- vocabulary

# Multi-word abbreviations, expanded before tokens are compared. Rewriting
# phrases rather than single tokens keeps "N" from becoming "Neagra" in
# "Rhein Extra N" — only "FET N" and "RARA N" mean the grape.
PHRASE_REWRITES: list[tuple[str, str]] = [
    (r"\bcab\.?\s*sauv\w*\b", "cabernet sauvignon"),
    (r"\bcab\.?\s*franc\b", "cabernet franc"),
    (r"\bsauv\.?\s*bl\w*\b", "sauvignon blanc"),
    (r"\bfet\.?\s*n\b", "feteasca neagra"),
    (r"\bfet\.?\s*reg\w*\b", "feteasca regala"),
    (r"\bfet\.?\s*alb\w*\b", "feteasca alba"),
    (r"\bf\.?\s*neagra\b", "feteasca neagra"),
    (r"\bf\.?\s*regala\b", "feteasca regala"),
    (r"\brara\.?\s*n\b", "rara neagra"),
    (r"\btam\.?\s*rom\w*\b", "tamaioasa romaneasca"),
    (r"\bbusuioaca\.?\s*b\b", "busuioaca de bohotin"),
    (r"\bpin\.?\s*gr(i|ig|igio)?\b", "pinot grigio"),
    (r"\bpin\.?\s*n(oir)?\b", "pinot noir"),
    (r"\bpin\.?\s*bl\w*\b", "pinot blanc"),
    (r"\bgr\.?\s*grigio\b", "pinot grigio"),
    (r"\bchard\w*\b", "chardonnay"),
    (r"\bsauv\w*\b", "sauvignon"),
    (r"\bmerl\.?\b", "merlot"),
    (r"\briesl\w*\b", "riesling"),
    (r"\btram\.?\b", "traminer"),
    (r"\bmusc\.?\b", "muscat"),
    (r"\bcramp\w*\b", "cramposie"),
    (r"\bnegru\s*de\s*dragasani\b", "negru de dragasani"),
    (r"\bbl\.?\s*de\s*bl\w*\b", "blanc de blancs"),
    # These require the abbreviating full stop. Without it, "dom" matches the
    # start of "domnesc" and rewrites it to "domeniile nesc" — which then poisons
    # the brand lexicon, because "Beciul Domnesc" is a real brand at nine
    # retailers.
    (r"\bdom\.\s*", "domeniile "),
    (r"\bv\.\s*cavalerului\b", "vinul cavalerului"),
    (r"\bbec\.?\s+domnesc\b", "beciul domnesc"),
    (r"\bcr\.\s*girboiu\b", "crama girboiu"),
]

# Sweetness, written a dozen ways. Mapped to the same values parse_sweetness uses.
SWEETNESS_ABBREV = {
    "dms": "demisec", "dmd": "demidulce", "dlc": "dulce", "ds": "demisec",
    "dd": "demidulce", "sc": "sec",
}

# Tokens that say nothing about which wine this is.
NOISE = {
    # the word "wine" in five languages, and the articles around it
    "vin", "vinul", "vinuri", "vino", "wine", "vino", "de", "la", "si", "cu",
    "din", "the", "of", "and", "el", "il", "los", "las",
    # colour and sweetness are recorded as fields, not as identity tokens
    "alb", "alba", "albe", "rosu", "rosie", "rosii", "rose", "roze", "rosato",
    "blanc", "blanco", "bianco", "rouge", "rosso", "tinto", "negro",
    "sec", "secco", "seco", "demisec", "demidulce", "dulce", "dry", "sweet",
    "brut", "extrasec", "extra", "nature", "dms", "dmd", "dlc", "ds", "dd",
    # appellation and quality codes
    "doc", "docg", "dop", "ig", "igp", "igt", "aoc", "ap", "cmd", "cmn", "ct",
    "dvr", "vdt", "vs", "vsc", "qba",
    # packaging, deposit and volume
    "sgr", "sg", "ls", "lsg", "bib", "bag", "box", "pet", "cutie", "gift",
    "sticla", "sticle", "buc", "ml", "cl", "litru", "litri", "magnum",
    # scraped-in noise
    "alc", "alcool", "alcohol", "vol", "bio", "eco", "organic", "vegan",
}

# Words that describe a tier rather than name a wine. They stay in the anchor —
# Tohani Premium costs 2.5x plain Tohani and Banfi's Chianti Riserva 30% more
# than its base — but they must never form an anchor on their own, or every
# retailer's "Premium" would collapse into one wine.
WEAK_ANCHORS = {"premium", "selection", "seleccion", "special", "classic",
                "clasic", "traditional", "traditie", "colectia", "collection",
                "edition", "editie", "limitata", "limited", "grand", "gran",
                "reserva", "riserva", "reserve", "rezerva", "superiore"}

# Stripped from the *brand field* only. The full NOISE list cannot be used here:
# it contains colour words, and "Casa de Rose" would reduce to "Casa", merging
# a Recaș rosé range with every other brand beginning with that word.
BRAND_NOISE = {"vin", "vinul", "vinuri", "vino", "wine", "de", "la", "si", "cu",
               "din", "the", "of", "and", "sgr", "doc", "docg", "ig", "igp"}

# Romanian producers name ranges after a colour: "Negru de Purcari", "Roșu de
# Purcari", "Alb de Ceptura", "Negru de Tomai". The colour word is the range
# name, not the colour of the wine, so it must survive the noise filter — but
# only in this exact contiguous form. "Vin alb sec de Purcari" is a description
# and must not be read as a range. "de masă" is table wine, not a place.
RANGE_RE = re.compile(
    r"\b(negru|rosu|alb|alba|rose|roze|grasa)\s+de\s+(?!masa\b)([a-z]{3,})\b")

_TOKEN_RE = re.compile(r"[a-z]+")
# Kaufland prefixes a code that reads like a volume ("12L SEC"), and every
# retailer states volume and ABV somewhere in the title.
_MEASURE_RE = re.compile(r"\d+[.,]?\d*\s*(?:l|ml|cl|%|k)\b|\d+[.,]?\d*(?=\s|$)")


# ---------------------------------------------------------------- signature

@dataclass(frozen=True)
class Signature:
    """What identifies one wine, separated from what merely describes it."""

    brand: str
    anchor: frozenset            # the producer's name for this wine
    volume_l: float | None
    sparkling: bool
    # Attributes a retailer may or may not print. None means "not stated",
    # which is different from "does not apply".
    colour: str | None
    sweetness: str | None
    grapes: frozenset | None
    vintage: int | None = None
    #: "Roșu de Purcari" and the like — a named range, when the title gives one.
    range_name: str | None = None


def expand(text: str) -> str:
    """Fold, then expand the abbreviations retailers use in place of words."""
    folded = fold(text)
    for pattern, replacement in PHRASE_REWRITES:
        folded = re.sub(pattern, replacement, folded)
    return folded


def _tokens(text: str) -> list[str]:
    without_measures = _MEASURE_RE.sub(" ", text)
    return _TOKEN_RE.findall(without_measures)


def brand_lexicon(rows: Sequence[dict]) -> list[str]:
    """Brand names, learned from the retailers that publish them.

    Six of thirteen sources leave the brand field empty — Kaufland, Penny,
    Profi and Supeco between them account for 1,064 listings, none of which the
    old matcher could touch, because it required a brand. The brands are all
    present in those titles; only the field is missing. Retailers that do fill
    it in supply the vocabulary to read them.
    """
    counts: Counter = Counter()
    for row in rows:
        brand = (row.get("brand") or "").strip()
        if len(brand) < 3:
            continue
        cleaned = " ".join(t for t in _tokens(expand(brand)) if t not in BRAND_NOISE)
        if len(cleaned) >= 3:
            counts[cleaned] += 1
    # A brand seen once is as likely to be a mis-filled field as a real brand.
    lexicon = [b for b, c in counts.items() if c >= 2]
    # Longest first, so "Beciul Domnesc" is found before "Beciul".
    return sorted(lexicon, key=lambda b: (-len(b.split()), -len(b)))


def _brand_from_title(title_tokens: Sequence[str], lexicon: Iterable[str]) -> str:
    """Longest lexicon brand appearing as a run of tokens in the title."""
    joined = " ".join(title_tokens)
    for brand in lexicon:
        if re.search(rf"(?:^| ){re.escape(brand)}(?:$| )", joined):
            return brand
    return ""


def signature(row: dict, lexicon: Sequence[str] = ()) -> Signature:
    """Reduce one listing to what identifies the wine it sells."""
    expanded = expand(row.get("name") or "")
    tokens = [t for t in _tokens(expanded) if t not in NOISE and len(t) > 1]

    brand = ""
    stated = (row.get("brand") or "").strip()
    if len(stated) >= 3:
        brand = " ".join(t for t in _tokens(expand(stated)) if t not in BRAND_NOISE)
    if not brand:
        brand = _brand_from_title(tokens, lexicon)

    # Grapes come from the retailer's own field when it has one, and from the
    # title otherwise. Blend descriptors ("Cuvée", "Cupaj") are not varieties.
    stated_grapes = row.get("grape_varieties") or ""
    if isinstance(stated_grapes, str):
        stated_grapes = [g for g in re.split(r"[;,|]", stated_grapes) if g.strip()]
    # parse_grapes returns display-cased names ("Feteasca Neagra"); everything
    # here compares folded text, so both sources are folded before the union or
    # the same grape counts twice and its tokens escape the anchor.
    grapes = {fold(g).strip() for g in stated_grapes}
    grapes |= {fold(g).strip() for g in parse_grapes(expanded)}
    grapes = {g for g in grapes if g and g not in NOT_A_GRAPE}

    # The anchor is what remains once the brand and every recorded attribute is
    # taken out: the producer's own name for this particular wine.
    consumed = set(brand.split())
    for grape in grapes:
        consumed |= set(grape.split())
    anchor = {t for t in tokens if t not in consumed}
    if anchor and anchor <= WEAK_ANCHORS and not brand:
        # Qualifying a brand, "Premium" is a real range: Tohani Premium costs
        # 2.5x plain Tohani, and Villa Vinea Classic is not Villa Vinea
        # Selection. On its own, with no brand to qualify, it identifies
        # nothing and would merge every retailer's premium tier into one wine.
        anchor = set()

    range_match = RANGE_RE.search(expanded)
    range_name = "-".join(range_match.groups()) if range_match else None

    return Signature(
        brand=brand,
        anchor=frozenset(anchor),
        range_name=range_name,
        volume_l=round(row["volume_l"], 3) if row.get("volume_l") else None,
        sparkling=bool(row.get("sparkling")),
        vintage=row.get("vintage"),
        colour=row.get("colour") or parse_colour(expanded),
        sweetness=(row.get("sweetness") or parse_sweetness(expanded)
                   or SWEETNESS_ABBREV.get(next(
                       (t for t in _tokens(fold(row.get("name") or ""))
                        if t in SWEETNESS_ABBREV), ""))),
        grapes=frozenset(grapes) if grapes else None,
    )


# ---------------------------------------------------------------- resolution

@dataclass
class WineGroup:
    """One wine, and every listing of it."""

    key: str
    signature: Signature
    rows: list = field(default_factory=list)

    @property
    def retailers(self) -> set:
        return {r["retailer"] for r in self.rows}


def _block(sig: Signature) -> tuple:
    """What must match exactly before two listings can be considered."""
    return (sig.brand, sig.anchor, sig.volume_l, sig.sparkling)


#: A stated vintage this many years back marks a cellar bottle rather than
#: current stock. Cotnari sells a 1994 Feteasca Alba at 203 lei beside an
#: ordinary one at 22; the year is the product. Recent vintages are not: a 2023
#: Purcari Chardonnay and an unlabelled one are the same wine on the same shelf,
#: and treating the year as identity would split seven retailers into eight.
CELLAR_AGE_YEARS = 6


def _cellar_vintage(sig: Signature, recent_year: int | None) -> int | None:
    """The vintage, but only when it identifies the bottle rather than the year
    the current stock happens to come from."""
    if not sig.vintage or not recent_year:
        return None
    return sig.vintage if recent_year - sig.vintage > CELLAR_AGE_YEARS else None


def _variant(sig: Signature, recent_year: int | None = None) -> tuple:
    """The attributes a retailer may leave unstated.

    An unstated attribute is unknown, not absent, so it resolves against the
    other listings of the same wine. That works for colour, sweetness and grape,
    which are permanent facts about a wine. It does not work for vintage, which
    turns over every year — so only a cellar vintage takes part, and it splits
    rather than resolves.
    """
    return (sig.colour, sig.sweetness, sig.grapes,
            _cellar_vintage(sig, recent_year))


def _compatible(partial: tuple, full: tuple) -> bool:
    """Whether an under-specified listing could be this variant.

    An unstated attribute matches anything. A stated one must agree — except
    for grapes, where a retailer naming one variety of a blend the other
    describes in full should still match.
    """
    for i, (left, right) in enumerate(zip(partial, full)):
        if left is None or right is None:
            continue
        if i == 2:
            if not (left & right):
                return False
        elif left != right:
            return False
    return True


def _slug(sig: Signature, variant: tuple, range_name: str | None) -> str:
    """A readable, deterministic key. Same wine, same key, every run."""
    colour, sweetness, grapes, vintage = variant
    parts = [sig.brand] + sorted(sig.anchor)
    if range_name:
        parts.append(range_name)
    parts += sorted(grapes or ())
    parts += [p for p in (colour, sweetness) if p]
    if vintage:
        parts.append(str(vintage))
    if sig.volume_l:
        parts.append(f"{sig.volume_l:g}l")
    text = "-".join(re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-") for p in parts if p)
    text = re.sub(r"-+", "-", text).strip("-") or "wine"
    digest = hashlib.sha1(
        repr((sig.brand, sorted(sig.anchor), sig.volume_l, sig.sparkling,
              colour, sweetness, sorted(grapes or ()), vintage, range_name)).encode()
    ).hexdigest()[:6]
    return f"{text[:60].strip('-')}-{digest}"


def _consolidate_range(members: list) -> list:
    """Decide whether listings that name a range and listings that do not are
    the same wine.

    Four retailers call it "Rosé de Purcari" and five just call it Purcari rosé;
    it is one wine. One Auchan listing calls it "Roșu de Purcari" at 110 lei
    while seven retailers sell plain Purcari Cabernet Sauvignon at 35-43; those
    are two wines, and the naming is the only thing separating them.

    What tells them apart is not the text but who is selling: a shop lists a
    given wine once. If the same retailer appears both with and without the
    range name, it is describing two different wines, and they stay apart. If no
    retailer appears on both sides, the two sets are the same wine written two
    ways, and they merge under the named form.

    Returns a list of ``(range_name, rows)`` groups.
    """
    by_range: dict = defaultdict(list)
    for row, sig in members:
        by_range[sig.range_name].append(row)

    unnamed = by_range.pop(None, None)
    if unnamed is None or len(by_range) != 1:
        # Nothing to fold in, or more than one candidate range — in which case
        # the data does not say which one an unnamed listing belongs to.
        if unnamed is not None:
            by_range[None] = unnamed
        return list(by_range.items())

    (range_name, named), = by_range.items()
    if {r["retailer"] for r in named} & {r["retailer"] for r in unnamed}:
        return [(range_name, named), (None, unnamed)]
    return [(range_name, named + unnamed)]


def group_wines(rows: Sequence[dict]) -> list[WineGroup]:
    """Cluster listings into wines and give each one a stable key.

    Listings are blocked on brand, anchor, volume and style, then split by the
    attributes they state. A listing that leaves an attribute unstated joins the
    one variant it is compatible with; if it is compatible with several, the
    data does not say which, so it stays separate rather than being guessed.
    """
    lexicon = brand_lexicon(rows)
    signed = [(row, signature(row, lexicon)) for row in rows]
    # "Recent" is read off the data rather than the clock, so the same database
    # always produces the same keys.
    vintages = [s.vintage for _, s in signed if s.vintage]
    recent_year = max(vintages) if vintages else None

    blocks: dict[tuple, list] = defaultdict(list)
    for row, sig in signed:
        blocks[_block(sig)].append((row, sig))

    groups: dict[str, WineGroup] = {}
    for _, members in blocks.items():
        # Variants that are fully described are the candidates an
        # under-described listing can be resolved against. A cellar vintage is
        # never resolved into, only split on, so it is excluded from the test.
        fully_stated = {_variant(sig, recent_year) for _, sig in members
                        if all(v is not None for v in _variant(sig, recent_year)[:3])}
        by_variant: dict[tuple, list] = defaultdict(list)
        for row, sig in members:
            variant = _variant(sig, recent_year)
            if variant not in fully_stated:
                candidates = [f for f in fully_stated
                              if _compatible(variant[:3], f[:3]) and f[3] == variant[3]]
                # Exactly one reading, or none at all: anything else is a guess.
                if len(candidates) == 1:
                    variant = candidates[0]
            by_variant[variant].append((row, sig))

        for variant, variant_members in by_variant.items():
            for range_name, rows_in in _consolidate_range(variant_members):
                sig = next(s for r, s in variant_members if r in rows_in)
                key = _slug(sig, variant, range_name)
                group = groups.get(key)
                if group is None:
                    group = groups[key] = WineGroup(key=key, signature=sig)
                group.rows.extend(rows_in)
    return sorted(groups.values(), key=lambda g: (-len(g.retailers), g.key))


def assign_keys(rows: Sequence[dict]) -> dict:
    """``{(retailer, external_id): wine_key}`` for every listing."""
    out = {}
    for group in group_wines(rows):
        for row in group.rows:
            out[(row["retailer"], str(row["external_id"]))] = group.key
    return out
