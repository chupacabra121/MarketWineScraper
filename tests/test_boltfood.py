"""Bolt Food dish mapping, exercised against a real getMenuDishes record."""

import pytest

from winescraper.sites.boltfood import KauflandBoltAdapter

DISH = {
    "id": 6333341701430026,
    "type": "dish",
    "parent_id": 6333341701430025,
    "name": {"locale": "ro-RO", "value": "PURCARI CHARDONNAY SEC 13.5% IG 0.75LSGR"},
    "images": {
        "menu_item_list_v1": {
            "aspect_ratio_map": {"original": {
                "1x": "", "2x": "",
                "3x": "https://images.bolt.eu/store/2025/wine.jpeg",
            }},
        },
    },
    "price": {"value": 39.99, "currency": "ron", "price_str": "39,99 lei"},
    "availability": "in_stock",
    "available_quantity": 401,
    "product_id": "20677327",
    "selling_unit": "piece",
    "fee_info_key": "fl_1",
    "promo_key": None,
}


@pytest.fixture()
def adapter():
    return KauflandBoltAdapter(fetcher=None)


def test_maps_core_fields(adapter):
    p = adapter._to_product(DISH, "Vin/Vin alb")
    assert p.retailer == "kaufland_bolt"
    assert p.external_id == "20677327"
    assert p.price == 39.99
    assert p.currency == "RON"
    assert p.in_stock is True
    assert p.image_url == "https://images.bolt.eu/store/2025/wine.jpeg"
    assert p.location == "bolt-food/kaufland-tei-2600"


def test_glued_sgr_suffix_is_stripped_and_volume_recovered(adapter):
    """Kaufland titles end in '0.75LSGR'; the glued SGR must not eat the volume."""
    p = adapter._to_product(DISH, "Vin/Vin alb")
    assert p.name.endswith("0.75L")
    assert p.volume_l == 0.75
    assert p.abv == 13.5
    assert p.price_per_litre == 53.32


def test_attributes_parsed_from_title(adapter):
    p = adapter._to_product(DISH, "Vin/Vin alb")
    assert p.sweetness == "sec"
    assert "Chardonnay" in p.grape_varieties


def test_leaf_category_marks_sparkling(adapter):
    dish = dict(DISH, name={"value": "ANGELLI CUVEE DULCE 0.75LSGR"})
    p = adapter._to_product(dish, "Vin/Vin spumant")
    assert p.sparkling is True


def test_out_of_stock(adapter):
    p = adapter._to_product(dict(DISH, availability="out_of_stock"), "Vin")
    assert p.in_stock is False


def test_provenance_is_recorded(adapter):
    """Third-party pricing must be traceable: source and store in every row."""
    p = adapter._to_product(DISH, "Vin")
    assert p.raw["source"] == "bolt-food"
    assert p.raw["available_quantity"] == 401
    assert "kaufland-tei-2600" in p.url


def test_dish_without_name_or_id_is_skipped(adapter):
    assert adapter._to_product({"product_id": "1"}, "Vin") is None
    assert adapter._to_product({"name": {"value": "Vin"}, "id": None,
                                "product_id": None}, "Vin") is None


def test_wine_root_keeps_every_leaf():
    """Under a wine-named root (Kaufland's 🍷 Vin), all leaves belong."""
    keep = KauflandBoltAdapter._keep_leaf
    assert keep(True, "Vin alb") is True
    assert keep(True, None) is True


def test_drinks_root_filters_to_wine_leaves():
    """Penny buries wine inside Băuturi; only wine-named leaves survive."""
    keep = KauflandBoltAdapter._keep_leaf
    assert keep(False, "Vin") is True
    assert keep(False, "Șampanie, prosecco") is True
    assert keep(False, "Bere blondă și brună") is False
    assert keep(False, "Spirtoase") is False
    assert keep(False, "Cidru") is False
    assert keep(False, None) is False


def test_penny_bolt_is_registered_with_its_own_identity():
    from winescraper.sites import get_adapter
    from winescraper.sites.boltfood import PennyBoltAdapter

    cls = get_adapter("penny_bolt")
    assert cls is PennyBoltAdapter
    assert cls.provider_id == 138503
    assert cls.location == "bolt-food/penny-nasaud-4343"
    # Must never collide with the direct penny.ro adapter.
    assert get_adapter("penny") is not cls
