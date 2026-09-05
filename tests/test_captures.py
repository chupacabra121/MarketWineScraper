"""Shelf prices read by hand, for the chains no scraper reaches."""

from __future__ import annotations

import pytest

from winescraper import captures, deposit, pricing
from winescraper.storage import Store

HEADER = ",".join(captures.COLUMNS) + "\n"


def write(tmp_path, *lines):
    path = tmp_path / "captures.csv"
    path.write_text(HEADER + "".join(lines), encoding="utf-8")
    return path


def test_a_captured_row_becomes_a_product(tmp_path):
    path = write(tmp_path,
                 "2026-08-12,froo,froo-bucuresti,Babanu Vin rosu demidulce 2L,"
                 "Babanu,2,13.99,16.99,ioan,raft\n")
    product, = captures.read(path)
    assert product.retailer == "froo"
    assert product.price == 13.99
    assert product.list_price == 16.99      # a promotion, since it is higher
    assert product.on_promotion
    assert product.volume_l == 2.0
    assert product.raw["source"] == "shelf capture"
    assert product.scraped_at.year == 2026


def test_the_deposit_is_added_to_a_captured_price(tmp_path):
    """A price rail states the deposit separately, so the number written down
    is the shelf price without it — same basis as every online source."""
    assert deposit.included("froo") is False
    path = write(tmp_path, ",froo,,Babanu Vin rosu 2L,Babanu,2,13.99,,,\n")
    product, = captures.read(path)
    with Store(tmp_path / "w.sqlite") as store:
        store.upsert(product)
        row = dict(store.latest()[0])
    assert row["deposit"] == 0.5
    assert pricing.paid(row) == pytest.approx(14.49)


def test_a_row_missing_a_price_is_skipped_not_guessed(tmp_path):
    path = write(tmp_path,
                 ",froo,,Vin fara pret,,0.75,,,,\n"
                 ",froo,,Vin cu pret,,0.75,19.99,,,\n")
    assert [p.name for p in captures.read(path)] == ["Vin cu pret"]


def test_a_price_that_is_not_a_number_is_an_error(tmp_path):
    """Silently dropping it would leave a wine missing with no sign why."""
    path = write(tmp_path, ",froo,,Vin,,0.75,nu stiu,,,\n")
    with pytest.raises(ValueError, match="price is not a number"):
        captures.read(path)


def test_reloading_the_same_file_does_not_duplicate(tmp_path):
    path = write(tmp_path, ",froo,,Babanu Vin rosu 2L,Babanu,2,13.99,,,\n")
    with Store(tmp_path / "w.sqlite") as store:
        for _ in range(3):
            for product in captures.read(path):
                store.upsert(product)
        assert len(store.latest()) == 1
