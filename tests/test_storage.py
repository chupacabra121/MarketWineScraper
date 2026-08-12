"""Tests for SQLite persistence and price history."""

import csv
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


# ------------------------------------------------ carrying history forward

def _observed_on(store, day: str) -> None:
    """Backdate everything, so a second run reads as a different day."""
    store.conn.execute("UPDATE price_observations SET observed_at = ?", (day,))
    store.conn.execute("UPDATE products SET first_seen = ?, last_seen = ?", (day, day))
    store.conn.commit()


def test_history_survives_a_rebuilt_database(tmp_path):
    """The exact shape of a scheduled run: the database is a build artefact and
    starts empty, so yesterday's prices come back from a committed CSV. Without
    that, every price looks new and nothing is ever recorded as having moved."""
    history = tmp_path / "price-history.csv"

    with Store(tmp_path / "day1.sqlite") as day1:
        day1.save_all([make(30.0, external_id="a"), make(50.0, external_id="b")])
        _observed_on(day1, "2026-08-10T09:00:00+00:00")
        assert day1.export_history(history) == 2

    with Store(tmp_path / "day2.sqlite") as day2:
        assert day2.import_history(history) == 2
        # "a" moved, "b" did not, "c" is new.
        day2.save_all([make(27.0, external_id="a"), make(50.0, external_id="b"),
                       make(19.0, external_id="c")])
        d = day2.digest()

    assert d["runs"] == 2 and d["since"] == "2026-08-10"
    assert (d["moved"], d["down"], d["up"]) == (1, 1, 0)
    assert d["biggest_drops"][0]["old_price"] == 30.0
    assert d["biggest_drops"][0]["new_price"] == 27.0
    assert [p["name"] for p in d["appeared"]] == ["Vin rosu sec 0.75L"]


def test_importing_twice_changes_nothing(tmp_path):
    history = tmp_path / "h.csv"
    with Store(tmp_path / "a.sqlite") as s:
        s.save_all([make(30.0)])
        s.export_history(history)
    with Store(tmp_path / "b.sqlite") as s:
        assert s.import_history(history) == 1
        assert s.import_history(history) == 0
        assert s.conn.execute(
            "SELECT COUNT(*) c FROM price_observations").fetchone()["c"] == 1


def test_importing_a_missing_file_is_not_an_error(tmp_path):
    with Store(tmp_path / "a.sqlite") as s:
        assert s.import_history(tmp_path / "nothing.csv") == 0


def test_digest_reports_a_delisted_wine(tmp_path):
    with Store(tmp_path / "a.sqlite") as s:
        s.save_all([make(30.0, external_id="a"), make(50.0, external_id="b")])
        _observed_on(s, "2026-08-10T09:00:00+00:00")
        s.save_all([make(30.0, external_id="a")])       # "b" is no longer offered
        d = s.digest()
    assert [g["retailer"] for g in d["gone"]] == ["testmart"]


def test_digest_says_so_when_there_is_only_one_run(tmp_path):
    with Store(tmp_path / "a.sqlite") as s:
        s.save_all([make(30.0)])
        assert s.digest()["runs"] == 1


def test_digest_on_an_empty_database(tmp_path):
    with Store(tmp_path / "a.sqlite") as s:
        assert s.digest()["runs"] == 0


def test_a_delisted_wine_leaves_the_latest_prices(store):
    """Carrying a price series forward would otherwise leave a wine that is no
    longer sold sitting in "latest" at whatever it last cost."""
    store.upsert(make(30.0, external_id="a"))
    store.upsert(make(50.0, external_id="b"))
    _observed_on(store, "2026-08-10T09:00:00+00:00")
    store.upsert(make(30.0, external_id="a"))          # only "a" is still offered
    store.conn.commit()
    assert [r["external_id"] for r in store.latest()] == ["a"]


def test_one_retailer_running_does_not_delist_the_others(store):
    """A run covering some sites must not drop the rest out of the data."""
    store.upsert(make(30.0, external_id="a"))
    store.upsert(WineProduct(retailer="othermart", external_id="z",
                             name="Vin alb sec 0.75L", price=40.0, volume_l=0.75))
    _observed_on(store, "2026-08-10T09:00:00+00:00")
    store.upsert(make(31.0, external_id="a"))          # testmart alone re-runs
    store.conn.commit()
    assert {r["retailer"] for r in store.latest()} == {"testmart", "othermart"}


def test_a_recycled_product_id_does_not_relabel_past_prices(tmp_path):
    """Carrefour reused two product ids for different wines on consecutive
    days. The name used to be read off `products` when the history was
    exported, so yesterday's row picked up today's wine — a price series that
    silently rewrites its own past."""
    history = tmp_path / "h.csv"
    with Store(tmp_path / "a.sqlite") as store:
        store.save_all([make(18.49, external_id="10005615",
                             name="Vin rose Sigillum Moldaviae, Demisec, 0.75L")])
        _observed_on(store, "2026-08-11T09:36:21+00:00")
        # Same id, different wine, different price.
        store.save_all([make(21.99, external_id="10005615",
                             name="Vin alb demidulce Domeniile Recas Gewurtztraminer")])
        store.export_history(history)

    rows = list(csv.DictReader(history.open(encoding="utf-8")))
    assert [r["name"] for r in rows] == [
        "Vin rose Sigillum Moldaviae, Demisec, 0.75L",
        "Vin alb demidulce Domeniile Recas Gewurtztraminer",
    ]


def test_an_exported_name_survives_a_round_trip(tmp_path):
    history = tmp_path / "h.csv"
    with Store(tmp_path / "a.sqlite") as store:
        store.save_all([make(18.49, external_id="x", name="Vin rosu sec Alira, 0.75L")])
        store.export_history(history)
    with Store(tmp_path / "b.sqlite") as store:
        store.import_history(history)
        store.export_history(history)
    rows = list(csv.DictReader(history.open(encoding="utf-8")))
    assert [r["name"] for r in rows] == ["Vin rosu sec Alira, 0.75L"]


def test_history_written_before_the_name_column_still_exports(tmp_path):
    """Databases predating the column fall back to the product name, which is
    the best that can be recovered for them."""
    path = tmp_path / "old.sqlite"
    with Store(path) as store:
        store.save_all([make(30.0, external_id="a", name="Vin alb sec 0.75L")])
        store.conn.execute("UPDATE price_observations SET name = NULL")
        store.conn.commit()
        store.export_history(tmp_path / "h.csv")
    rows = list(csv.DictReader((tmp_path / "h.csv").open(encoding="utf-8")))
    assert rows[0]["name"] == "Vin alb sec 0.75L"


def test_importing_the_series_does_not_delist_the_catalogue(tmp_path):
    """A history import creates products from observations alone.

    Those carry the observation's date, and a few of them dated later than the
    last scrape used to redefine "today" for the whole retailer, dropping every
    genuinely current listing out of ``latest``.
    """
    from winescraper.models import WineProduct

    store = Store(tmp_path / "w.sqlite")
    for n in range(3):
        store.upsert(WineProduct(retailer="shop", external_id=str(n),
                                 name=f"Vin {n}", price=10.0 + n, volume_l=0.75),
                     run_id=store.start_run("shop"))
    assert len(store.latest()) == 3

    history = tmp_path / "history.csv"
    history.write_text(
        ",".join(Store.HISTORY_COLUMNS) + "\n"
        # A price recorded the next day, for a product the scrape never saw.
        "2099-01-02T00:00:00+00:00,shop,99,Vin nou,12.0,RON,,0,catalogue,1,0.5\n")
    store.import_history(history)

    still_listed = {r["external_id"] for r in store.latest()}
    assert still_listed == {"0", "1", "2"}
    store.close()


def test_the_deposit_survives_a_history_round_trip(tmp_path):
    from winescraper.models import WineProduct

    source = Store(tmp_path / "a.sqlite")
    source.upsert(WineProduct(retailer="metro", external_id="1", name="Vin SGR 0,75 L",
                              price=13.31, volume_l=0.75))
    source.upsert(WineProduct(retailer="metro", external_id="2",
                              name="Cotnari Bag in Box 3 L", price=42.15, volume_l=3.0))
    path = tmp_path / "history.csv"
    source.export_history(path)
    source.close()

    copy = Store(tmp_path / "b.sqlite")
    copy.import_history(path)
    deposits = {r["external_id"]: r["deposit"] for r in copy.latest()}
    assert deposits == {"1": 0.5, "2": 0.0}
    copy.close()
