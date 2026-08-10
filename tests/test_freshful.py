"""Freshful payload mapping, exercised against a real API item shape."""

import json

import pytest

from winescraper.sites.freshful import FreshfulAdapter

# Trimmed from a live /api/v2/shop/categories/705-vinuri response.
ITEM = {
    "code": "100171473",
    "sku": "100171473",
    "variantCode": "100171473",
    "name": "Vin roșu sec Bacanta, Barrique Merlot, 14.5%, 750ml",
    "slug": "100171473-crama-girboiu-vin-rosu-sec-bacanta-barrique-merlot-14-5-750ml",
    "brand": "Crama Girboiu",
    "price": 92.99,
    "originalPrice": None,
    "promotionalPrice": None,
    "geniusPrice": 74.39,
    "currencyCode": "RON",
    "unitPriceLabel": "123,99 Lei/l",
    "isAvailable": True,
    "maxAvailableQuantity": 25,
    "image": {
        "thumbnail": {"default": "https://cdn.freshful.ro/thumb.jpg"},
        "large": {"default": "https://cdn.freshful.ro/large.jpg"},
    },
    "breadcrumbs": [
        {"code": "7", "name": "Băuturi", "slug": "7-bauturi-si-tutun"},
        {"code": "705", "name": "Vinuri", "slug": "705-vinuri"},
        {"code": "70504", "name": "Vinuri roșii", "slug": "70504-vinuri-rosii-romanesti"},
        {"code": "100171473", "name": "Vin roșu sec Bacanta...", "slug": "100171473-..."},
    ],
    "taxes": [{"type": "sgr", "text": "+ 0.5 Lei"}],
}


@pytest.fixture()
def adapter():
    return FreshfulAdapter(fetcher=None)


def test_maps_core_fields(adapter):
    p = adapter._to_product(ITEM)
    assert p.retailer == "freshful"
    assert p.external_id == "100171473"
    assert p.price == 92.99
    assert p.currency == "RON"
    assert p.brand == "Crama Girboiu"
    assert p.in_stock is True
    assert p.url.endswith("/p/100171473-crama-girboiu-vin-rosu-sec-bacanta-barrique-merlot-14-5-750ml")
    assert p.image_url == "https://cdn.freshful.ro/large.jpg"


def test_category_path_excludes_the_product_itself(adapter):
    p = adapter._to_product(ITEM)
    assert p.category_path == "Băuturi/Vinuri/Vinuri roșii"


def test_attributes_parsed_from_title(adapter):
    p = adapter._to_product(ITEM)
    assert p.colour == "rosu"
    assert p.sweetness == "sec"
    assert p.abv == 14.5
    assert p.volume_l == 0.75
    assert p.sparkling is False
    assert "Merlot" in p.grape_varieties


def test_unit_price_read_from_label_not_recomputed(adapter):
    p = adapter._to_product(ITEM)
    assert p.unit_price == 123.99
    assert p.unit_price_unit == "l"


def test_loyalty_price_kept_but_shelf_price_recorded(adapter):
    """Genius is a subscription price; recording it would understate the shelf price."""
    p = adapter._to_product(ITEM)
    assert p.price == 92.99
    assert p.raw["genius_price"] == 74.39
    assert p.on_promotion is False


def test_promotional_price_becomes_the_price(adapter):
    item = dict(ITEM, price=100.0, promotionalPrice=80.0, originalPrice=110.0)
    p = adapter._to_product(item)
    assert p.price == 80.0
    assert p.list_price == 110.0
    assert p.on_promotion is True


def test_original_price_at_or_below_price_is_discarded(adapter):
    item = dict(ITEM, price=92.99, originalPrice=92.99)
    p = adapter._to_product(item)
    assert p.list_price is None
    assert p.on_promotion is False


def test_out_of_stock_when_quantity_is_zero(adapter):
    p = adapter._to_product(dict(ITEM, maxAvailableQuantity=0))
    assert p.in_stock is False


def test_item_without_code_is_skipped(adapter):
    assert adapter._to_product({"name": "Vin rosu"}) is None
    assert adapter._to_product({"code": "1"}) is None


def test_payload_extracted_from_next_data():
    payload = {"total": 927, "pages": 16, "items": [ITEM]}
    html = (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps({"props": {"pageProps": {"dehydratedState": {"queries": [
            {"queryKey": ["config"], "state": {"data": {}}},
            {"queryKey": ["category", "1"], "state": {"data": {"payload": payload}}},
        ]}}}})
        + "</script></body></html>"
    )
    assert FreshfulAdapter._payload_from_html(html)["total"] == 927


def test_missing_next_data_raises():
    with pytest.raises(ValueError):
        FreshfulAdapter._payload_from_html("<html><body>nope</body></html>")
