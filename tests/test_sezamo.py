"""Sezamo mapping, exercised against real API record shapes.

Sezamo returns a product across three separate endpoints, so the joining logic
and the sale/price precedence are what these tests pin down.
"""

import pytest

from winescraper.sites.sezamo import SezamoAdapter

DETAIL = {
    "id": 35044,
    "name": "Henkell Trocken Mignon Vin spumant alb sec",
    "slug": "henkell-trocken-mignon-vin-spumant-alb-sec",
    "mainCategoryId": 1611,
    "unit": "l",
    "textualAmount": "0,2 l",
    "brand": "Henkell",
    "images": ["https://cdn.sezamo.ro/images/grocery/products/35044/a.jpg"],
}

PRICE_PLAIN = {
    "productId": 35044,
    "price": {"amount": 40.49, "currency": "RON"},
    "pricePerUnit": {"amount": 53.99, "currency": "RON"},
    "sales": [],
}

PRICE_ON_SALE = {
    "productId": 35044,
    "price": {"amount": 40.49, "currency": "RON"},
    "pricePerUnit": {"amount": 53.99, "currency": "RON"},
    "sales": [{
        "id": 51308174, "type": "sale", "active": True,
        "price": {"amount": 36.44, "currency": "RON"},
        "pricePerUnit": {"amount": 48.59, "currency": "RON"},
        "originalPrice": {"amount": 40.49, "currency": "RON"},
        "validTill": "2026-08-31T22:59:00+02:00",
    }],
}

STOCK = {
    "productId": 35044,
    "packageInfo": {"amount": 0.2, "unit": "l"},
    "inStock": True,
}


@pytest.fixture()
def adapter():
    return SezamoAdapter(fetcher=None)


def test_maps_core_fields(adapter):
    p = adapter._to_product(DETAIL, PRICE_PLAIN, STOCK)
    assert p.retailer == "sezamo"
    assert p.external_id == "35044"
    assert p.price == 40.49
    assert p.brand == "Henkell"
    assert p.in_stock is True
    assert p.url == "https://www.sezamo.ro/35044-henkell-trocken-mignon-vin-spumant-alb-sec"


def test_active_sale_replaces_price_and_sets_list_price(adapter):
    p = adapter._to_product(DETAIL, PRICE_ON_SALE, STOCK)
    assert p.price == 36.44
    assert p.list_price == 40.49
    assert p.on_promotion is True
    # The sale's own per-unit figure wins over the standing one.
    assert p.unit_price == 48.59


def test_inactive_sale_is_ignored(adapter):
    price_doc = dict(PRICE_ON_SALE)
    price_doc["sales"] = [dict(PRICE_ON_SALE["sales"][0], active=False)]
    p = adapter._to_product(DETAIL, price_doc, STOCK)
    assert p.price == 40.49
    assert p.on_promotion is False
    assert p.list_price is None


def test_volume_comes_from_package_info_not_the_title(adapter):
    """The title says 'Mignon', not a size; packageInfo is authoritative."""
    p = adapter._to_product(DETAIL, PRICE_PLAIN, STOCK)
    assert p.volume_l == 0.2
    assert p.price_per_litre == 202.45


def test_volume_falls_back_to_textual_amount_without_stock(adapter):
    p = adapter._to_product(DETAIL, PRICE_PLAIN, {})
    assert p.volume_l == 0.2


def test_millilitre_package_is_converted(adapter):
    p = adapter._to_product(DETAIL, PRICE_PLAIN,
                            {"packageInfo": {"amount": 750, "unit": "ml"}, "inStock": True})
    assert p.volume_l == 0.75


def test_subcategory_drives_sparkling_detection(adapter):
    """Category 1611 is 'Vin spumant', so the leaf marks it sparkling."""
    p = adapter._to_product(dict(DETAIL, name="Henkell Trocken Mignon"), PRICE_PLAIN, STOCK)
    assert p.category_path == "Bauturi/Vin/Vin spumant"
    assert p.sparkling is True


def test_unknown_subcategory_falls_back(adapter):
    p = adapter._to_product(dict(DETAIL, mainCategoryId=999999), PRICE_PLAIN, STOCK)
    assert p.category_path == "Bauturi/Vin"


def test_missing_price_record_is_tolerated(adapter):
    p = adapter._to_product(DETAIL, None, STOCK)
    assert p is not None
    assert p.price is None


def test_record_without_id_or_name_is_skipped(adapter):
    assert adapter._to_product({"name": "Vin"}, PRICE_PLAIN, STOCK) is None
    assert adapter._to_product({"id": 1}, PRICE_PLAIN, STOCK) is None
