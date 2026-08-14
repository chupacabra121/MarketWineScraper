"""German listing parsing, against titles actually collected.

Every string is a real listing from the August 2026 run. The volume tests matter
most: price per litre is computed from the parsed size, so a misread size is a
wrong price point rather than a missing field.
"""

import pytest

from winescraper.de import parse as P


class TestVolume:
    @pytest.mark.parametrize("title,expected", [
        ("CIMAROSA Chardonnay Chile 3-l-Bag-in-Box trocken, Weißwein 2024", 3.0),
        ("Vino Tinto Tempranillo Spanien 3,0-l-Bag-in-Box trocken, Rotwein 2025", 3.0),
        ("Sauvignon Blanc feinherb 3,0 l Bag in Box - Maybach", 3.0),
        ("Andes Cabernet Sauvignon, trocken, 2024, Bag-in-Box, 3,0l", 3.0),
        ("Edizione Ennio Primitivo Bag-in-Box - 5,0 L", 5.0),
        ("Wolfsglut Glühwein rot \"Bag in Box\" 10,0 L", 10.0),
        ("2025 Silvaner Bag in Box 1,5 L", 1.5),
        ("2024 Bacat Weiß GRÜNE WEINBOX BIO 2,25 L", 2.25),
        ("Valmarone Bianco Frizzante Perlwein - 750 ml Flasche", 0.75),
        ("Roséwein lieblich, 1,5-l-Packung, Roséwein", 1.5),
        ("Airén Spanien halbtrocken, Literflasche, Weißwein", None),
    ])
    def test_sizes_as_retailers_write_them(self, title, expected):
        assert P.parse_volume_l(title) == expected

    def test_a_multipack_gives_the_size_of_one_container(self):
        # Not 4.5 litres. Six bottles of 0.75, and the pack count says six.
        assert P.parse_volume_l("6 x 0,75-l-Flasche Château Dauzac Margaux") == 0.75
        assert P.parse_pack_count("6 x 0,75-l-Flasche Château Dauzac Margaux") == 6

    def test_a_single_container_counts_as_one(self):
        assert P.parse_pack_count("CIMAROSA Shiraz 3-l-Bag-in-Box trocken") == 1

    def test_an_alcohol_percentage_is_not_a_size(self):
        assert P.parse_volume_l("Sol & Mar Sangria 7,0% Vol") is None


class TestColour:
    @pytest.mark.parametrize("title,expected", [
        ("MAYBACH Riesling QbA 3-l-Bag-in-Box trocken, Weißwein 2025", "weiss"),
        ("Grand Sud Merlot 3-l-Bag-in-Box trocken, Rotwein 2025", "rot"),
        ("Vino Rosado Tempranillo 3-l-Bag-in-Box trocken, Roséwein 2025", "rose"),
        ("Vino Blanco Airén 3-l-Bag-in-Box halbtrocken", "weiss"),
        ("2025 Grauburgunder, Bag-in-Box, 3 L, Kaiserstuhl", "weiss"),
        ("2025 Spätburgunder, Bag-in-Box, 3 L", "rot"),
    ])
    def test_colour_from_word_or_grape(self, title, expected):
        assert P.parse_colour(title) == expected

    def test_a_rose_made_from_a_red_grape_is_still_rose(self):
        # "Pinot Noir Rosé" names a red grape; the wine is pink.
        assert P.parse_colour("BREE Pinot Noir Rosé 3-l-Bag-in-Box feinherb") == "rose"
        assert P.parse_colour("CIMAROSA Shiraz 3-l-Bag-in-Box trocken, Roséwein") == "rose"


class TestSweetness:
    @pytest.mark.parametrize("title,expected", [
        ("MAYBACH Riesling QbA 3-l-Bag-in-Box trocken", "trocken"),
        ("Vino Blanco Airén 3-l-Bag-in-Box halbtrocken", "halbtrocken"),
        ("BREE Riesling 3-l-Bag-in-Box feinherb", "halbtrocken"),
        ("MERTES Liebfraumilch 3-l-Bag-in-Box lieblich", "lieblich"),
        ("CHÂTEAU D`YQUEM Sauternes AOC süß", "suess"),
    ])
    def test_the_four_german_steps(self, title, expected):
        # feinherb is legally halbtrocken and is printed instead of it.
        assert P.parse_sweetness(title) == expected

    def test_halbtrocken_is_not_read_as_trocken(self):
        # "trocken" is a substring of "halbtrocken"; order decides.
        assert P.parse_sweetness("Weißwein halbtrocken") == "halbtrocken"


class TestProductType:
    @pytest.mark.parametrize("title,expected", [
        ("MAYBACH Riesling QbA 3-l-Bag-in-Box trocken", "still"),
        ("Wolfsglut Glühwein rot Bag in Box 10,0 L", "gluehwein"),
        ("Sol & Mar Sangria 3-l-Bag-in-Box 7,0% Vol", "sangria"),
        ("ALLINI Prosecco DOC Vino Spumante extra trocken Magnum", "sparkling"),
        ("CHÂTEAU D`YQUEM Sauternes AOC süß 0,375-l, Süßwein", "dessert"),
    ])
    def test_drinks_priced_on_another_scale_are_marked(self, title, expected):
        # Glühwein in the same 10-litre box runs at a third of the litre price.
        assert P.parse_product_type(title) == expected


class TestIsWine:
    @pytest.mark.parametrize("title", [
        "MAYBACH Riesling QbA 3-l-Bag-in-Box trocken, Weißwein 2025",
        "2025 Grauburgunder, Bag-in-Box, 3 L, Region Kaiserstuhl, Baden",
        "2024 MRKGRFLR Gutedel Bag in Box 3,0 L",
        "Vino Tinto Tempranillo Spanien 3,0-l-Bag-in-Box trocken",
    ])
    def test_wine_survives_including_grape_only_titles(self, title):
        # German growers title by variety and never write "Wein".
        assert P.looks_like_wine(title)

    @pytest.mark.parametrize("title", [
        "2024 Traubensaft weiß - BAG in BOX 3,0 L",
        "Kennenlern-Paket Bag-in-Box (BiB) + 6 Gläser",
        "W5 Boxen 5 l mit Deckel, 6er Set",
        "BEN BRACKEN Highland Single Malt Scotch Whisky",
        "6 x 0,75-l-Flasche Weinpaket Mouton Cadet",
        "Spumante Zero Alkoholfrei",
    ])
    def test_the_wine_aisle_contains_things_that_are_not_wine(self, title):
        assert not P.looks_like_wine(title)


class TestPrice:
    @pytest.mark.parametrize("text,expected", [
        ("10,98 €", 10.98), ("4,99 €*", 4.99), ("1.234,56 €", 1234.56),
        ("41,50\xa0€", 41.50), (9.99, 9.99),
    ])
    def test_german_number_format(self, text, expected):
        assert P.parse_price(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("4.2", 4.20), ("6.8", 6.80), ("40", 40.0), ("2.49", 2.49),
    ])
    def test_bare_decimals_from_microdata(self, text, expected):
        # NORMA publishes itemprop="price" content="4.2". Requiring two decimal
        # places dropped the tenths and read that as 4 — a 20-cent error on
        # every one-decimal price in the shop, and invisible in the output.
        assert P.parse_price(text) == expected


class TestOrigin:
    def test_country_from_name_or_region(self):
        assert P.parse_country("Vino Tinto Tempranillo Spanien lieblich") == "Spanien"
        assert P.parse_country("MAYBACH Riesling QbA Pfalz") == "Deutschland"
        assert P.parse_country("Primitivo Puglia IGT trocken") == "Italien"

    def test_grapes_do_not_swallow_each_other(self):
        # "Sauvignon Blanc" must not also register Cabernet Sauvignon's Sauvignon.
        assert P.parse_grapes("CIMAROSA Sauvignon Blanc Marlborough") == ["Sauvignon Blanc"]
