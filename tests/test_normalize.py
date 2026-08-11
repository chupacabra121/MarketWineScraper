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


def test_blend_descriptors_are_not_grapes():
    """Auchan and METRO put 'Cuvée'/'Cupaj' in the grape field; they are blends."""
    from winescraper.normalize import is_grape
    assert is_grape("Cabernet Sauvignon") is True
    assert is_grape("Cuvée") is False
    assert is_grape("Cupaj") is False
    # Cotnari is a region and a producer, not a variety.
    assert is_grape("Cotnari") is False
    assert is_grape("Grasa de Cotnari") is True


def test_year_in_brand_is_not_a_vintage():
    """'Sarica Niculitel 1958' and Penny's '1958' range are label names."""
    assert parse_vintage("Vin alb demisec Sarica Niculitel 1958, 0.75 l",
                         brand="Sarica Niculitel 1958") is None
    assert parse_vintage("1958 VIN ALB DEMISEC", brand="1958") is None
    # A real vintage alongside a year-free brand still parses.
    assert parse_vintage("Vin rosu sec Domeniul Coroanei 2018", brand="Domeniul Coroanei") == 2018


def test_enrich_drops_blend_descriptors_from_supplied_varieties():
    product = WineProduct(retailer="metro", external_id="1",
                          name="BUDUREASCA CLASIC FUME Blanc 0,75 L",
                          grape_varieties=["Cuvée"])
    enrich(product)
    assert "Cuvée" not in product.grape_varieties


@pytest.mark.parametrize("title", [
    # Wine-based drinks that are not wine
    "Bautura aromatizata pe baza de vin rosu Wine Chocolate, 0.75 l",
    "Bautura carbogazoasa cu aroma de capsuni Robby Bubble, 0.75 l",
    "VINARTE Gluhwein Bautura pe Baza de Vin Aromat 3 L",
    "WINE CHOCOLATE DARK 14% 0.75L",
    # Ready-to-drink cocktails
    "Spumant Cocktail to Go Zarea Hugo, 0.75L",
    "Chandon Garden Spritz 0.75L",
    "Il Spritz Mionetto 0.75L",
    "ZAREA SEX ON THE BEACH 7%ALC750ML COCKT.",
    # Alcohol-free, including children's "champagne"
    "Sampanie copii fara alcool Vitapress Fairies, 0.75 L",
    "Spumant Zarea Free 0.0% 0.75L",
    "Freixenet alb, fara alcool, 0.75L",
    "Bambino Party Vin spumant fara alcool cu aroma de Piersica",
    # Sparkling tea sold in the wine aisle
    "Ceai spumant organic alb sec, 0% alc, 750ml",
    # Vermouth and aperitifs
    "MARTINI BIANCO VERMUT 15% 0.75L",
    "CINZANO ROSSO VERMUT 14.4% 0.75L",
    # Bundles price a pack, not a bottle
    "Pachet vin alb demidulce Murfatlar Zestrea, (3+1) x 0.75 l",
])
def test_wine_adjacent_products_are_excluded(title):
    """Every string here was a real listing collected from a wine category."""
    assert looks_like_wine(title) is False


@pytest.mark.parametrize("title", [
    "Vin rosu sec Feteasca Neagra, 0.75 l",
    "COTNARI Vin Feteasca Alba Demidulce SGR 0,75 L",
    "Prosecco alb sec Mionetto Treviso, 0.75 l",
    "Vin spumant alb brut Freixenet Cava Cordon Negro, 0.75 l",
    # Fortified wines are wine and must survive the filter
    "Vin roșu dulce Porto Ruby, 19.5%, 750ml",
    "Vin alb Sherry Medium Golden, 15%, 750ml",
    "Vin rosu dulce Cantine Florio Vecchioflorio Marsala Superiore",
    # An ordinary ABV must not trip the alcohol-free rule
    "Vin alb sec Crama Girboiu, 12.0% alcool, 0.75 l",
])
def test_real_wine_survives_the_filter(title):
    assert looks_like_wine(title) is True


@pytest.mark.parametrize("title,expected", [
    # A single bottle in a gift box is still one bottle.
    ("DOM PERIGNON Sampanie Gift Box SGR 0,75 L", True),
    ("Vin alb dulce Ice Wine Riesling Gift Box, 7%, 375ml", True),
    ("Louis Roederer Sampanie brut rose vintage gift box", True),
    # A bundle prices several bottles, so per-bottle figures would be wrong.
    ("Pachet vin alb demidulce Murfatlar Zestrea, (3+1) x 0.75 l", False),
    ("Vin spumant 6 x 0,187 L", False),
    ("VIN ALB SEC BAX 6 STICLE", False),
])
def test_gift_boxes_are_kept_but_bundles_are_not(title, expected):
    assert looks_like_wine(title) is expected


@pytest.mark.parametrize("title,expected", [
    # Kaufland titles carry an internal code that reads like a volume. The real
    # bottle size is the last one in the name.
    ("SERAFIM MERLOT 12L SEC 13.5% 0.75L", 0.75),
    ("ECLIPSE MERLOT 19L SEC 14.5% 0.75L", 0.75),
    ("AMBRA SARBA 14L DLC 13.5% 0.375L", 0.375),
    ("LATOUR GR ARDECHE CHARD 10L 0.75L", 0.75),
    # A single volume is unaffected.
    ("COTNARI ET.GALBENA VIN ALB DMD 1.5L", 1.5),
    ("Vin rosu demisec, Budureasca BIB 2L Cabernet sauvignon, 2 l", 2.0),
])
def test_last_volume_wins_over_an_internal_code(title, expected):
    assert parse_volume_l(title) == expected
