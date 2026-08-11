"""Command line interface: ``python -m winescraper``."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .export import export_run
from .runner import RunOptions, resolve_sites, run_sites
from .sites import all_adapters
from .storage import Store

DEFAULT_DB = Path("data/wines.sqlite")
DEFAULT_EXPORT_DIR = Path("exports")


def _setup_logging(verbosity: int) -> None:
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    # httpx logs every request at INFO, which drowns out our own progress lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_parser() -> argparse.ArgumentParser:
    # Verbosity flags are attached to both the top level and every subcommand so
    # that `winescraper run -q` works as readily as `winescraper -q run`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="count",
                        default=argparse.SUPPRESS, help="repeat for debug logging")
    common.add_argument("-q", "--quiet", action="store_true",
                        default=argparse.SUPPRESS, help="errors only")

    parser = argparse.ArgumentParser(
        prog="winescraper",
        parents=[common],
        description="Scrape wine listings and prices from Romanian grocery retailers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", parents=[common], help="scrape one or more retailers")
    run.add_argument("--site", action="append", dest="sites", metavar="KEY",
                     help="retailer key; repeatable")
    run.add_argument("--all", action="store_true", help="every scrapable retailer")
    run.add_argument("--limit", type=int, help="stop after N wines per retailer")
    run.add_argument("--delay", type=float, default=1.0,
                     help="minimum seconds between requests to one host (default 1.0)")
    run.add_argument("--no-cache", action="store_true", help="bypass the on-disk HTTP cache")
    run.add_argument("--dry-run", action="store_true", help="scrape without writing to the database")
    run.add_argument("--db", type=Path, default=DEFAULT_DB)
    run.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    run.add_argument("--format", dest="formats", default="csv,jsonl",
                     help="comma-separated export formats, or 'none'")
    run.add_argument("--config", type=Path, help="JSON file of per-site settings")
    run.add_argument("--no-check", action="store_true",
                     help="skip the data checks that normally follow a run")

    listing = sub.add_parser("list-sites", parents=[common], help="show retailers and their status")
    listing.add_argument("--json", action="store_true")

    export = sub.add_parser("export", parents=[common], help="export the latest stored prices")
    export.add_argument("--site", dest="site")
    export.add_argument("--db", type=Path, default=DEFAULT_DB)
    export.add_argument("--out", type=Path, default=DEFAULT_EXPORT_DIR / "latest.csv")

    history = sub.add_parser("history", parents=[common], help="show recent price changes")
    history.add_argument("--site", dest="site")
    history.add_argument("--db", type=Path, default=DEFAULT_DB)
    history.add_argument("--limit", type=int, default=40)

    stats = sub.add_parser("stats", parents=[common], help="row counts per retailer")
    stats.add_argument("--db", type=Path, default=DEFAULT_DB)

    checks = sub.add_parser("check", parents=[common],
                            help="look for implausible prices and non-wine rows")
    checks.add_argument("--db", type=Path, default=DEFAULT_DB)
    checks.add_argument("--site", dest="site")
    checks.add_argument("--show", type=int, default=15,
                        help="rows to print per finding type")

    return parser


def cmd_list_sites(args) -> int:
    adapters = all_adapters()
    if args.json:
        print(json.dumps(
            {key: {"label": cls.label, "catalogue": cls.catalogue,
                   "needs_browser": cls.needs_browser, "note": cls.note}
             for key, cls in adapters.items()}, indent=2, ensure_ascii=False))
        return 0
    width = max(len(k) for k in adapters)
    status_label = {"catalogue": "full catalogue", "promo": "weekly offers", "none": "unsupported"}
    for key, cls in adapters.items():
        flag = " [browser]" if cls.needs_browser else ""
        print(f"{key:<{width}}  {status_label[cls.catalogue]:<14}{flag}  {cls.label}")
        if cls.note:
            print(f"{'':<{width}}  └─ {cls.note}")
    return 0


def cmd_run(args) -> int:
    site_config = {}
    if args.config:
        site_config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    keys = resolve_sites(args.sites, args.all)
    options = RunOptions(
        limit=args.limit,
        delay=args.delay,
        use_cache=not args.no_cache,
        db_path=args.db,
        dry_run=args.dry_run,
        site_config=site_config,
    )
    results = asyncio.run(run_sites(keys, options))

    formats = [f.strip() for f in args.formats.split(",") if f.strip() and f.strip() != "none"]
    failures = degraded = 0
    print()
    for result in results:
        if result.status == "error":
            failures += 1
            print(f"  {result.site:<12} FAILED  {result.error}")
            continue
        if result.status == "unsupported":
            print(f"  {result.site:<12} skipped ({result.error})")
            continue
        note = f"{result.count:>5} wines"
        if not args.dry_run:
            note += f", {result.price_changes} price change(s) recorded"
        if result.degraded:
            degraded += 1
            note += f"  ⚠ {result.warnings} recoverable failure(s)"
        print(f"  {result.site:<12} {note}")
        for message in result.warning_samples:
            print(f"  {'':<12}   ! {message[:100]}")
        if formats and result.products:
            for path in export_run(result.products, args.export_dir, result.site, formats):
                print(f"  {'':<12} → {path}")
    total = sum(r.count for r in results)
    print(f"\n{total} wines across {len([r for r in results if r.count])} retailer(s)")
    if degraded:
        print(f"{degraded} retailer(s) completed with recoverable failures — "
              "the catalogue may be incomplete")

    # Validating here rather than leaving it to a separate command is the point:
    # a check nobody remembers to run catches nothing.
    suspect = 0
    if not args.dry_run and not args.no_check:
        suspect = _report_findings(args.db, show=3)
    return 1 if (failures or degraded or suspect) else 0


def cmd_export(args) -> int:
    import csv

    with Store(args.db) as store:
        rows = store.latest(args.site)
    if not rows:
        print("nothing stored yet — run a scrape first", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    print(f"{len(rows)} rows → {args.out}")
    return 0


def cmd_history(args) -> int:
    with Store(args.db) as store:
        rows = store.price_changes(args.site, args.limit)
    if not rows:
        print("no price changes recorded yet (needs at least two runs)")
        return 0
    for row in rows:
        old, new = row["old_price"], row["new_price"]
        arrow = "↑" if (new or 0) > (old or 0) else "↓"
        print(f"{row['changed_at'][:19]}  {row['retailer']:<12} {arrow} "
              f"{old} → {new}  {row['name'][:60]}")
    return 0


def cmd_stats(args) -> int:
    with Store(args.db) as store:
        rows = store.stats()
    if not rows:
        print("database is empty")
        return 0
    for row in rows:
        print(f"{row['retailer']:<12} {row['products']:>6} products   last seen {row['last_seen'][:19]}")
    return 0


def _report_findings(db: Path, site: str | None = None, show: int = 15) -> int:
    """Print the data checks over the latest stored prices. Returns the count."""
    from .validate import check, summarise

    with Store(db) as store:
        rows = [dict(r) for r in store.latest(site)]
        drift = store.retailer_drift()
    if not rows:
        print("database is empty")
        return 0

    findings = check(rows)
    print(f"\nchecked {len(rows):,} rows")
    if drift:
        print("run-over-run drift:")
        for d in drift:
            print(f"  {d['retailer']:<14} {d['previous']:>5} → {d['current']:<5} rows "
                  f"({d['change']:+.0%})")
    if not findings:
        print("no problems found")
        return 0

    counts = summarise(findings)
    print(f"{len(findings)} finding(s):")
    for kind, count in counts.items():
        print(f"  {kind:<22} {count}")
    for kind in counts:
        examples = [f for f in findings if f.kind == kind][:show]
        print(f"\n{kind}:")
        for f in examples:
            print(f"  {f.retailer:<14} {f.name[:56]:<56} {f.detail}")
    return len(findings)


def cmd_check(args) -> int:
    """Report rows that look wrong, so a run can be inspected before publishing."""
    # Findings are advisory: a real 2,541-lei bottle looks like an outlier too,
    # so this reports rather than fails.
    _report_findings(args.db, args.site, args.show)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(0 if getattr(args, "quiet", False) else getattr(args, "verbose", 1))
    handlers = {
        "run": cmd_run,
        "list-sites": cmd_list_sites,
        "export": cmd_export,
        "history": cmd_history,
        "stats": cmd_stats,
        "check": cmd_check,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
