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
from dataclasses import dataclass, field, replace
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


class BrandLexicon:
    """The brand vocabulary, indexed for lookup by token run.

    Scanning a list of 600 brand names with a regex for every one of 6,750
    listings is 4 million pattern compilations and dominated the whole run.
    Brands are matched as runs of whole tokens, so indexing them by that run
    turns the scan into a handful of dict lookups.
    """

    def __init__(self, brands: Iterable[str]):
        self.brands = sorted(set(brands), key=lambda b: (-len(b.split()), -len(b)))
        self._by_tokens = {tuple(b.split()): b for b in self.brands}
        self._longest = max((len(t) for t in self._by_tokens), default=0)

    def __contains__(self, brand: str) -> bool:
        return brand in self._by_tokens.get(tuple(brand.split()), "")

    def __iter__(self):
        return iter(self.brands)

    def __len__(self) -> int:
        return len(self.brands)

    def find(self, tokens: Sequence[str]) -> str:
        """The longest brand appearing as a run of tokens in a title."""
        for size in range(min(self._longest, len(tokens)), 0, -1):
            for start in range(len(tokens) - size + 1):
                brand = self._by_tokens.get(tuple(tokens[start:start + size]))
                if brand:
                    return brand
        return ""


def brand_lexicon(rows: Sequence[dict]) -> BrandLexicon:
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
    return BrandLexicon(b for b, c in counts.items() if c >= 2)


def signature(row: dict, lexicon: BrandLexicon | None = None) -> Signature:
    """Reduce one listing to what identifies the wine it sells."""
    expanded = expand(row.get("name") or "")
    tokens = [t for t in _tokens(expanded) if t not in NOISE and len(t) > 1]

    brand = ""
    stated = (row.get("brand") or "").strip()
    if len(stated) >= 3:
        brand = " ".join(t for t in _tokens(expand(stated)) if t not in BRAND_NOISE)
    from_title = lexicon.find(tokens) if lexicon else ""
    if not brand:
        brand = from_title
    elif from_title and len(from_title.split()) > len(brand.split()) \
            and set(brand.split()) <= set(from_title.split()):
        # Auchan files "Pelin Carpatin" under the brand "Pelin", which left
        # "carpatin" looking like the name of a particular wine and split it
        # from the same bottle at METRO and Penny. Where the title carries a
        # longer known brand that contains the stated one, the longer wins.
        brand = from_title

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
    return (sig.brand, sig.volume_l, sig.sparkling)


#: Two sets of listings priced further apart than this are not folded together
#: by the circumstantial rules below. Across wines carried by several retailers
#: the median gap is 14% and almost none exceed 2.3x, so a 2.5x gap is evidence
#: against a merge the text could not settle on its own. It is deliberately
#: *only* applied to those two heuristic steps: price never decides identity
#: where the titles are clear, or a sale would rewrite the key.
MAX_MERGE_SPREAD = 2.5


def _prices_compatible(left: Sequence, right: Sequence) -> bool:
    prices = [r["price"] for r, _ in list(left) + list(right) if r.get("price")]
    if len(prices) < 2 or min(prices) <= 0:
        return True
    return max(prices) / min(prices) <= MAX_MERGE_SPREAD


def _consolidate_anchors(by_anchor: dict) -> dict:
    """Fold listings with no name of their own into the block's only named one.

    Auchan sells "Pelin Carpatin, Pelin alb demisec de Urlati"; METRO and Penny
    sell the same bottle as "Pelin Carpatin Vin Alb". "Urlați" is where the wine
    comes from, not which wine it is, and no rule can tell provenance from a
    range name by looking at the word.

    Who sells it can. A shop lists a given wine once, so if the named and
    unnamed listings come from entirely different shops they are one wine
    written two ways. If any shop appears on both sides — Auchan sells both
    plain Purcari Cabernet Sauvignon and "Roșu de Purcari" — they are two wines.
    The rule only applies when the block holds exactly one named group, since
    with two there is nothing to say which an unnamed listing belongs to.
    """
    unnamed = by_anchor.get(frozenset())
    named = {a: m for a, m in by_anchor.items() if a}
    if unnamed is None or len(named) != 1:
        return by_anchor
    (anchor, members), = named.items()
    if {r["retailer"] for r, _ in members} & {r["retailer"] for r, _ in unnamed}:
        return by_anchor
    if not _prices_compatible(members, unnamed):
        # Selgros' "LOPEZ DE HARO CRIANZA" at 40 lei and METRO's plain "LOPEZ DE
        # HARO" at 139 pass every textual test; the prices are the only thing
        # saying they are different wines.
        return by_anchor
    return {anchor: members + unnamed}


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


def _specificity(variant: tuple) -> int:
    return sum(1 for v in variant if v is not None)


def _resolve(variant: tuple, known: set) -> tuple:
    """Read an under-described listing as the one wine it can be.

    A listing is resolved against the most specific variant it is compatible
    with. The earlier rule only accepted variants where *every* attribute was
    stated, which almost never happens — most wines name no grape at all — so
    METRO's "Vin Alb Demisec" and Penny's "vin alb" stayed apart as two wines.

    If two equally specific readings survive, the data does not say which, and
    the listing keeps its own identity rather than being guessed into one.
    """
    own = _specificity(variant)
    candidates = [k for k in known
                  if k != variant and _specificity(k) > own and _compatible(variant, k)]
    if not candidates:
        return variant
    # Keep only the maximal readings: a variant that another candidate refines
    # is not itself a reading. Sorting by specificity means every variant that
    # could refine a candidate has already been seen, and lets the scan stop the
    # moment a second maximal reading turns up — which is the expensive case and
    # also the one that resolves to nothing.
    candidates.sort(key=_specificity, reverse=True)
    maximal = []
    for i, c in enumerate(candidates):
        spec = _specificity(c)
        if any(_specificity(o) > spec and _compatible(c, o) for o in candidates[:i]):
            continue
        maximal.append(c)
        if len(maximal) > 1:
            return variant
    return maximal[0]


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
    # The anchor and the range name overlap when a title carries both ("Pelin
    # ... de Urlati" gives anchor "urlati" and range "rose-urlati"), which reads
    # as "urlati-rose-urlati-rose". Repeats are cosmetic, but the key is meant
    # to be read.
    seen: set[str] = set()
    text = "-".join(w for w in re.sub(r"-+", "-", text).strip("-").split("-")
                    if w and not (w in seen or seen.add(w))) or "wine"
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
    if not _prices_compatible([(r, None) for r in named],
                              [(r, None) for r in unnamed]):
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
    for (brand, _volume, _sparkling), block_members in blocks.items():
        by_anchor: dict[frozenset, list] = defaultdict(list)
        for row, sig in block_members:
            by_anchor[sig.anchor].append((row, sig))

        # With no brand, the anchor is the only identity a listing has, so it is
        # never folded away: two unbranded wines sharing a colour and a bottle
        # size are not the same wine.
        anchors = (_consolidate_anchors(dict(by_anchor)) if brand else dict(by_anchor))
        for anchor, members in anchors.items():
            # A cellar vintage splits rather than resolves, so listings are only
            # read against others of the same vintage.
            by_vintage: dict[int | None, set] = defaultdict(set)
            for _, sig in members:
                variant = _variant(sig, recent_year)
                by_vintage[variant[3]].add(variant)
            # Resolution depends only on the variant, so it is worked out once
            # per distinct variant rather than once per listing. Without this a
            # 150-listing brand costs 150 times more than it needs to.
            resolution = {v: _resolve(v, siblings)
                          for siblings in by_vintage.values() for v in siblings}

            by_variant: dict[tuple, list] = defaultdict(list)
            for row, sig in members:
                by_variant[resolution[_variant(sig, recent_year)]].append((row, sig))

            for variant, variant_members in by_variant.items():
                for range_name, rows_in in _consolidate_range(variant_members):
                    sig = next(s for r, s in variant_members if r in rows_in)
                    sig = replace(sig, anchor=anchor)
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
