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
    label = "Profi Rom Food"
    note = "No e-commerce catalogue; site rejects automated requests (HTTP 403)."


@register
class LidlAdapter(_NoCatalogue):
    key = "lidl"
    label = "Lidl Romania"
    note = "Online shop carries no wine; alcohol is in-store and leaflet only."


@register
class LaCocosAdapter(_NoCatalogue):
    key = "lacocos"
    label = "La Cocos"
    note = "Blocked at the edge (HTTP 403) including from a real browser."


@register
class SupecoAdapter(_NoCatalogue):
    key = "supeco"
    label = "Supeco"
    note = "Blocked at the edge (HTTP 403); no public product listing found."


@register
class FrooAdapter(_NoCatalogue):
    key = "froo"
    label = "Froo"
    note = "Marketing site only (WordPress); sitemap contains no products."


@register
class AnnabellaAdapter(_NoCatalogue):
    key = "annabella"
    label = "Annabella"
    note = "Product sitemap lists 18 items, none of them wine."


@register
class UnicarmAdapter(_NoCatalogue):
    key = "unicarm"
    label = "Unicarm"
    note = "Single-page landing site; no product listing at all."


@register
class LaDoiPasiAdapter(_NoCatalogue):
    key = "ladoipasi"
    label = "La Doi Pasi"
    note = "Franchise network; official site publishes a leaflet, not a catalogue."


@register
class AttackAdapter(_NoCatalogue):
    key = "attack"
    label = "Attack Discount"
    note = "No public product listing found."
