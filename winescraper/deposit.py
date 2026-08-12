"""The SGR deposit, and which retailers have already added it to their price.

Romania's deposit-return scheme (Sistemul Garanție-Returnare) charges a flat
0.50 lei on each single-use beverage container of 0.1 to 3 litres made of glass,
plastic or metal. It is refunded when the container is returned, but a shopper
pays it at the till, so a price that leaves it out is not what the wine costs.

Two separate questions decide what to add to a listing:

1. **Does the container carry a deposit?** A packaging question. Bottles and PET
   do; bag-in-box does not, being composite packaging outside the scheme, and
   neither do the 5 and 10 litre casks. The rule below is not quoted from the
   legislation — it is read off METRO, the one source that publishes a deposit
   for every article, and :mod:`tests.test_deposit` checks it still reproduces
   all 990 of those figures.

2. **Has the retailer already added it?** A pricing question, and the answer
   differs by shop. It cannot be inferred from a price, so each source is
   recorded below with the evidence for it, and a source whose basis is not
   established says so rather than being assumed either way.
"""

from __future__ import annotations

import re

#: Lei per container, set by law and the same for every material and size.
AMOUNT = 0.50

#: The scheme covers 0.1 to 3 litres inclusive.
MIN_VOLUME_L = 0.1
MAX_VOLUME_L = 3.0

#: Composite packaging — a cardboard box holding a plastic bladder — is not a
#: returnable container, so a bag-in-box carries no deposit whatever it holds.
_BAG_IN_BOX = re.compile(r"\bbag[\s-]*in[\s-]*box\b|\bbib\b|\bcubi\b|\bpouch\b", re.I)

#: Some retailers stamp the deposit into the product name: METRO writes "SGR"
#: and Kaufland suffixes the size, "0,75LSGR" or "0.75LSG".
_MARKED = re.compile(r"\bsgr\b|\d\s*l\s*sgr?\b", re.I)

#: At three litres the bag-in-box is the rule and the bottle the exception —
#: 119 of the 122 three-litre wines in the data are boxes, and the three that
#: are not say so themselves. Below three litres the reverse holds, so the
#: default flips here rather than applying uniformly across the range.
_BOX_SIZE_L = 3.0


def applies(volume_l: float | None, name: str = "") -> bool | None:
    """Whether SGR is charged on this container, or ``None`` if undecidable."""
    name = name or ""
    if _MARKED.search(name):
        return True
    if volume_l is None:
        # A wine with no stated size is a bottle far more often than not, so
        # calling this exempt would quietly shave 0.50 off it. It is not known.
        return None
    if not MIN_VOLUME_L <= volume_l <= MAX_VOLUME_L:
        return False
    if _BAG_IN_BOX.search(name):
        return False
    return volume_l < _BOX_SIZE_L


def amount(volume_l: float | None, name: str = "",
           published: float | None = None) -> float | None:
    """The deposit on one container, or ``None`` where the container is unclear.

    ``published`` is the retailer's own figure where it prints one, and it wins:
    the shop knows its packaging, and reading the container off a product title
    is a fallback for the twelve sources that say nothing.
    """
    if published is not None:
        return float(published)
    charged = applies(volume_l, name)
    if charged is None:
        return None
    return AMOUNT if charged else 0.0


# Whether the price a source publishes already contains the deposit.
# False = the deposit must be added to get what a shopper pays.
# None  = not established; the reports will not guess in either direction.
INCLUDED_IN_PRICE: dict[str, bool | None] = {
    # Publishes ``price_net`` alongside the gross price. Every one of the 990
    # articles satisfies gross == round(net * 1.21, 2) exactly, so the gross is
    # net plus VAT and nothing else; the deposit rides in its own field.
    "metro": False,
    # States the deposit on the product as the string "+ 0.5 Lei".
    "freshful": False,
    # The rest are settled against the SP-IKA shelf audit of August 2026, which
    # priced these chains in 11 stores. 111 comparable lines match our figures
    # to the cent and 2 sit 0.50 above, which is the wrong shape for a deposit
    # we had added and the audit had not.
    "carrefour": False,
    "auchan": False,
    "selgros": False,
    "kaufland": False,
    "kaufland_bolt": False,
    "mega_image": False,
    "penny": False,
    "penny_bolt": False,
    "profi_glovo": False,
    # Neither appears in the audit and neither publishes a deposit field.
    # Glovo's *Penny* store was measured at 0.50 above Bolt's in an earlier
    # survey, which is why Supeco is suspected of including it — but suspected
    # is not measured, and Sezamo has nothing pointing either way.
    "sezamo": None,
    "supeco_glovo": None,
}


def included(retailer: str) -> bool | None:
    """Whether this source's published price already carries the deposit."""
    return INCLUDED_IN_PRICE.get(retailer)


def payable(retailer: str, volume_l: float | None, name: str = "",
            published: float | None = None) -> float | None:
    """What must be added to this source's price to reach the till price.

    ``0.0`` when the container is exempt or the price already includes the
    deposit, and ``None`` when the source's basis is unknown — which is not the
    same as zero and must not be silently treated as such.
    """
    basis = included(retailer)
    if basis:
        return 0.0
    owed = amount(volume_l, name, published)
    if owed is None or (basis is None and owed):
        return None
    return owed


UNSETTLED = sorted(k for k, v in INCLUDED_IN_PRICE.items() if v is None)
