"""A recorded search for wine in PET bottles.

Half the brief is PET, and the collection returned none of it. "We found none"
is a weak claim when it rests on a filter, so this module asks each searchable
source for PET directly, in the words a German retailer would use, and records
what came back. The result is carried into the workbook as evidence, so a reader
can see which queries were run rather than take the absence on trust.

What it establishes: PET is a live packaging format in German wine, but on the
*supply* side. Flaschenland and comparable suppliers sell empty 250 ml and 750
ml PET wine bottles to wineries and event caterers. No filled wine in a PET
bottle appears in any German retail catalogue reached here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import packaging as pkg
from . import parse as P
from .fetch import Fetcher

log = logging.getLogger(__name__)

#: The words a German listing would use for a plastic wine bottle. "Kunststoff"
#: and "Plastik" are included because a retailer selling one may well avoid the
#: acronym, and "Einweg" because the deposit is what makes it visible on a label.
QUERIES = (
    "wein pet flasche",
    "wein kunststoffflasche",
    "wein plastikflasche",
    "wein pet",
    "weisswein pet flasche",
    "rotwein kunststoff",
    "wein einweg pfand flasche",
)


@dataclass(frozen=True)
class ProbeResult:
    source: str
    query: str
    hits: int
    #: Products classified PET *of any kind* — the honest denominator, because
    #: the searches do return PET, just never PET holding wine.
    pet_hits: int
    #: PET products that are also wine. This is the number the claim rests on.
    pet_wine_hits: int
    example: str


def _tally(source: str, query: str, names: list[str]) -> ProbeResult:
    pet = [n for n in names if pkg.classify(n) == pkg.PET]
    pet_wine = [n for n in pet if P.looks_like_wine(n)]
    # The example shown is the nearest miss: a PET product that is not wine
    # says more about why the count is zero than an arbitrary wine does.
    example = (pet_wine[0] if pet_wine else
               pet[0] if pet else
               (names[0] if names else ""))
    return ProbeResult(source, query, len(names), len(pet), len(pet_wine), example)


async def probe(fetcher: Fetcher) -> list[ProbeResult]:
    """Ask Lidl and METRO for PET wine by name and classify whatever comes back."""
    from .sources import LidlSource, MetroSource

    results: list[ProbeResult] = []

    lidl = LidlSource(fetcher)
    for query in QUERIES:
        items = await lidl._search({"q": query})
        names = [((item.get("gridbox") or {}).get("data") or {}).get("fullTitle", "")
                 for item in items]
        results.append(_tally("Lidl", query, names))

    metro = MetroSource(fetcher)
    metro._prices = {}
    for query in QUERIES:
        ids = await metro._ids(query)
        hydrated = await metro._hydrate(ids[:40])
        names = [(blob["bundle"].get("description") or "") for blob in hydrated.values()]
        results.append(_tally("METRO", query, names))
    return results


def summarise(results: list[ProbeResult]) -> str:
    total_hits = sum(r.hits for r in results)
    total_pet = sum(r.pet_hits for r in results)
    total_wine = sum(r.pet_wine_hits for r in results)
    lines = ["", "PET availability probe", "-" * 68,
             f"{len(results)} queries across {len({r.source for r in results})} "
             f"sources returned {total_hits} products; {total_pet} were in PET "
             f"and {total_wine} of those were wine"]
    for result in results:
        lines.append(f"  {result.source:7} {result.query:28} "
                     f"{result.hits:>4} hits, {result.pet_hits:>3} PET, "
                     f"{result.pet_wine_hits:>2} PET wine   {result.example[:44]}")
    return "\n".join(lines)
