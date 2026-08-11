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
# Committed alongside the code: these are human judgements about a
# catalogue, not derived data, and they must outlive any rebuilt database.
DEFAULT_DECISIONS = Path("decisions.jsonl")


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

    changes = sub.add_parser("changes", parents=[common],
                             help="what moved since the previous run")
    changes.add_argument("--db", type=Path, default=DEFAULT_DB)
    changes.add_argument("--limit", type=int, default=10,
                         help="movers to list in each direction")

    fix = sub.add_parser("reenrich", parents=[common],
                         help="apply current parsing to rows already collected")
    fix.add_argument("--db", type=Path, default=DEFAULT_DB)

    hist = sub.add_parser("history-file", parents=[common],
                          help="move the price series in or out of a portable CSV")
    hist.add_argument("action", choices=("export", "import"))
    hist.add_argument("--db", type=Path, default=DEFAULT_DB)
    hist.add_argument("--path", type=Path, default=Path("data/price-history.csv"))

    stats = sub.add_parser("stats", parents=[common], help="row counts per retailer")
    stats.add_argument("--db", type=Path, default=DEFAULT_DB)

    wines = sub.add_parser("wines", parents=[common],
                           help="the same wine across retailers, by wine key")
    wines.add_argument("--db", type=Path, default=DEFAULT_DB)
    wines.add_argument("--key", help="show every listing under one wine key")
    wines.add_argument("--min-retailers", type=int, default=2,
                       help="only wines carried by at least this many (default 2)")
    wines.add_argument("--limit", type=int, default=25)
    wines.add_argument("--reassign", action="store_true",
                       help="recompute the keys before showing them")

    checks = sub.add_parser("check", parents=[common],
                            help="look for implausible prices and non-wine rows")
    checks.add_argument("--db", type=Path, default=DEFAULT_DB)
    checks.add_argument("--site", dest="site")
    checks.add_argument("--show", type=int, default=15,
                        help="rows to print per finding type")
    checks.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    checks.add_argument("--all", dest="include_settled", action="store_true",
                        help="include findings already decided")

    decide = sub.add_parser("decide", parents=[common],
                            help="record a judgement so a finding stops recurring")
    decide.add_argument("finding", help="the finding kind, e.g. 'review' or 'not wine'")
    decide.add_argument("verdict", choices=("wine", "exclude", "noted"),
                        help="wine = the flag was wrong; exclude = drop the listing; "
                             "noted = real but unfixable, stop reporting it")
    decide.add_argument("--retailer")
    decide.add_argument("--id", dest="external_id")
    decide.add_argument("--wine", dest="wine_key", help="for findings about a whole wine")
    decide.add_argument("--note", default="", help="why — this is the part worth keeping")
    decide.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)

    decided = sub.add_parser("decisions", parents=[common],
                             help="show the judgements recorded so far")
    decided.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)

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

    # Identity depends on the whole catalogue, so it is recomputed once the run
    # is complete rather than per product as rows arrive.
    if not args.dry_run:
        with Store(args.db) as store:
            counts = store.assign_wine_keys()
        print(f"{counts['wines']:,} distinct wines, "
              f"{counts['shared']:,} carried by more than one retailer")

    # Validating here rather than leaving it to a separate command is the point:
    # a check nobody remembers to run catches nothing.
    suspect = 0
    if not args.dry_run and not args.no_check:
        suspect = _report_findings(args.db, show=3,
                                   decisions_path=DEFAULT_DECISIONS)
    return 1 if (failures or degraded or suspect) else 0


def cmd_export(args) -> int:
    import csv

    from . import decisions as dec

    with Store(args.db) as store:
        rows = [dict(r) for r in store.latest(args.site)]
    rows, dropped = dec.filter_rows(rows, dec.load(DEFAULT_DECISIONS))
    if dropped:
        print(f"{dropped} listing(s) excluded by decision", file=sys.stderr)
    if not rows:
        print("nothing stored yet — run a scrape first", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
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


def cmd_changes(args) -> int:
    """The run-over-run digest: what is new, what has gone, what moved."""
    with Store(args.db) as store:
        d = store.digest(args.limit)
    if not d.get("runs"):
        print("nothing stored yet — run a scrape first")
        return 0
    if d["runs"] < 2:
        print(f"only one run stored ({d['today']}). Price history needs a second "
              "run to compare against.")
        return 0

    print(f"{d['since']} → {d['today']}\n")
    print(f"  {d['moved']:>5} price(s) moved   {d['down']} down, {d['up']} up")
    print(f"  {len(d['appeared']):>5} new listing(s)")
    print(f"  {len(d['gone']):>5} listing(s) no longer offered")

    for label, movers in (("biggest drops", d["biggest_drops"]),
                          ("biggest rises", d["biggest_rises"])):
        if not movers:
            continue
        print(f"\n{label}:")
        for m in movers:
            print(f"  {m['retailer']:<14} {m['old_price']:>8.2f} → {m['new_price']:<8.2f} "
                  f"{m['change']:>+7.0%}  {m['name'][:48]}")

    for label, items in (("new", d["appeared"]), ("gone", d["gone"])):
        if not items:
            continue
        print(f"\n{label} ({len(items)}):")
        for item in items[:args.limit]:
            print(f"  {item['retailer']:<14} {item['name'][:60]}")
        if len(items) > args.limit:
            print(f"  {'':<14} … and {len(items) - args.limit} more")
    return 0


def cmd_reenrich(args) -> int:
    """Bring stored rows up to date with the current code, without scraping.

    A fix to the normaliser is worth nothing to rows already collected, and a
    re-scrape is a poor way to apply one. Only gaps are filled: a value the
    retailer published is never replaced by one read off its own product name.
    """
    from .sites import scrapable_adapters

    locations = {key: cls(fetcher=None).location
                 for key, cls in scrapable_adapters().items()}
    with Store(args.db) as store:
        located = store.backfill_locations(locations)
        parsed = store.reenrich()
        keys = store.assign_wine_keys()
    print(f"{located:,} row(s) given a location, {parsed:,} row(s) re-parsed")
    print(f"{keys['wines']:,} distinct wines, "
          f"{keys['shared']:,} carried by more than one retailer")
    return 0


def cmd_history_file(args) -> int:
    """Carry the price series across rebuilds of the database.

    A scheduled run starts from an empty database, so the series has to be
    imported before the scrape (or every price looks new) and exported after.
    """
    with Store(args.db) as store:
        if args.action == "export":
            count = store.export_history(args.path)
            print(f"{count:,} observation(s) → {args.path}")
        else:
            count = store.import_history(args.path)
            print(f"{count:,} observation(s) loaded from {args.path}")
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


def _report_findings(db: Path, site: str | None = None, show: int = 15,
                     decisions_path: Path | None = None,
                     include_settled: bool = False) -> int:
    """Print the data checks over the latest stored prices. Returns the count."""
    from . import decisions as dec
    from .validate import check, summarise

    with Store(db) as store:
        rows = [dict(r) for r in store.latest(site)]
        drift = store.retailer_drift()
    if not rows:
        print("database is empty")
        return 0

    log = dec.load(decisions_path) if decisions_path else dec.DecisionLog()
    rows, dropped = dec.filter_rows(rows, log)
    findings = check(rows)
    settled = 0
    if not include_settled:
        findings, settled = dec.apply(findings, log)

    print(f"\nchecked {len(rows):,} rows"
          + (f" ({dropped} excluded by decision)" if dropped else ""))
    if drift:
        print("run-over-run drift:")
        for d in drift:
            print(f"  {d['retailer']:<14} {d['previous']:>5} → {d['current']:<5} rows "
                  f"({d['change']:+.0%})")
    if settled:
        print(f"{settled} finding(s) already decided — see 'winescraper decisions'")
    if not findings:
        print("no open findings")
        return 0

    counts = summarise(findings)
    print(f"{len(findings)} open finding(s):")
    for kind, count in counts.items():
        print(f"  {kind:<22} {count}")
    for kind in counts:
        examples = [f for f in findings if f.kind == kind][:show]
        print(f"\n{kind}:")
        for f in examples:
            print(f"  {f.retailer:<14} {f.name[:56]:<56} {f.detail}")
        if examples:
            print(f"    settle one with: winescraper decide '{kind}' "
                  f"<wine|exclude|noted> {examples[0].target}")
    return len(findings)


def cmd_wines(args) -> int:
    """Show wines rather than listings: one row per wine, priced by each shop."""
    with Store(args.db) as store:
        if args.reassign:
            counts = store.assign_wine_keys()
            print(f"{counts['listings']:,} listings → {counts['wines']:,} wines, "
                  f"{counts['shared']:,} carried by more than one retailer\n")

        if args.key:
            rows = store.wine(args.key)
            if not rows:
                print(f"no listings under '{args.key}'", file=sys.stderr)
                return 1
            prices = [r["price"] for r in rows if r["price"]]
            print(f"{args.key}\n{len(rows)} listing(s), "
                  f"{prices[0]:.2f}–{prices[-1]:.2f} RON "
                  f"({prices[-1] / prices[0] - 1:+.0%})\n")
            for row in rows:
                promo = " promo" if row["on_promotion"] else ""
                print(f"  {row['retailer']:<14} {row['price']:>8.2f}{promo:<6} {row['name'][:58]}")
            return 0

        groups = store.wine_groups(args.min_retailers)
        if not groups:
            print("no wine keys stored yet — run with --reassign")
            return 0
        print(f"{len(groups):,} wines carried by {args.min_retailers}+ retailers\n")
        print(f"  {'shops':>5} {'low':>8} {'high':>8} {'gap':>6}  wine")
        for row in groups[:args.limit]:
            gap = (row["high"] / row["low"] - 1) if row["low"] else 0
            print(f"  {row['retailers']:>5} {row['low']:>8.2f} {row['high']:>8.2f} "
                  f"{gap:>5.0%}  {row['wine_key']}")
        return 0


def cmd_check(args) -> int:
    """Report rows that look wrong, so a run can be inspected before publishing."""
    # Findings are advisory: a real 2,541-lei bottle looks like an outlier too,
    # so this reports rather than fails.
    _report_findings(args.db, args.site, args.show, args.decisions,
                     args.include_settled)
    return 0


def cmd_decide(args) -> int:
    """Record a judgement about a finding so it stops coming back."""
    from . import decisions as dec

    try:
        decision = dec.record(args.decisions, dec.Decision(
            finding=args.finding, verdict=args.verdict,
            retailer=args.retailer or "", external_id=args.external_id or "",
            wine_key=args.wine_key or "", note=args.note))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    what = decision.wine_key or f"{decision.retailer}/{decision.external_id}"
    print(f"recorded: {decision.finding} on {what} → {decision.verdict}")
    if decision.verdict == "exclude":
        print("the listing is now dropped from exports and reports")
    return 0


def cmd_decisions(args) -> int:
    from . import decisions as dec

    log = dec.load(args.decisions)
    if not log.decisions:
        print(f"no decisions recorded in {args.decisions}")
        return 0
    print(f"{len(log.decisions)} decision(s) in {args.decisions}\n")
    for d in log.decisions:
        what = d.wine_key or f"{d.retailer}/{d.external_id}"
        print(f"  {d.decided_at[:10]}  {d.verdict:<8} {d.finding:<20} {what}")
        if d.note:
            print(f"  {'':<12}└─ {d.note}")
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
        "wines": cmd_wines,
        "changes": cmd_changes,
        "history-file": cmd_history_file,
        "reenrich": cmd_reenrich,
        "decide": cmd_decide,
        "decisions": cmd_decisions,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
