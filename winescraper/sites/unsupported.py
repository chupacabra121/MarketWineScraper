"""Retailers with no scrapable online wine catalogue.

These are registered deliberately rather than omitted, so ``list-sites`` reports
why each one yields nothing and adding a real adapter later is a drop-in change.
Findings are from live checks; see README for the date.
"""

from __future__ import annotations

from ..models import WineProduct
from .base import Adapter, register


class _NoCatalogue(Adapter):
    catalogue = "none"
    reason = "no online wine catalogue"

    async def scrape(self) -> list[WineProduct]:
        return []


@register
class ProfiAdapter(_NoCatalogue):
    key = "profi"
    label = "Profi Rom Food (direct)"
    note = "Site rejects automated requests (HTTP 403); use profi_glovo instead."


@register
class LidlAdapter(_NoCatalogue):
    key = "lidl"
    label = "Lidl Romania"
    note = "Online shop carries no wine; absent from Bolt Food and Glovo too."


@register
class LaCocosAdapter(_NoCatalogue):
    key = "lacocos"
    label = "La Cocos"
    note = "Blocked at the edge (HTTP 403); absent from Bolt Food and Glovo (checked 2026-08-10)."


@register
class SupecoAdapter(_NoCatalogue):
    key = "supeco"
    label = "Supeco (direct)"
    note = "Blocked at the edge (HTTP 403); use supeco_glovo instead."


@register
class FrooAdapter(_NoCatalogue):
    key = "froo"
    label = "Froo"
    note = "Marketing site only; absent from Bolt Food and Glovo (checked 2026-08-10)."


@register
class AnnabellaAdapter(_NoCatalogue):
    key = "annabella"
    label = "Annabella"
    note = "Product sitemap lists 18 items, none wine; absent from Bolt Food and Glovo."


@register
class UnicarmAdapter(_NoCatalogue):
    key = "unicarm"
    label = "Unicarm"
    note = "Single-page landing site; absent from Bolt Food and Glovo (checked 2026-08-10)."


@register
class LaDoiPasiAdapter(_NoCatalogue):
    key = "ladoipasi"
    label = "La Doi Pasi"
    note = "Franchise network; leaflet-only site, absent from Bolt Food and Glovo."


@register
class AtacAdapter(_NoCatalogue):
    key = "atac"
    label = "Atac Hiper Discount (Auchan)"
    note = "No public product listing; absent from Bolt Food and Glovo (checked 2026-08-10)."
