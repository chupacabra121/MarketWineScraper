"""Tests for SQLite persistence and price history."""

from datetime import datetime, timedelta, timezone

import pytest

from winescraper.models import WineProduct
from winescraper.storage import Store


def make(price, *, external_id="1", name="Vin rosu sec 0.75L", **kwargs):
    return WineProduct(retailer="testmart", external_id=external_id, name=name,
                       price=price, volume_l=0.75, **kwargs)


@pytest.fixture()
def store(tmp_path):
    with Store(tmp_path / "test.sqlite") as s:
        yield s


def test_upsert_inserts_once_and_updates_in_place(store):
    store.upsert(make(30.0))
    store.upsert(make(30.0))
    store.conn.commit()
    rows = store.conn.execute("SELECT COUNT(*) c FROM products").fetchone()
    assert rows["c"] == 1


def test_observation_only_written_when_price_moves(store):
    store.upsert(make(30.0))
    _, added_same = store.upsert(make(30.0))
    assert added_same is False

    _, added_changed = store.upsert(make(27.5))
    assert added_changed is True

    store.conn.commit()
    count = store.conn.execute(
        "SELECT COUNT(*) c FROM price_observations").fetchone()["c"]
    assert count == 2


def test_stock_change_alone_records_an_observation(store):
    store.upsert(make(30.0, in_stock=True))
    _, added = store.upsert(make(30.0, in_stock=False))
    assert added is True


def test_price_changes_reports_old_and_new(store):
    now = datetime.now(timezone.utc)
    store.upsert(make(30.0, scraped_at=now - timedelta(days=1)))
    store.upsert(make(24.0, scraped_at=now))
    store.conn.commit()

    changes = store.price_changes()
    assert len(changes) == 1
    assert changes[0]["old_price"] == 30.0
    assert changes[0]["new_price"] == 24.0


def test_latest_returns_most_recent_observation_per_product(store):
    now = datetime.now(timezone.utc)
    store.upsert(make(30.0, scraped_at=now - timedelta(days=2)))
    store.upsert(make(21.0, scraped_at=now))
    store.upsert(make(45.0, external_id="2", name="Vin alb sec 0.75L"))
    store.conn.commit()

    rows = {r["external_id"]: r for r in store.latest()}
    assert len(rows) == 2
    assert rows["1"]["price"] == 21.0
    assert rows["1"]["price_per_litre"] == 28.0


def test_products_are_scoped_per_retailer(store):
    store.upsert(make(30.0))
    other = WineProduct(retailer="othermart", external_id="1", name="Vin rosu", price=30.0)
    store.upsert(other)
    store.conn.commit()
    assert store.conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 2


def test_run_bookkeeping(store):
    run_id = store.start_run("testmart")
    seen, added = store.save_all([make(30.0), make(40.0, external_id="2")], run_id)
    store.finish_run(run_id, "ok", seen=seen, added=added)

    row = store.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row["status"] == "ok"
    assert row["products_seen"] == 2
    assert row["prices_added"] == 2
    assert row["finished_at"] is not None


def test_stats(store):
    store.save_all([make(30.0), make(40.0, external_id="2")])
    stats = store.stats()
    assert stats[0]["retailer"] == "testmart"
    assert stats[0]["products"] == 2


def test_retailer_drift_flags_a_collapsed_run(tmp_path):
    """A retailer that halves between runs is the shape of a silent truncation."""
    with Store(tmp_path / "d.sqlite") as store:
        for site, seen in [("mega_image", 218), ("auchan", 860),
                           ("mega_image", 146), ("auchan", 864)]:
            run_id = store.start_run(site)
            store.finish_run(run_id, "ok", seen=seen, added=seen)
        drift = {d["retailer"]: d for d in store.retailer_drift()}
    assert set(drift) == {"mega_image"}
    assert drift["mega_image"]["previous"] == 218
    assert drift["mega_image"]["current"] == 146
    assert drift["mega_image"]["change"] == pytest.approx(-0.330, abs=0.001)


def test_retailer_drift_ignores_failed_runs(tmp_path):
    """A run that errored has no count to compare against."""
    with Store(tmp_path / "d.sqlite") as store:
        ok = store.start_run("selgros")
        store.finish_run(ok, "ok", seen=500, added=500)
        bad = store.start_run("selgros")
        store.finish_run(bad, "error", message="HTTP 400")
        assert store.retailer_drift() == []


def test_retailer_drift_needs_two_runs(tmp_path):
    with Store(tmp_path / "d.sqlite") as store:
        run_id = store.start_run("penny")
        store.finish_run(run_id, "ok", seen=32, added=32)
        assert store.retailer_drift() == []
