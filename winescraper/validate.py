"""Post-scrape data checks.

The scraper cannot tell a wrong price from a right one, but a wrong price
usually leaves a trace: a bottle at 3 lei, a per-litre figure ten times its
neighbours', a duplicate id, or a name that never looked like wine. These checks
surface those rows so a run can be inspected before its numbers are published.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass

from .normalize import looks_like_wine

# A 0.75 L bottle below this is almost certainly a parsing error or a per-100ml
# price; above it, a mis-read multipack or a decimal-separator mistake.
MIN_PLAUSIBLE_PPL = 6.0
MAX_PLAUSIBLE_PPL = 4000.0
# Flag a row whose price per litre is this many times its retailer's median.
OUTLIER_FACTOR = 12.0


@dataclass
class Finding:
    kind: str
    retailer: str
    name: str
    detail: str


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
                                    f"{count} rows share this product id"))

    for r in rows:
        name = r.get("name") or ""
        price = r.get("price")
        volume = r.get("volume_l")

        if not name.strip():
            findings.append(Finding("empty name", r["retailer"], "", "row has no product name"))
            continue
        if price is None:
            findings.append(Finding("no price", r["retailer"], name, "listing carries no price"))
            continue
        if price <= 0:
            findings.append(Finding("bad price", r["retailer"], name, f"price is {price}"))
        if not looks_like_wine(name, r.get("category_path")):
            findings.append(Finding("not wine", r["retailer"], name,
                                    "name does not read as wine"))
        if volume and volume > 0:
            ppl = price / volume
            if ppl < MIN_PLAUSIBLE_PPL:
                findings.append(Finding("price too low", r["retailer"], name,
                                        f"{ppl:.2f} RON/L on a {volume} L bottle"))
            elif ppl > MAX_PLAUSIBLE_PPL:
                findings.append(Finding("price too high", r["retailer"], name,
                                        f"{ppl:.2f} RON/L on a {volume} L bottle"))

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
                    f"{ppl:.0f} RON/L against a retailer median of {median:.0f}"))

    return findings


def summarise(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for f in findings:
        counts[f.kind] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
