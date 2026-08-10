"""Tests for Romanian product-text parsing.

Cases are taken from real listings observed on the target sites.
"""

import pytest

from winescraper.normalize import (
    clean_name, enrich, fold, is_sparkling, looks_like_wine, parse_abv,
    parse_colour, parse_grapes, parse_price, parse_sweetness, parse_unit_price,
    parse_volume_l, parse_vintage,
)
from winescraper.models import WineProduct


@pytest.mark.parametrize("raw,expected", [
    ("15,49 Lei", 15.49),
    ("1.234,50", 1234.50),
    ("39.90", 39.90),
    ("34,55", 34.55),
    (12.29, 12.29),
    ("12,99\xa0LEI", 12.99),
    ("", None),
    (None, None),
    ("gratuit", None),
    (0, None),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("title,expected", [
    ("Vin rosu demisec Feteasca Neagra & Merlot 750ml", 0.75),
    ("Vin alb demidulce Suvorov Letto Muscat, 1 l", 1.0),
    ("COTNARI ET.GALBENA VIN ALB DMD 1.5L", 1.5),
    # Cash & carry titles quote litres with no unit at all.
    ("CAII DE LA LETEA ALIGOTE ALB SEC 0,75", 0.75),
    ("Vin spumant 20 cl", 0.20),
    # A stray ABV must not be mistaken for a bottle size.
    ("Vin rosu sec 13,5% vol", None),
    ("Pahare vin", None),
])
def test_parse_volume(title, expected):
    assert parse_volume_l(title) == expected


@pytest.mark.parametrize("title,expected", [
    ("Vin alb sec 11,5% vol", 11.5),
    ("Vin rosu 13.5%", 13.5),
    ("Vin fara alcool 0,5%", 0.5),
    ("Whisky 40% vol", None),          # above the wine ceiling
    ("Vin rosu sec", None),
])
def test_parse_abv(title, expected):
    assert parse_abv(title) == expected


@pytest.mark.parametrize("title,expected", [
    ("Vin rosu demisec Feteasca Neagra", "rosu"),
    ("Vin alb sec Sauvignon Blanc", "alb"),
    ("BUSUIOACA VIN ROSE DEMIDULCE", "rose"),
    ("Vin roze demisec", "rose"),
    ("Vin Feudi Salentini 125", None),
])
def test_parse_colour(title, expected):
    assert parse_colour(title) == expected


@pytest.mark.parametrize("title,expected", [
    ("Vin alb demidulce", "demidulce"),
    ("Vin alb demisec", "demisec"),
    ("Vin alb dulce", "dulce"),
    ("Vin alb sec", "sec"),
    ("BUDUREASCA VIN ROSE DMS", "demisec"),
    ("COTNARI VIN ALB DMD", "demidulce"),
    ("Spumant brut", "sec"),
    # "DS" is ambiguous across retailers and must stay unparsed.
    ("COTNARI EUFORIA ALB DS", None),
])
def test_parse_sweetness(title, expected):
    assert parse_sweetness(title) == expected


def test_sweetness_prefers_longest_match():
    assert parse_sweetness("Vin demidulce") == "demidulce"
    assert parse_sweetness("Vin demisec") == "demisec"


@pytest.mark.parametrize("title,expected", [
    ("Vin spumant alb brut Freixenet Cava", True),
    ("Prosecco Treviso", True),
    ("Vin rosu sec Feteasca Neagra", False),
])
def test_is_sparkling(title, expected):
    assert is_sparkling(title) is expected


def test_parse_grapes_longest_match_wins():
    grapes = parse_grapes("Vin rosu Cabernet Sauvignon si Merlot")
    assert "Cabernet Sauvignon" in grapes
    # The bare "Sauvignon" inside "Cabernet Sauvignon" must not double count.
    assert "Sauvignon" not in grapes
    assert "Merlot" in grapes


def test_parse_grapes_handles_diacritics():
    assert "Feteasca Neagra" in parse_grapes("Vin rosu Fetească Neagră")


@pytest.mark.parametrize("title,category,expected", [
    ("Vin rosu demisec Feteasca Neagra", None, True),
    ("CAII DE LA LETEA ALIGOTE ALB SEC 0,75", "Vinuri si Spumante/Vin Alb", True),
    # "vintage" starts with "vin" but is not wine.
    ("Pepsi Baut racorit carbo vintage 6*0,33 l", "Oferte/Bauturi", False),
    ("Vinete la gratar", "Legume", False),
    ("Otet din vin alb", None, False),
    ("Pahare pentru vin rosu", None, False),
    ("Tirbuson metalic", None, False),
])
def test_looks_like_wine(title, category, expected):
    assert looks_like_wine(title, category) is expected


def test_parse_unit_price():
    assert parse_unit_price("20.65 Lei/L") == (20.65, "l")
    assert parse_unit_price("1 L 17,72 LEI") == (None, None)
    assert parse_unit_price("") == (None, None)


def test_fold_normalises_both_comma_and_cedilla_forms():
    assert fold("Fetească Neagră") == "feteasca neagra"
    # ș U+0219 and ş U+015F must fold the same way.
    assert fold("Vinuri și Spumante") == fold("Vinuri şi Spumante")


def test_clean_name_strips_deposit_marker():
    assert clean_name("Vin alb sec 0.75L SGR") == "Vin alb sec 0.75L"
    assert clean_name("  Vin   rosu  ") == "Vin rosu"


def test_parse_vintage_rejects_implausible_years():
    assert parse_vintage("Vin rosu 2018") == 2018
    assert parse_vintage("Vin rosu 1234") is None
    assert parse_vintage("Cod 999999") is None


def test_enrich_fills_missing_fields_and_computes_unit_price():
    product = WineProduct(retailer="x", external_id="1",
                          name="Vin rosu demisec Feteasca Neagra 750ml", price=15.0)
    enrich(product)
    assert product.volume_l == 0.75
    assert product.colour == "rosu"
    assert product.sweetness == "demisec"
    assert product.grape_varieties == ["Feteasca Neagra"]
    assert product.unit_price == 20.0
    assert product.price_per_litre == 20.0


def test_enrich_uses_leaf_category_not_parent_aisle():
    """A still wine under a "Vinuri si Spumante" aisle is not sparkling."""
    product = WineProduct(retailer="selgros", external_id="1",
                          name="CAII DE LA LETEA ALIGOTE ALB SEC 0,75",
                          category_path="Vinuri si Spumante/Vin Alb Romanesc")
    enrich(product)
    assert product.sparkling is False
    assert product.colour == "alb"


def test_enrich_reads_sparkling_from_leaf_category():
    product = WineProduct(retailer="auchan", external_id="1",
                          name="Zonin Cuvee 1821",
                          category_path="Bauturi si Tutun/Vin si Sampanie/Vin spumant")
    enrich(product)
    assert product.sparkling is True
