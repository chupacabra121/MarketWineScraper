"""SQLite persistence with per-product price history."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import WineProduct

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY,
    retailer        TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    name            TEXT NOT NULL,
    brand           TEXT,
    producer        TEXT,
    url             TEXT,
    image_url       TEXT,
    volume_l        REAL,
    abv             REAL,
    vintage         INTEGER,
    colour          TEXT,
    sweetness       TEXT,
    sparkling       INTEGER,
    country         TEXT,
    region          TEXT,
    grape_varieties TEXT,
    category_path   TEXT,
    location        TEXT,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    raw             TEXT,
    UNIQUE (retailer, external_id)
);

CREATE TABLE IF NOT EXISTS price_observations (
    id              INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    observed_at     TEXT NOT NULL,
    price           REAL,
    currency        TEXT,
    list_price      REAL,
    unit_price      REAL,
    unit_price_unit TEXT,
    price_per_litre REAL,
    on_promotion    INTEGER,
    offer_type      TEXT,
    in_stock        INTEGER,
    run_id          INTEGER REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY,
    site          TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL,
    products_seen INTEGER DEFAULT 0,
    prices_added  INTEGER DEFAULT 0,
    message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_retailer ON products(retailer);
CREATE INDEX IF NOT EXISTS idx_obs_product ON price_observations(product_id, observed_at);
"""

# Added after the first databases were built, so it ships as a migration rather
# than in SCHEMA: an existing file must gain the column without being rebuilt.
_MIGRATIONS = [
    ("products", "wine_key", "ALTER TABLE products ADD COLUMN wine_key TEXT"),
    # What the wine was called when this price was seen. Retailers recycle
    # product ids — Carrefour reused two on consecutive days — and reading the
    # name off `products` at export time rewrote the past to match the present.
    ("price_observations", "name",
     "ALTER TABLE price_observations ADD COLUMN name TEXT"),
]
_MIGRATION_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_products_wine_key ON products(wine_key)",
)

_PRODUCT_FIELDS = (
    "name", "brand", "producer", "url", "image_url", "volume_l", "abv", "vintage",
    "colour", "sweetness", "sparkling", "country", "region", "grape_varieties",
    "category_path", "location", "raw",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class Store:
    """Thin wrapper over SQLite. Safe to use as a context manager."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a database was first written."""
        for table, column, statement in _MIGRATIONS:
            existing = {r["name"] for r in
                        self.conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                self.conn.execute(statement)
        for statement in _MIGRATION_INDEXES:
            self.conn.execute(statement)

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    # -- runs ------------------------------------------------------------
    def start_run(self, site: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (site, started_at, status) VALUES (?, ?, 'running')",
            (site, _now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, seen: int = 0,
                   added: int = 0, message: str | None = None) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, products_seen = ?, "
            "prices_added = ?, message = ? WHERE id = ?",
            (_now(), status, seen, added, message, run_id),
        )
        self.conn.commit()

    # -- products --------------------------------------------------------
    def upsert(self, product: WineProduct, run_id: int | None = None) -> tuple[int, bool]:
        """Insert or update a product and append a price observation.

        A new observation row is only written when the price actually moved,
        which keeps the history table meaningful across daily runs instead of
        growing by one identical row per product per run.
        """
        now = _now()
        row = self.conn.execute(
            "SELECT id FROM products WHERE retailer = ? AND external_id = ?",
            (product.retailer, product.external_id),
        ).fetchone()

        values = {
            "name": product.name,
            "brand": product.brand,
            "producer": product.producer,
            "url": product.url,
            "image_url": product.image_url,
            "volume_l": product.volume_l,
            "abv": product.abv,
            "vintage": product.vintage,
            "colour": product.colour,
            "sweetness": product.sweetness,
            "sparkling": int(product.sparkling) if product.sparkling is not None else None,
            "country": product.country,
            "region": product.region,
            "grape_varieties": ", ".join(product.grape_varieties) or None,
            "category_path": product.category_path,
            "location": product.location,
            "raw": json.dumps(product.raw, ensure_ascii=False) if product.raw else None,
        }

        if row is None:
            cols = ", ".join(("retailer", "external_id", *_PRODUCT_FIELDS, "first_seen", "last_seen"))
            marks = ", ".join(["?"] * (len(_PRODUCT_FIELDS) + 4))
            cur = self.conn.execute(
                f"INSERT INTO products ({cols}) VALUES ({marks})",
                (product.retailer, product.external_id,
                 *[values[f] for f in _PRODUCT_FIELDS], now, now),
            )
            product_id = int(cur.lastrowid)
        else:
            product_id = int(row["id"])
            assignments = ", ".join(f"{f} = ?" for f in _PRODUCT_FIELDS)
            self.conn.execute(
                f"UPDATE products SET {assignments}, last_seen = ? WHERE id = ?",
                (*[values[f] for f in _PRODUCT_FIELDS], now, product_id),
            )

        added = self._maybe_add_observation(product_id, product, run_id)
        return product_id, added

    def _maybe_add_observation(self, product_id: int, product: WineProduct,
                               run_id: int | None) -> bool:
        last = self.conn.execute(
            "SELECT price, list_price, on_promotion, in_stock FROM price_observations "
            "WHERE product_id = ? ORDER BY observed_at DESC, id DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        in_stock = int(product.in_stock) if product.in_stock is not None else None
        if last is not None:
            unchanged = (
                last["price"] == product.price
                and last["list_price"] == product.list_price
                and last["on_promotion"] == int(product.on_promotion)
                and last["in_stock"] == in_stock
            )
            if unchanged:
                return False
        # The name is stored with the observation, not looked up from the
        # product later: a retailer that reuses an id would otherwise relabel
        # every past price of the wine that used to hold it.
        self.conn.execute(
            "INSERT INTO price_observations (product_id, observed_at, name, price, "
            "currency, list_price, unit_price, unit_price_unit, price_per_litre, "
            "on_promotion, offer_type, in_stock, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (product_id, product.scraped_at.isoformat(), product.name, product.price,
             product.currency, product.list_price, product.unit_price,
             product.unit_price_unit, product.price_per_litre,
             int(product.on_promotion), product.offer_type, in_stock, run_id),
        )
        return True

    def save_all(self, products: Iterable[WineProduct], run_id: int | None = None) -> tuple[int, int]:
        seen = added = 0
        for product in products:
            _, was_added = self.upsert(product, run_id)
            seen += 1
            added += int(was_added)
        self.conn.commit()
        return seen, added

    # -- reads -----------------------------------------------------------
    def latest(self, retailer: str | None = None) -> list[sqlite3.Row]:
        """Most recent price observation per product still on sale.

        Products the retailer's most recent run did not see are left out: a wine
        that has been delisted is not a current price, and once a price series
        is carried across runs it would otherwise sit in "latest" forever at
        whatever it last cost. The comparison is per retailer and by day, so a
        run covering only some sites does not delist the rest.
        """
        sql = """
        SELECT p.*, o.price, o.currency, o.list_price, o.unit_price, o.unit_price_unit,
               o.price_per_litre, o.on_promotion, o.offer_type, o.in_stock, o.observed_at
        FROM products p
        JOIN price_observations o ON o.id = (
            SELECT id FROM price_observations
            WHERE product_id = p.id ORDER BY observed_at DESC, id DESC LIMIT 1
        )
        JOIN (
            SELECT retailer, MAX(substr(last_seen, 1, 10)) AS day
            FROM products GROUP BY retailer
        ) current ON current.retailer = p.retailer
                 AND substr(p.last_seen, 1, 10) = current.day
        """
        params: tuple = ()
        if retailer:
            sql += " WHERE p.retailer = ?"
            params = (retailer,)
        sql += " ORDER BY p.retailer, p.name"
        return self.conn.execute(sql, params).fetchall()

    def price_changes(self, retailer: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
        """Products whose most recent two observations differ, newest first."""
        sql = """
        WITH ranked AS (
            SELECT o.*, p.retailer, p.name, p.volume_l,
                   ROW_NUMBER() OVER (PARTITION BY o.product_id
                                      ORDER BY o.observed_at DESC, o.id DESC) AS rn
            FROM price_observations o
            JOIN products p ON p.id = o.product_id
            {where}
        )
        SELECT cur.retailer, cur.name, cur.volume_l,
               prev.price AS old_price, cur.price AS new_price,
               cur.observed_at AS changed_at
        FROM ranked cur
        JOIN ranked prev ON prev.product_id = cur.product_id AND prev.rn = 2
        WHERE cur.rn = 1 AND cur.price IS NOT prev.price
        ORDER BY cur.observed_at DESC
        LIMIT ?
        """.format(where="WHERE p.retailer = ?" if retailer else "")
        params = (retailer, limit) if retailer else (limit,)
        return self.conn.execute(sql, params).fetchall()

    def stats(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT retailer, COUNT(*) AS products, MAX(last_seen) AS last_seen "
            "FROM products GROUP BY retailer ORDER BY retailer"
        ).fetchall()

    def assign_wine_keys(self) -> dict[str, int]:
        """Work out which listings are the same wine, and record it.

        The key depends on the whole catalogue — the brand vocabulary is learned
        from the retailers that publish one, and an unstated attribute is
        resolved against the other listings of the same wine — so this runs over
        every row at once rather than per product.
        """
        from .identity import group_wines

        rows = [dict(r) for r in self.latest()]
        groups = group_wines(rows)
        updates = [(g.key, r["retailer"], str(r["external_id"]))
                   for g in groups for r in g.rows]
        self.conn.executemany(
            "UPDATE products SET wine_key = ? WHERE retailer = ? AND external_id = ?",
            updates)
        self.conn.commit()
        return {"listings": len(updates), "wines": len(groups),
                "shared": sum(1 for g in groups if len(g.retailers) > 1)}

    def wine_groups(self, min_retailers: int = 1) -> list[sqlite3.Row]:
        """Stored wines, widest distribution first."""
        return self.conn.execute(
            """
            SELECT p.wine_key,
                   COUNT(*) AS listings,
                   COUNT(DISTINCT p.retailer) AS retailers,
                   MIN(o.price) AS low, MAX(o.price) AS high,
                   MAX(p.name) AS example
            FROM products p
            JOIN price_observations o ON o.id = (
                SELECT id FROM price_observations
                WHERE product_id = p.id ORDER BY observed_at DESC, id DESC LIMIT 1
            )
            WHERE p.wine_key IS NOT NULL
            GROUP BY p.wine_key
            HAVING retailers >= ?
            ORDER BY retailers DESC, listings DESC, p.wine_key
            """, (min_retailers,)).fetchall()

    def wine(self, wine_key: str) -> list[sqlite3.Row]:
        """Every listing recorded under one wine key."""
        return self.conn.execute(
            """
            SELECT p.retailer, p.name, p.wine_key, p.volume_l, p.url,
                   o.price, o.on_promotion, o.observed_at
            FROM products p
            JOIN price_observations o ON o.id = (
                SELECT id FROM price_observations
                WHERE product_id = p.id ORDER BY observed_at DESC, id DESC LIMIT 1
            )
            WHERE p.wine_key = ?
            ORDER BY o.price
            """, (wine_key,)).fetchall()

    #: Fields ``reenrich`` may fill in. Read from the title, so they can only
    #: ever be a fallback for what the retailer did not publish.
    _DERIVED_FIELDS = ("volume_l", "abv", "vintage", "colour", "sweetness")

    def backfill_locations(self, locations: dict[str, str]) -> int:
        """Record which location a stored price belongs to, where it is missing.

        The location is a property of how the scraper was configured, not
        something read off the page, so it can be filled in for rows already
        collected without inferring anything or re-hitting a retailer.
        """
        filled = 0
        for retailer, location in locations.items():
            if not location:
                continue
            cursor = self.conn.execute(
                "UPDATE products SET location = ? "
                "WHERE retailer = ? AND (location IS NULL OR location = '')",
                (location, retailer))
            filled += cursor.rowcount
        self.conn.commit()
        return filled

    def reenrich(self) -> int:
        """Fill gaps in parsed fields from the stored product names.

        A fix to the normaliser is worth nothing to rows already collected, and
        a re-scrape is a poor way to apply one. This replays ``enrich`` over what
        is stored instead.

        It only writes where the column is NULL. Overwriting would be worse than
        doing nothing: METRO publishes colour and sweetness in a characteristics
        table and Auchan publishes grape varieties, none of which appear in the
        title, so re-deriving everything from the name silently replaces what a
        retailer stated with what could be guessed from its product name.
        """
        from .models import WineProduct
        from .normalize import enrich

        changed = 0
        for row in self.conn.execute("SELECT * FROM products").fetchall():
            gaps = [f for f in self._DERIVED_FIELDS if row[f] is None]
            if not gaps:
                continue
            product = WineProduct(
                retailer=row["retailer"], external_id=row["external_id"],
                name=row["name"], brand=row["brand"],
                category_path=row["category_path"],
            )
            enrich(product)
            filled = {f: getattr(product, f) for f in gaps
                      if getattr(product, f) is not None}
            if not filled:
                continue
            assignments = ", ".join(f"{f} = ?" for f in filled)
            self.conn.execute(f"UPDATE products SET {assignments} WHERE id = ?",
                              (*filled.values(), row["id"]))
            changed += 1
        self.conn.commit()
        return changed

    #: Columns of the portable history file. Enough to recreate the products a
    #: past price belongs to, and nothing more — attributes are re-derived on
    #: every scrape, so storing them here would only let them go stale.
    HISTORY_COLUMNS = ("observed_at", "retailer", "external_id", "name", "price",
                       "currency", "list_price", "on_promotion", "offer_type",
                       "in_stock")

    def export_history(self, path: str | Path) -> int:
        """Write every price observation as CSV.

        The database is a build artefact — a scheduled run rebuilds it from
        nothing — so the price series has to live somewhere that survives that.
        A sorted text file does, and unlike a SQLite binary it can be committed
        and diffed: each run appends the handful of prices that actually moved.
        """
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.conn.execute(
            """
            SELECT o.observed_at, p.retailer, p.external_id,
                   -- The observation's own name, so a recycled product id
                   -- cannot relabel a price recorded before it was reused.
                   -- COALESCE covers rows written before the column existed.
                   COALESCE(o.name, p.name) AS name,
                   o.price, o.currency, o.list_price, o.on_promotion,
                   o.offer_type, o.in_stock
            FROM price_observations o JOIN products p ON p.id = o.product_id
            ORDER BY o.observed_at, p.retailer, p.external_id
            """).fetchall()
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.HISTORY_COLUMNS)
            writer.writerows(tuple(r) for r in rows)
        return len(rows)

    def import_history(self, path: str | Path) -> int:
        """Load a previously exported series into an empty database.

        Runs before a scrape, so that the scrape can tell a price that moved
        from one it is seeing for the first time. Observations already present
        are left alone, which makes re-running it harmless.
        """
        import csv

        path = Path(path)
        if not path.exists():
            return 0
        loaded = 0
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                product_id = self._history_product(row)
                exists = self.conn.execute(
                    "SELECT 1 FROM price_observations "
                    "WHERE product_id = ? AND observed_at = ?",
                    (product_id, row["observed_at"])).fetchone()
                if exists:
                    continue
                self.conn.execute(
                    "INSERT INTO price_observations (product_id, observed_at, name, "
                    "price, currency, list_price, on_promotion, offer_type, in_stock) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (product_id, row["observed_at"], row["name"] or None,
                     _float(row["price"]), row["currency"] or None,
                     _float(row["list_price"]), _int(row["on_promotion"]),
                     row["offer_type"] or None, _int(row["in_stock"])))
                loaded += 1
        self.conn.commit()
        return loaded

    def _history_product(self, row: dict) -> int:
        """The product a historical observation belongs to, created if needed."""
        found = self.conn.execute(
            "SELECT id FROM products WHERE retailer = ? AND external_id = ?",
            (row["retailer"], row["external_id"])).fetchone()
        if found:
            return found["id"]
        cursor = self.conn.execute(
            "INSERT INTO products (retailer, external_id, name, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (row["retailer"], row["external_id"], row["name"],
             row["observed_at"], row["observed_at"]))
        return cursor.lastrowid

    def digest(self, limit: int = 10) -> dict:
        """What changed since the previous run.

        A price series nobody reads is a table; this is the part that makes it a
        report. Products appearing for the first time in the most recent run are
        new listings, products not seen in it have gone, and everything else is
        a price that moved.
        """
        # Anchored on last_seen, not on the newest observation: a price that did
        # not move writes no observation, so on a quiet day the observations
        # would say no run happened at all.
        latest = self.conn.execute("SELECT MAX(last_seen) FROM products").fetchone()[0]
        if not latest:
            return {"since": None, "runs": 0}
        day = latest[:10]

        previous = self.conn.execute(
            "SELECT MAX(observed_at) FROM price_observations WHERE observed_at < ?",
            (day,)).fetchone()[0]
        if not previous:
            return {"since": None, "runs": 1, "today": day}

        moves = [dict(r) for r in self.conn.execute(
            """
            WITH ranked AS (
                SELECT o.product_id, o.price, o.observed_at,
                       ROW_NUMBER() OVER (PARTITION BY o.product_id
                                          ORDER BY o.observed_at DESC, o.id DESC) AS rn
                FROM price_observations o
            )
            SELECT p.retailer, p.name, p.wine_key,
                   prev.price AS old_price, cur.price AS new_price,
                   (cur.price - prev.price) / prev.price AS change
            FROM ranked cur
            JOIN ranked prev ON prev.product_id = cur.product_id AND prev.rn = 2
            JOIN products p ON p.id = cur.product_id
            WHERE cur.rn = 1 AND cur.observed_at >= ?
              AND cur.price IS NOT NULL AND prev.price > 0
              AND cur.price != prev.price
            ORDER BY ABS((cur.price - prev.price) / prev.price) DESC
            """, (day,))]

        # Scoped per retailer, like `latest`: a run covering some sites must not
        # report every other site's whole catalogue as delisted.
        current = """
            SELECT retailer, MAX(substr(last_seen, 1, 10)) AS day
            FROM products GROUP BY retailer
        """
        appeared = [dict(r) for r in self.conn.execute(
            f"SELECT p.retailer, p.name, p.wine_key FROM products p "
            f"JOIN ({current}) c ON c.retailer = p.retailer "
            f"WHERE substr(p.first_seen, 1, 10) = c.day AND c.day >= ? "
            f"ORDER BY p.retailer, p.name", (day,))]
        gone = [dict(r) for r in self.conn.execute(
            f"SELECT p.retailer, p.name, p.wine_key FROM products p "
            f"JOIN ({current}) c ON c.retailer = p.retailer "
            f"WHERE substr(p.last_seen, 1, 10) < c.day "
            f"ORDER BY p.retailer, p.name")]

        drops = [m for m in moves if m["change"] < 0]
        rises = [m for m in moves if m["change"] > 0]
        return {
            "since": previous[:10], "today": day, "runs": 2,
            "moved": len(moves), "down": len(drops), "up": len(rises),
            "appeared": appeared, "gone": gone,
            "biggest_drops": drops[:limit],
            "biggest_rises": sorted(rises, key=lambda m: -m["change"])[:limit],
        }

    def retailer_drift(self, threshold: float = 0.10) -> list[dict]:
        """Retailers whose row count moved sharply against their previous run.

        Every specific check in ``validate`` tests something someone thought to
        look for. This one does not: it just compares each retailer against
        itself a run ago, which is how a problem nobody predicted — a category
        renamed, a filter over-matching, an endpoint quietly paginating
        differently — shows up first.
        """
        rows = self.conn.execute(
            """
            WITH ok AS (
                SELECT site, products_seen,
                       ROW_NUMBER() OVER (PARTITION BY site
                                          ORDER BY started_at DESC, id DESC) AS rn
                FROM runs WHERE status = 'ok'
            )
            SELECT c.site AS retailer, p.products_seen AS previous,
                   c.products_seen AS current
            FROM ok c JOIN ok p ON p.site = c.site AND p.rn = 2
            WHERE c.rn = 1 AND p.products_seen > 0
            ORDER BY c.site
            """
        ).fetchall()
        drift = []
        for row in rows:
            change = (row["current"] - row["previous"]) / row["previous"]
            if abs(change) >= threshold:
                drift.append({"retailer": row["retailer"], "previous": row["previous"],
                              "current": row["current"], "change": change})
        return drift


def open_store(path: str | Path) -> Store:
    return Store(path)


__all__ = ["Store", "open_store", "closing"]
