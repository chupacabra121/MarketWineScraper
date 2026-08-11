"""Separating the regular price from the discount.

The trap is that ``list_price`` is only published when something is actually
discounted, so it is null on 94.9% of rows. Reading it as "the regular price"
would leave almost the whole dataset empty.
"""

import pytest

from winescraper import pricing


def row(**kw):
    base = {"price": 40.0, "list_price": None, "on_promotion": 0, "volume_l": 0.75}
    base.update(kw)
    return base


def test_with_no_promotion_the_shelf_price_is_the_regular_price():
    """94.9% of listings. The page shows one number and it is the normal one."""
    r = row(price=52.29)
    assert pricing.regular(r) == 52.29
    assert pricing.discounted(r) is None
    assert pricing.paid(r) == 52.29
    assert pricing.discount_share(r) is None


def test_with_a_promotion_the_two_prices_separate():
    r = row(price=27.49, list_price=34.46, on_promotion=1)
    assert pricing.regular(r) == 34.46
    assert pricing.discounted(r) == 27.49
    assert pricing.paid(r) == 27.49
    assert pricing.discount_share(r) == pytest.approx(0.2023, abs=1e-4)


def test_a_discount_with_no_former_price_yields_no_regular_price():
    """Kaufland's leaflet is promotions only and never says what a wine costs
    the rest of the time. Handing it its discount price would pull a promotion
    into the series that is meant to exclude them."""
    r = row(price=19.99, list_price=None, on_promotion=1)
    assert pricing.regular(r) is None
    assert pricing.discounted(r) == 19.99
    assert pricing.discount_share(r) is None


def test_per_litre_makes_bottle_sizes_comparable():
    assert pricing.per_litre(29.49, 1.5) == 19.66
    assert pricing.per_litre(34.46, 0.75) == 45.95


@pytest.mark.parametrize("price,volume", [
    (None, 0.75), (40.0, None), (40.0, 0), (0, 0.75),
])
def test_per_litre_needs_both_numbers(price, volume):
    assert pricing.per_litre(price, volume) is None


def test_a_discount_that_is_not_a_discount_is_not_reported():
    """Some feeds repeat the selling price as the former price."""
    assert pricing.discount_share(row(price=40.0, list_price=40.0,
                                      on_promotion=1)) is None
    assert pricing.discount_share(row(price=40.0, list_price=35.0,
                                      on_promotion=1)) is None


def test_the_regular_price_is_never_a_discounted_one():
    """The whole point of the split: nothing in the regular series is a price
    somebody paid because a promotion was running."""
    rows = [row(price=27.49, list_price=34.46, on_promotion=1),
            row(price=52.29),
            row(price=19.99, on_promotion=1)]
    regulars = [pricing.regular(r) for r in rows]
    assert regulars == [34.46, 52.29, None]
    assert 27.49 not in regulars and 19.99 not in regulars
