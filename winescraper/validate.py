"""Post-scrape data checks.

The scraper cannot tell a wrong price from a right one, but a wrong price
usually leaves a trace: a bottle at 3 lei, a per-litre figure ten times its
neighbours', a duplicate id, or a name that never looked like wine. These checks
surface those rows so a run can be inspected before its numbers are published.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass

from .normalize import fold, looks_like_wine, _WINE_WORDS

# A 0.75 L bottle below this is almost certainly a parsing error or a per-100ml
# price; above it, a mis-read multipack or a decimal-separator mistake. The floor
# sits just under the cheapest verified real listing — Carrefour's 2 L PET table
# wine at 10.99 lei, or 5.50 RON/L.
MIN_PLAUSIBLE_PPL = 5.0
MAX_PLAUSIBLE_PPL = 4000.0
# Flag a row whose price per litre is this many times its retailer's median.
OUTLIER_FACTOR = 12.0
# The widest believable gap between two retailers selling the same wine. Above
# it, the listings were probably not the same wine to begin with.
MAX_WINE_SPREAD = 2.5
# Tolerance on the unit-price cross-check below. Sites round their own per-litre
# figure, so a couple of percent is normal and 5% is comfortably outside it.
UNIT_PRICE_TOLERANCE = 0.05
# Units whose published figure is directly comparable to price / volume_l.
_PER_LITRE_UNITS = {"", "l", "1l", "litru", "ron/l", "lei/l"}


# A row carrying fewer than this many independent wine signals goes into the
# review queue. Two is the level at which the queue stayed around 2-3% of a run:
# small enough to read, and it is what surfaced fruit wine and "Zero Alcool" —
# neither of which any hand-written rule was looking for.
MIN_WINE_SIGNALS = 2

_WINE_WORD_RE = re.compile(r"\b(" + "|".join(_WINE_WORDS) + r")\b")


@dataclass
class Finding:
    kind: str
    retailer: str
    name: str
    detail: str
    #: What a decision about this finding would point at. ``retailer`` above is
    #: for display and can read "metro/auchan"; these identify a row exactly.
    retailer_key: str = ""
    external_id: str = ""
    wine_key: str = ""

    @property
    def target(self) -> str:
        """How to refer to this finding on the command line."""
        if self.wine_key:
            return f"--wine {self.wine_key}"
        return f"--retailer {self.retailer_key} --id {self.external_id}"


def wine_signals(row: dict) -> int:
    """Count the independent things about a row that say "this is wine".

    The exclusion rules in ``normalize`` can only reject what someone has
    already seen. This counts positive evidence instead, so a listing that
    nothing recognises stands out even when no rule names it.
    """
    abv = row.get("abv")
    return sum((
        bool(_WINE_WORD_RE.search(fold(row.get("name") or ""))),
        bool(row.get("colour")),
        bool(row.get("grape_varieties")),
        bool(row.get("sweetness")),
        bool(abv and float(abv) >= 8),
    ))


def check(rows: list[dict]) -> list[Finding]:
    """Run every check over the latest observation per product."""
    findings: list[Finding] = []

    # -- structural ----------------------------------------------------
    seen: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        seen[(r["retailer"], str(r.get("external_id")))] += 1
    for (retailer, ext), count in seen.items():
        if count > 1:
            findings.append(Finding("duplicate id", retailer, ext,
                                    f"{count} rows share this product id",
                                    retailer_key=retailer, external_id=ext))

    for r in rows:
        name = r.get("name") or ""
        price = r.get("price")
        volume = r.get("volume_l")

        where = {"retailer_key": r["retailer"],
                 "external_id": str(r.get("external_id") or "")}
        if not name.strip():
            findings.append(Finding("empty name", r["retailer"], "",
                                    "row has no product name", **where))
            continue
        if price is None:
            findings.append(Finding("no price", r["retailer"], name,
                                    "listing carries no price", **where))
            continue
        if price <= 0:
            findings.append(Finding("bad price", r["retailer"], name,
                                    f"price is {price}", **where))
        if not looks_like_wine(name, r.get("category_path")):
            findings.append(Finding("not wine", r["retailer"], name,
                                    "name does not read as wine", **where))
        elif (signals := wine_signals(r)) < MIN_WINE_SIGNALS:
            findings.append(Finding("review", r["retailer"], name,
                                    f"only {signals} wine signal(s): kept on the "
                                    "retailer's category alone", **where))
        if volume and volume > 0:
            ppl = price / volume
            if ppl < MIN_PLAUSIBLE_PPL:
                findings.append(Finding("price too low", r["retailer"], name,
                                        f"{ppl:.2f} RON/L on a {volume} L bottle", **where))
            elif ppl > MAX_PLAUSIBLE_PPL:
                findings.append(Finding("price too high", r["retailer"], name,
                                        f"{ppl:.2f} RON/L on a {volume} L bottle", **where))

            # Most sites publish their own price per litre next to the price.
            # It is computed server-side from the same two numbers we parsed,
            # so disagreeing with it means we read the price, the volume, or
            # both wrongly. This is the only check here that tests a scraped
            # price against the retailer rather than against its neighbours.
            unit_price = r.get("unit_price")
            unit = (r.get("unit_price_unit") or "").strip().lower()
            if unit_price and unit_price > 0 and unit in _PER_LITRE_UNITS:
                if abs(ppl - unit_price) / unit_price > UNIT_PRICE_TOLERANCE:
                    findings.append(Finding(
                        "unit price disagrees", r["retailer"], name,
                        f"{price} over {volume} L is {ppl:.2f} RON/L, but the "
                        f"site publishes {unit_price:.2f} RON/L", **where))

    # -- wines whose listings disagree too much to be one wine ---------
    # Identity is reconstructed from titles, so it can be wrong. When it is, the
    # prices say so: across 763 wines carried by more than one retailer, the
    # median gap is 14% and almost none exceed 2.3x. A cluster spanning more
    # than that is either a bad merge or a listing worth looking at — the Auchan
    # Chardonnay listed twice, at 34.99 and 109.99, is both.
    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("wine_key") and r.get("price"):
            by_key[r["wine_key"]].append(r)
    for wine_key, listings in by_key.items():
        prices = [r["price"] for r in listings]
        if len(prices) < 2 or min(prices) <= 0:
            continue
        if max(prices) / min(prices) > MAX_WINE_SPREAD:
            cheap = min(listings, key=lambda r: r["price"])
            dear = max(listings, key=lambda r: r["price"])
            findings.append(Finding(
                "wine spread", f"{cheap['retailer']}/{dear['retailer']}", wine_key,
                f"{cheap['price']:.2f} to {dear['price']:.2f} "
                f"({max(prices) / min(prices):.1f}x) — grouped as one wine",
                wine_key=wine_key))

    # -- per-retailer outliers ----------------------------------------
    by_retailer: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for r in rows:
        if r.get("price") and r.get("volume_l"):
            by_retailer[r["retailer"]].append((r["price"] / r["volume_l"], r))
    for retailer, pairs in by_retailer.items():
        if len(pairs) < 30:
            continue
        median = statistics.median(p for p, _ in pairs)
        for ppl, r in pairs:
            if ppl > median * OUTLIER_FACTOR:
                findings.append(Finding(
                    "outlier", retailer, r["name"],
                    f"{ppl:.0f} RON/L against a retailer median of {median:.0f}",
                    retailer_key=retailer,
                    external_id=str(r.get("external_id") or "")))

    return findings


def summarise(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for f in findings:
        counts[f.kind] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
