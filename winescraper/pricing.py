"""Splitting a listing's price into the regular price and the discount.

The database records what the retailer publishes: ``price`` is what a shopper
pays on the day, and ``list_price`` is the pre-discount figure — which sites
only print when something is actually discounted. For 94.9% of listings there is
no promotion running, so the price on the page *is* the regular price.

Analysis of regular prices therefore cannot just read ``list_price``: it is null
on nearly every row. It has to be reconstructed:

======================  ==========================  ========================
                        on promotion                not on promotion
======================  ==========================  ========================
``regular``             ``list_price``              ``price``
``discounted``          ``price``                   — (nothing to show)
``paid``                ``price``                   ``price``
======================  ==========================  ========================

The one case with no honest answer is a listing the retailer flags as
discounted while publishing no former price — 16 rows, including Kaufland's
leaflet, which is promotions only and never states what the wine costs the rest
of the time. Those get no regular price rather than being handed their discount
price, which would quietly pull a promotion into a series that is meant to
exclude them.
"""

from __future__ import annotations


def regular(row: dict) -> float | None:
    """The undiscounted price: what the wine costs when nothing is running."""
    if row.get("on_promotion"):
        # None when the retailer discounts without saying what from.
        return row.get("list_price")
    return row.get("price")


def discounted(row: dict) -> float | None:
    """What a shopper pays today, but only where that is a reduced price."""
    return row.get("price") if row.get("on_promotion") else None


def paid(row: dict) -> float | None:
    """What a shopper pays today, discount or not."""
    return row.get("price")


def discount_share(row: dict) -> float | None:
    """How far below the regular price the current one sits, as a fraction."""
    before, now = regular(row), discounted(row)
    if not before or not now or before <= 0 or now >= before:
        return None
    return (before - now) / before


def per_litre(price: float | None, volume_l: float | None) -> float | None:
    """Price for one litre, which is what makes bottle sizes comparable."""
    if not price or not volume_l or volume_l <= 0:
        return None
    return round(price / volume_l, 2)
