"""Orchestration: run one or more adapters, persist and export the results."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .browser import BrowserSession
from .fetch import Fetcher
from .models import WineProduct
from .sites import get_adapter, scrapable_adapters
from .storage import Store

log = logging.getLogger(__name__)


class WarningCounter(logging.Handler):
    """Count warnings emitted while one adapter runs.

    Adapters log-and-continue on a failed page so that one bad response cannot
    lose a whole run. The cost is that a degraded run and a clean one print the
    same summary. Counting the warnings makes the difference visible without
    editing the recovery logic in thirteen adapters.
    """

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.count = 0
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1
        if len(self.messages) < 10:
            self.messages.append(record.getMessage())


@dataclass
class SiteResult:
    site: str
    products: list[WineProduct] = field(default_factory=list)
    saved: int = 0
    price_changes: int = 0
    status: str = "ok"
    error: str | None = None
    #: Recoverable failures — a page that 500ed, a batch that timed out.
    warnings: int = 0
    warning_samples: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.products)

    @property
    def degraded(self) -> bool:
        """Completed, but not cleanly: some of the catalogue may be missing."""
        return self.status == "ok" and self.warnings > 0


@dataclass
class RunOptions:
    limit: int | None = None
    delay: float = 1.0
    use_cache: bool = True
    cache_dir: Path = Path(".cache/http")
    db_path: Path = Path("data/wines.sqlite")
    dry_run: bool = False
    site_config: dict[str, dict] = field(default_factory=dict)


async def run_sites(keys: list[str], options: RunOptions) -> list[SiteResult]:
    """Scrape each requested site, persisting unless ``dry_run`` is set.

    A browser is started only if at least one selected adapter needs one, so the
    common case (API-backed sites) stays fast.
    """
    adapters = {key: get_adapter(key) for key in keys}
    needs_browser = any(cls.needs_browser for cls in adapters.values())

    results: list[SiteResult] = []
    store = None if options.dry_run else Store(options.db_path)

    try:
        async with Fetcher(delay=options.delay, cache_dir=options.cache_dir,
                           use_cache=options.use_cache) as fetcher:
            browser_ctx = BrowserSession() if needs_browser else None
            browser = await browser_ctx.__aenter__() if browser_ctx else None
            try:
                for key, cls in adapters.items():
                    results.append(
                        await _run_one(key, cls, fetcher, browser, store, options)
                    )
            finally:
                if browser_ctx is not None:
                    await browser_ctx.__aexit__(None, None, None)
    finally:
        if store is not None:
            store.close()
    return results


async def _run_one(key, cls, fetcher, browser, store, options: RunOptions) -> SiteResult:
    result = SiteResult(site=key)
    if cls.catalogue == "none":
        result.status = "unsupported"
        result.error = cls.note
        log.info("[%s] skipped — %s", key, cls.note)
        return result

    run_id = store.start_run(key) if store else None
    adapter = cls(fetcher, limit=options.limit, browser=browser,
                  config=options.site_config.get(key, {}))
    counter = WarningCounter()
    root = logging.getLogger("winescraper")
    root.addHandler(counter)
    try:
        log.info("[%s] scraping…", key)
        result.products = await adapter.scrape()
    except Exception as exc:
        result.status = "error"
        result.error = f"{type(exc).__name__}: {exc}"
        log.exception("[%s] failed", key)
        if store and run_id is not None:
            store.finish_run(run_id, "error", message=result.error)
        return result
    finally:
        root.removeHandler(counter)
        result.warnings = counter.count
        result.warning_samples = counter.messages

    log.info("[%s] %d wines", key, result.count)
    if result.degraded:
        log.warning("[%s] completed with %d recoverable failure(s); the "
                    "catalogue may be incomplete", key, result.warnings)
    if store and run_id is not None:
        seen, added = store.save_all(result.products, run_id)
        result.saved, result.price_changes = seen, added
        store.finish_run(run_id, "ok", seen=seen, added=added)
    return result


def resolve_sites(requested: list[str] | None, include_all: bool) -> list[str]:
    """Turn CLI selectors into a list of adapter keys."""
    if include_all:
        return list(scrapable_adapters())
    if not requested:
        raise SystemExit("pick at least one --site, or pass --all")
    return requested
