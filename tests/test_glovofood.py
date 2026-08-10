"""Glovo store-page parsing and tile mapping."""

import pytest

from winescraper.sites.glovofood import (
    _IDS_RE, _SECTION_RE, ProfiGlovoAdapter, SupecoGlovoAdapter,
)

PAGE_SNIPPET = """
...api.glovoapp.com/v4/stores/330531/addresses/524152/content/partial...
href="?content=vin-alb-romania-s.57624334" href="?content=list-item-vin-rose-romania-s.57624352"
"sublist-vin-rosu-romania-s.57624350" "vin-spumant-si-sampanie-s.57785931"
"bere-fara-alcool-s.41133976" "tab-bauturi-alcoolice-sc.41133807"
"vinuri-internationale-s.57785934"
"""

TILE = {
    "id": 4611686018453157175,
    "externalId": "093820-000",
    "storeProductId": "093820-000",
    "name": "Rose De Purcari Vin Sec 0.75L",
    "description": "Rose De Purcari Vin Sec 0.75L. Vin rose sec. 750 ml. Produs in: Moldova. ",
    "price": 43.19,
    "priceInfo": {"amount": 43.19, "currencyCode": "RON", "displayText": "43,19 RON"},
    "imageUrl": "https://glovo.dhmedia.io/image/x.jpg",
    "promotions": [],
    "restricted": True,
}


@pytest.fixture()
def adapter():
    return ProfiGlovoAdapter(fetcher=None)


def test_store_and_address_ids_parse_from_page():
    match = _IDS_RE.search(PAGE_SNIPPET)
    assert match.group(1) == "330531"
    assert match.group(2) == "524152"


def test_section_regex_finds_wine_sections_only():
    found = {sid: slug for slug, sid in _SECTION_RE.findall(PAGE_SNIPPET)}
    slugs = set(found.values())
    assert "vin-alb-romania" in slugs
    assert "vin-spumant-si-sampanie" in slugs
    assert "vinuri-internationale" in slugs
    # Beer must not match; navigation chrome is filtered by prefix later.
    assert not any("bere" in s for s in slugs)


def test_navigation_chrome_prefixes_are_dropped():
    kept = {}
    for slug, sid in _SECTION_RE.findall(PAGE_SNIPPET):
        if slug.startswith(("list-item-", "sublist-", "tab-")):
            continue
        kept[sid] = slug
    assert "57624334" in kept
    # Same section id via its "list-item-" twin must not add noise once the
    # real slug is present; the chrome-only rose section id is dropped.
    assert all(not s.startswith(("list-item-", "sublist-", "tab-")) for s in kept.values())


def test_tile_maps_to_product(adapter):
    p = adapter._to_product(TILE, "Vinuri internaționale")
    assert p.retailer == "profi_glovo"
    assert p.external_id == "093820-000"
    assert p.price == 43.19
    assert p.currency == "RON"
    assert p.volume_l == 0.75
    assert p.colour == "rose"
    assert p.sweetness == "sec"
    assert p.category_path == "Vin/Vinuri internaționale"
    assert p.location == "glovo/profi-buc-bucuresti"
    assert p.raw["source"] == "glovo"


def test_promotions_flag(adapter):
    p = adapter._to_product(dict(TILE, promotions=[{"id": 1}]), None)
    assert p.on_promotion is True


def test_tile_without_id_or_name_is_skipped(adapter):
    assert adapter._to_product({"name": "Vin"}, None) is None
    assert adapter._to_product({"externalId": "x", "name": ""}, None) is None


def test_both_glovo_stores_registered():
    from winescraper.sites import get_adapter

    assert get_adapter("profi_glovo") is ProfiGlovoAdapter
    assert get_adapter("supeco_glovo") is SupecoGlovoAdapter
    assert SupecoGlovoAdapter.city_path == "suceava"
    # Direct stubs stay registered so list-sites still explains them.
    assert get_adapter("profi").catalogue == "none"
    assert get_adapter("supeco").catalogue == "none"
    assert get_adapter("atac").catalogue == "none"
