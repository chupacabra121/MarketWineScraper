"""Adapter-level filtering and the partial-run guard.

Every adapter logs-and-skips a failed page so one bad response cannot lose a
whole run. That is the right behaviour for a page, and the wrong behaviour for a
run: Mega Image once returned 146 of 218 wines with nothing in the output saying
so. The guard turns that into a visible failure.
"""

import pytest

from winescraper.sites.base import Adapter


class _Stub(Adapter):
    key = "stub"
    label = "Stub"


def _products(count: int, name: str = "Vin rosu sec 0.75L") -> list:
    adapter = _Stub(fetcher=None)
    return [adapter.make_product(external_id=str(i), name=name, price=30.0)
            for i in range(count)]


def test_partial_run_is_refused():
    adapter = _Stub(fetcher=None)
    adapter.expected_total = 218
    with pytest.raises(RuntimeError, match="146 of 218"):
        adapter.keep_wines(_products(146))


def test_a_run_within_tolerance_passes():
    """Retailers overstate their own totals slightly — an out-of-stock line, a
    duplicate id — so the guard allows a 10% shortfall."""
    adapter = _Stub(fetcher=None)
    adapter.expected_total = 218
    assert len(adapter.keep_wines(_products(210))) == 210


def test_the_guard_is_off_when_a_limit_is_set():
    adapter = _Stub(fetcher=None, limit=5)
    adapter.expected_total = 218
    assert len(adapter.keep_wines(_products(10))) == 5


def test_unpriced_listings_are_dropped():
    adapter = _Stub(fetcher=None)
    sold_out = adapter.make_product(external_id="x", name="Vin alb sec 0.75L", price=None)
    priced = adapter.make_product(external_id="y", name="Vin alb sec 0.75L", price=25.0)
    assert [p.external_id for p in adapter.keep_wines([sold_out, priced])] == ["y"]


def test_non_wine_listings_are_dropped():
    adapter = _Stub(fetcher=None)
    kept = adapter.keep_wines([
        adapter.make_product(external_id="1", name="Otet din vin alb 1L", price=6.0),
        adapter.make_product(external_id="2", name="Vin alb sec Feteasca 0.75L", price=29.0),
    ])
    assert [p.external_id for p in kept] == ["2"]
