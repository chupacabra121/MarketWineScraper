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


@pytest.mark.parametrize("title", [
    # Fizzy juice in a wine bottle, shelved with the sparkling wine
    "Spumant pentru copii cu suc de mere si cirese, Kidibul 0.75L",
    "BAMBINO PARTY BAUTURA COPII ZMEURA0.75LS",
    "TOM&JERRY SPUMANT COPII STRUGURI 0.75LSG",
    "FROZEN Spumant pentru Copii SGR 0,75 L",
    "ANGELLI BAMBINO PARTY Piersica SGR 0,75 L",
    # A fruit named as the flavour: aromatised wine-based drinks
    "Zarea Fruits Collection Zmeura 0.75L",
    "Vin spumant alb Zarea Fruit Collection, Capsuni, Demisec, 0.75L",
    "Vin Spumant Zarea cu aroma de afine 0.75L",
    "DORATO Vin Spumant de Piersici Demisec SGR 0,75 L",
    "DORATO Florentino Vin Spumant Demisec Capsuni 7% SGR 0,75 L",
    "Zarea Vin spumant capsuni 750 ml",
    "Angelli Bautura Arom. Baza De Vin Cu Suc Cirese 1L",
    "BFL ANGELLI APERITIV AFINE 14% 1L",
    # Fruit wine is not grape wine
    "Vin Cirese Negre+Rosii 750Ml",
    "Vin Din Mure 750Ml",
    "Vin Din Caise Anticum, 750 Ml",
    # A vodka RTD and a wheat beer, both filed under wine by the retailer
    "ABSOLUT PASSIONFRUIT MARTINI 5% 0.25L",
    "KONIG LUDWIG ALBA 5.5%EP.12.6ST 0.5L SG",
    # "Spritzz" with the doubled z escaped the old word-boundary rule
    "LANDHAUS O-Spritzz Frizzante 6.9% SGR 0,75 L",
])
def test_flavoured_and_mis_shelved_drinks_are_excluded(title):
    """Every string here was a real listing that survived the earlier filter."""
    assert looks_like_wine(title, "Vinuri/Vin spumant") is False


@pytest.mark.parametrize("title", [
    # "Visinescu" is a producer, not a cherry: 30 real wines carry the name.
    "Vin alb sec Aurelia Visinescu Promessa, Chardonnay, 0.75 l",
    "Aurelia Visinescu Anima 3 Fete Negre Vin rosu",
    "Vin alb Povestea Alb Visinie, Domeniile Averesti, demisec, 0.75 l",
    # Martini & Rossi's Asti and Prosecco are wine; only the RTD tin is not.
    "Vin spumant Martini Asti, 0.75 l",
    "MARTINI ASTI Vin Alb Spumant SGR 0,75 L",
    # Pelin is grape wine macerated with wormwood, sold and titled as wine.
    "Vin alb demisec Domeniile Ostrov Pelin, alcool 11%, 0.75 l",
    # "Nectar Impérial" is a cuvée name, not a fruit drink.
    "MOËT & CHANDON Nectar Imperial Demisec Sampanie SGR 0,75 L",
])
def test_lookalike_names_are_not_swept_up(title):
    assert looks_like_wine(title, "Vinuri/Vin alb") is True


@pytest.mark.parametrize("title,expected", [
    # Kaufland glues its deposit marker to the unit, which used to stop the real
    # bottle size matching at all — leaving the internal code to win.
    ("DOM BLAGA MERLOT 8L SEC 14.2% DOC 0.75LS", 0.75),
    ("TECTONIC CAB SYRAH 12L SEC 14.5% 0.75LSG", 0.75),
    ("ANNO SAUV CHARD 4L DOC SEC 12.5% 0.75LSG", 0.75),
    # A genuine bag-in-box is the last volume in its title and stays 3 L.
    ("VARANCHA SAUV BL SEC IG 12.5% 3L BIB", 3.0),
    ("PR PONTICA TAM ROM DMD11.5% IG 1.5L", 1.5),
])
def test_deposit_marker_does_not_hide_the_bottle_size(title, expected):
    assert parse_volume_l(title) == expected


@pytest.mark.parametrize("title", [
    # Fruit wines, found by the review queue rather than by a hand-written rule
    "Vin Aronia 750Ml",
    "Vin de Coacaze 750ml Anticum de Butea",
    # De-alcoholised wine, which the "fara alcool" rule did not phrase-match
    "Maschio Spumant Zero Alcool 0.75L",
    "Zarea Zero alcool Cabernet Sauvignon Rosu 0.75L",
])
def test_fruit_wine_and_zero_alcohol_are_excluded(title):
    assert looks_like_wine(title, "Vinuri/Vin alb") is False


@pytest.mark.parametrize("title", [
    # "Pere Ventura" is a Cava house and "Grand-Pere" a Crama Bratu range, so
    # the fruit rule for "pere" only fires in the "vin de/din pere" form.
    "Vin spumant alb sec Pere Ventura Primer Reserva Brut, cupaj, 0.75 l",
    "Crama Bratu Vin alb sec Feteasca Regala Grand-Pere",
])
def test_producers_named_after_fruit_survive(title):
    assert looks_like_wine(title, "Vinuri/Vin alb") is True


@pytest.mark.parametrize("title", [
    # "Băutură" is how a Romanian label says "this is not wine"
    "Bautura spumoasa aromata alb sec Blue Nun 24K, 0.75 l",
    "Bautura spumoasa aromatizata 24K Gold Edition 0.75L",
    "Băutură nealcoolică din vin dezalcoolizat, alb 750ml",
    "ZAREA ZERO % BAUTURA CARB. DIN VIN DEZALCOOLIZAT 0,75",
    # De-alcoholised, spelled the way Romanian retailers actually spell it
    "Vin dezalcoolizat spumos sec 750ml",
    "Leopard's Leap Natura Red Vin rosu demisec dezalcoolizat",
    "Zarea Vin spumant Free 0.00%",
    # A spirit shelved under red wine, given away only by its strength
    "CARPATHIAN SM FET.NEAGRA 46% 0.7L",
    "SENATOR BITTER 18% 0.5L",
    # "Spr!z" spells its way around a plain word match
    "Mionetto IL Spr!z Vin frizzante",
    # Two bottles, or a bottle plus glassware: the price is not a bottle price
    "Kanga Mateus Rose 0.75L + Mateus Rose 0.187L",
    "ZAREA EMOTIONS+2PAH.DS0,75",
    "ZAREA FINE MOMENTS SPUMANT ALB DEMISEC 0,75+2PAHARE",
    "MIONETTO PROSECCO TREVISO DOC ORANGE PRESTIGE 0,75 +2 PA.",
    "Kit Pentru Sprit Domeniile Samburesti Vin Alb Sauvignon Blanc 0.75L + 2 pahare",
])
def test_drinks_that_are_not_a_bottle_of_wine_are_excluded(title):
    assert looks_like_wine(title, "Vinuri/Vin alb") is False


@pytest.mark.parametrize("title", [
    # Fortified wines run to 20% and must clear the spirit-strength rule
    "Vin roșu dulce Fine Tawny Port, 20%, 750ml",
    "OSBORNE VIN PORTO RUBY 19% 0.75L",
    "OSBORNE CREAM SHERRY 17% 0.75L",
    "FLORIO MARSALA VECCHIO SECCO 18% 0,75(VIN DESERT)",
    # A single bottle of the same wine, without the glasses
    "MIONETTO PROSECCO TREVISO DOC ORANGE PRESTIGE ALB S 1,5",
    # "23K" is gold leaf, not a percentage
    "Zarea Royal Gold Cu Foita De Aur 23K Editie Limitata, Alb 0.75L",
])
def test_strong_wines_and_lookalikes_survive(title):
    assert looks_like_wine(title, "Vinuri/Vin rosu") is True


def test_a_ten_litre_cask_written_without_a_unit():
    """Selgros writes its bag-in-box sizes as a bare number: "10,0"."""
    assert parse_volume_l("VINUL STRAMOSESC ALB BIB DEMIDULCE 10,0") == 10.0
    assert parse_volume_l("CRAMA STARMINA SAUVIGNON BLANC BIB 10,00") == 10.0


def test_an_unlabelled_strength_is_not_read_as_a_cask():
    """Above five litres only a whole number is a size; 13,5 is alcohol."""
    assert parse_volume_l("VIN ROSU SEC 13,5") is None
    assert parse_volume_l("VIN ALB DEMISEC 9,5") is None


def test_a_size_abbreviated_onto_a_word():
    """Selgros compresses titles: "S.0,75" is a 0.75 L bottle, sec."""
    assert parse_volume_l("STIH SAUV. BLANC S.0,75") == 0.75
    assert parse_volume_l("POMMERY SAMPANIE BR.0,75") == 0.75
    # but a decimal cut out of a longer number still must not match
    assert parse_volume_l("SERAFIM 12L SEC 0.750 L") == 0.75
