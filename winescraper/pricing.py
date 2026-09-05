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

Every figure here is what a shopper hands over, so it carries the SGR deposit
where the shop has not already added it — see :mod:`winescraper.deposit`. On a
2 litre wine at 12 lei the deposit is 4% of the price, which is larger than most
of the differences these numbers get used to argue about. ``published_regular``
gives the price without it, for reconciling against a retailer's own page.
"""

from __future__ import annotations

from . import deposit as sgr


def deposit_on(row: dict) -> float:
    """The SGR owed on top of the published price, in lei.

    Stored on the observation by the scrape. Falling back to the rule keeps rows
    written before the column existed usable; an unknown basis reads as nothing
    owed here, and is reported as unknown by ``check`` rather than by silently
    moving a price.
    """
    stated = row.get("deposit")
    if stated is not None:
        return float(stated)
    owed = sgr.payable(row.get("retailer") or "", row.get("volume_l"),
                       row.get("name") or "")
    return owed or 0.0


def regular(row: dict) -> float | None:
    """The undiscounted price, deposit included: the till price with no promotion."""
    if row.get("on_promotion"):
        # None when the retailer discounts without saying what from.
        before = row.get("list_price")
        return before + deposit_on(row) if before is not None else None
    return paid(row)


def discounted(row: dict) -> float | None:
    """What a shopper pays today, but only where that is a reduced price."""
    return paid(row) if row.get("on_promotion") else None


def paid(row: dict) -> float | None:
    """What a shopper pays today, discount or not, deposit included."""
    price = row.get("price")
    return price + deposit_on(row) if price is not None else None


def published_regular(row: dict) -> float | None:
    """The regular price as the retailer prints it, before the deposit.

    What to reconcile against a shop's own page or a shelf audit; ``regular`` is
    what to put in front of a shopper.
    """
    return row.get("list_price") if row.get("on_promotion") else row.get("price")


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
