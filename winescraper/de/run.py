"""Run the German sources and write the study's outputs."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
from pathlib import Path

from . import packaging as pkg
from .fetch import Fetcher
from .model import EXPORT_COLUMNS, Listing
from .sources import all_sources

log = logging.getLogger(__name__)

DEFAULT_OUT = Path("exports/germany")


async def collect(keys: list[str] | None = None, *, limit: int | None = None,
                  delay: float = 1.0, use_cache: bool = True) -> list[Listing]:
    """Scrape every requested source, keeping a failure from losing the rest."""
    chosen = all_sources()
    if keys:
        chosen = {k: v for k, v in chosen.items() if k in keys}
    listings: list[Listing] = []
    async with Fetcher(delay=delay, use_cache=use_cache) as fetcher:
        for key, cls in chosen.items():
            source = cls(fetcher, limit=limit)
            try:
                got = await source.scrape()
            except Exception as exc:                      # noqa: BLE001
                log.error("[%s] failed: %s", key, exc)
                continue
            in_scope = [x for x in got if pkg.is_in_scope(x.packaging)]
            log.info("[%s] %d wines, %d in scope (PET/bag-in-box)",
                     key, len(got), len(in_scope))
            listings.extend(got)
    return listings


def write_outputs(listings: list[Listing], out_dir: Path) -> dict[str, Path]:
    """Write the full collection and the in-scope subset side by side.

    Both are kept. The in-scope file is the study; the full file is what makes
    the in-scope share meaningful — "23 bag-in-box wines" means nothing without
    the 800 bottles they were separated from.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for label, rows in (("all", listings),
                        ("pet-bib", [x for x in listings if pkg.is_in_scope(x.packaging)])):
        csv_path = out_dir / f"german-wine-{label}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for listing in rows:
                writer.writerow(listing.to_row())
        paths[label] = csv_path

    json_path = out_dir / "german-wine-pet-bib.jsonl"
    with json_path.open("w", encoding="utf-8") as handle:
        for listing in listings:
            if pkg.is_in_scope(listing.packaging):
                handle.write(json.dumps(listing.to_row(), ensure_ascii=False) + "\n")
    paths["jsonl"] = json_path
    return paths


def summarise(listings: list[Listing]) -> str:
    """A short run report, printed after a scrape."""
    lines = ["", f"{len(listings)} wine listings collected", ""]
    by_source: dict[str, list[Listing]] = {}
    for listing in listings:
        by_source.setdefault(listing.retailer_label, []).append(listing)
    lines.append(f"{'retailer':22} {'wines':>6} {'PET':>5} {'BiB':>5} {'other':>6}")
    for label, rows in sorted(by_source.items()):
        pet = sum(1 for x in rows if x.packaging == pkg.PET)
        bib = sum(1 for x in rows if x.packaging == pkg.BAG_IN_BOX)
        lines.append(f"{label:22} {len(rows):>6} {pet:>5} {bib:>5} {len(rows)-pet-bib:>6}")
    scope = [x for x in listings if pkg.is_in_scope(x.packaging)]
    prices = sorted(x.price_per_litre for x in scope if x.price_per_litre)
    if prices:
        mid = prices[len(prices) // 2]
        lines += ["", f"{len(scope)} in scope; EUR/litre min {prices[0]:.2f} "
                      f"median {mid:.2f} max {prices[-1]:.2f}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="winescraper-de",
        description="German market: PET and bag-in-box wine price points.")
    parser.add_argument("--source", action="append", dest="sources",
                        help="limit to one source (repeatable)")
    parser.add_argument("--limit", type=int, help="stop each source after N wines")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds per host")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-check", action="store_true",
                        help="skip the data checks run after a scrape")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workbook", action="store_true",
                        help="also build the Excel workbook")
    parser.add_argument("--language", action="append", choices=("de", "en"),
                        help="workbook language, repeatable; default both")
    parser.add_argument("--no-pet-probe", action="store_true",
                        help="skip the recorded search for PET wine")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    # Both languages by default: the study is of the German market and reads
    # naturally in German, but the people commissioning it may not.
    args.language = args.language or ["de", "en"]

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s")

    listings = asyncio.run(collect(args.sources, limit=args.limit,
                                   delay=args.delay, use_cache=not args.no_cache))
    if not listings:
        log.error("no listings collected")
        return 1

    paths = write_outputs(listings, args.out)
    print(summarise(listings))

    if not args.no_check:
        from .validate import report, run_checks
        print(report(run_checks(listings), listings))

    print("\n" + "\n".join(f"wrote {p}" for p in paths.values()))

    if args.workbook:
        from .petprobe import probe
        from .petprobe import summarise as summarise_probe
        from .workbook import build_workbook

        # The PET result is a null, so it needs its own evidence rather than an
        # absence in the data. Run the probe unless it was explicitly skipped.
        results = []
        if not args.no_pet_probe:
            async def _probe():
                async with Fetcher(delay=args.delay, use_cache=not args.no_cache) as f:
                    return await probe(f)
            results = asyncio.run(_probe())
            print(summarise_probe(results))

        names = {"de": "Deutscher-Weinmarkt-PET-BagInBox.xlsx",
                 "en": "German-Wine-Market-PET-BagInBox.xlsx"}
        for language in args.language:
            path = build_workbook(listings, args.out / names[language],
                                  probe_results=results, language=language)
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
