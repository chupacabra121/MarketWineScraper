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

_PRODUCT_FIELDS = (
    "name", "brand", "producer", "url", "image_url", "volume_l", "abv", "vintage",
    "colour", "sweetness", "sparkling", "country", "region", "grape_varieties",
    "category_path", "location", "raw",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        self.conn.commit()

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
        self.conn.execute(
            "INSERT INTO price_observations (product_id, observed_at, price, currency, "
            "list_price, unit_price, unit_price_unit, price_per_litre, on_promotion, "
            "offer_type, in_stock, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (product_id, product.scraped_at.isoformat(), product.price, product.currency,
             product.list_price, product.unit_price, product.unit_price_unit,
             product.price_per_litre, int(product.on_promotion), product.offer_type,
             in_stock, run_id),
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
        """Most recent price observation per product."""
        sql = """
        SELECT p.*, o.price, o.currency, o.list_price, o.unit_price, o.price_per_litre,
               o.on_promotion, o.offer_type, o.in_stock, o.observed_at
        FROM products p
        JOIN price_observations o ON o.id = (
            SELECT id FROM price_observations
            WHERE product_id = p.id ORDER BY observed_at DESC, id DESC LIMIT 1
        )
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


def open_store(path: str | Path) -> Store:
    return Store(path)


__all__ = ["Store", "open_store", "closing"]
