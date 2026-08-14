"""Checks that test a collected price against the retailer that published it.

Most German wine listings advertise their own price per litre — German price
labelling law requires a Grundpreis on packaged goods — and that figure is
computed server-side from the same price and size we parsed. Where it disagrees
with ours, one of the two numbers we read is wrong.

That check is not decoration. It is what caught Wein Schäpers being recorded at
5.06 EUR for a 3-litre box: the price and the per-litre reference sit in
adjacent elements, the parser took the cheaper of the two, and every affected
row still looked entirely plausible on its own. Only the retailer's own
arithmetic showed it.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import packaging as pkg
from .model import Listing

#: A parsed price is treated as agreeing with the retailer's when it is within
#: two percent, or five cents on a cheap wine. Rounding alone moves a per-litre
#: figure by a cent or two on a 0.75 L bottle.
TOLERANCE_FRACTION = 0.02
TOLERANCE_ABSOLUTE = 0.05

#: Litre prices outside this band are not large-format wine prices. The band is
#: deliberately narrow, and deliberately applied to the PET and bag-in-box rows
#: only: the wider catalogue holds a Château d'Yquem at 744 EUR/l and a
#: Champagne at 80, which are correct prices, so a band that had to accommodate
#: them would be too wide to catch anything. The floor sits below the cheapest
#: real box seen (1.23 EUR/l) and the ceiling above the dearest (13.00).
MIN_PRICE_PER_LITRE = 0.80
MAX_PRICE_PER_LITRE = 40.0


@dataclass(frozen=True)
class Finding:
    check: str
    retailer: str
    name: str
    detail: str


def _disagrees(ours: float, theirs: float) -> bool:
    return abs(ours - theirs) > max(TOLERANCE_ABSOLUTE, TOLERANCE_FRACTION * theirs)


def check_unit_prices(listings: list[Listing]) -> list[Finding]:
    """Our price per litre against the retailer's own Grundpreis."""
    findings = []
    for listing in listings:
        ours, theirs = listing.price_per_litre, listing.unit_price
        if ours is None or theirs is None:
            continue
        if _disagrees(ours, theirs):
            findings.append(Finding(
                "unit price", listing.retailer, listing.name,
                f"we compute {ours:.2f} EUR/l from {listing.price} over "
                f"{listing.volume_l} l x{listing.pack_count}; "
                f"{listing.retailer} advertises {theirs:.2f}"))
    return findings


def check_price_range(listings: list[Listing]) -> list[Finding]:
    """Litre prices that are not plausible large-format wine prices."""
    findings = []
    for listing in listings:
        if not pkg.is_in_scope(listing.packaging):
            continue
        per_litre = listing.price_per_litre
        if per_litre is None:
            continue
        if not MIN_PRICE_PER_LITRE <= per_litre <= MAX_PRICE_PER_LITRE:
            findings.append(Finding(
                "price range", listing.retailer, listing.name,
                f"{per_litre:.2f} EUR/l is outside "
                f"{MIN_PRICE_PER_LITRE}-{MAX_PRICE_PER_LITRE}"))
    return findings


def check_missing_volume(listings: list[Listing]) -> list[Finding]:
    """In-scope wines with no size, which cannot enter a per-litre comparison."""
    return [Finding("no volume", x.retailer, x.name, "no container size read")
            for x in listings
            if pkg.is_in_scope(x.packaging) and not x.volume_l]


def check_pfand(listings: list[Listing]) -> list[Finding]:
    """In-scope wines whose deposit could not be decided."""
    return [Finding("pfand", x.retailer, x.name,
                    f"{x.packaging} at {x.volume_l} l gives no deposit answer")
            for x in listings
            if pkg.is_in_scope(x.packaging) and x.pfand is None]


def run_checks(listings: list[Listing]) -> list[Finding]:
    findings: list[Finding] = []
    for check in (check_unit_prices, check_price_range,
                  check_missing_volume, check_pfand):
        findings.extend(check(listings))
    return findings


def report(findings: list[Finding], listings: list[Listing]) -> str:
    """A readable summary, including what passed."""
    checked = sum(1 for x in listings
                  if x.price_per_litre is not None and x.unit_price is not None)
    by_check: dict[str, list[Finding]] = {}
    for finding in findings:
        by_check.setdefault(finding.check, []).append(finding)

    lines = ["", "data checks", "-" * 60,
             f"{checked} of {len(listings)} listings could be cross-checked "
             f"against the retailer's own price per litre"]
    if not findings:
        lines.append("no findings")
        return "\n".join(lines)
    for check, found in sorted(by_check.items()):
        lines.append(f"\n{check}: {len(found)}")
        for finding in found[:8]:
            lines.append(f"  [{finding.retailer}] {finding.name[:52]}")
            lines.append(f"      {finding.detail}")
        if len(found) > 8:
            lines.append(f"  ... and {len(found) - 8} more")
    return "\n".join(lines)
