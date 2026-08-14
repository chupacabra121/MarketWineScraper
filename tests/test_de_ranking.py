"""The cheapest-per-store ranking, and what it is allowed to leave out.

The sheet answers "what is the cheapest bag-in-box at each shop", which is a
question a wrong filter answers confidently and incorrectly. These tests pin the
three filters that change the answer at a real store, and the tie-break, which
fires constantly: Lidl prices three colours of its own-brand box identically.
"""

from winescraper.de import packaging as pkg
from winescraper.de.model import Listing
from winescraper.de.workbook import _rank_key


def box(name, price, volume=3.0, product_type="still", retailer="lidl",
        pack_count=1):
    return Listing(
        retailer=retailer, retailer_label=retailer.title(), channel="discounter",
        external_id=name, name=name, price=price, volume_l=volume,
        packaging=pkg.BAG_IN_BOX, product_type=product_type,
        pack_count=pack_count,
    )


class TestRankKey:
    def test_cheapest_per_litre_first(self):
        cheap = box("Vino Tinto", 4.99)
        dear = box("Maybach Riesling", 9.99)
        assert sorted([dear, cheap], key=_rank_key)[0] is cheap

    def test_a_bigger_box_can_beat_a_smaller_one_on_litre_price(self):
        # 5 litres at 15.80 is 3.16/l; 3 litres at 11.49 is 3.83/l.
        five = box("Biqueirão Branco", 15.80, volume=5.0)
        three = box("Tres Reyes", 11.49, volume=3.0)
        assert sorted([three, five], key=_rank_key)[0] is five

    def test_ties_break_on_pack_price_then_name(self):
        # Lidl lists three colours of its own brand at exactly 1.66 EUR/l. The
        # order has to be stable or the sheet reshuffles between runs.
        rosado = box("Vino Rosado Tempranillo", 4.99)
        tinto = box("Vino Tinto Tempranillo", 4.99)
        blanco = box("Vino Blanco Airén", 4.99)
        order = [x.name for x in sorted([tinto, rosado, blanco], key=_rank_key)]
        assert order == ["Vino Blanco Airén", "Vino Rosado Tempranillo",
                         "Vino Tinto Tempranillo"]
        # And re-sorting a differently ordered input gives the same answer.
        again = [x.name for x in sorted([blanco, tinto, rosado], key=_rank_key)]
        assert again == order

    def test_a_cheaper_pack_price_wins_a_litre_tie(self):
        small = box("Drei Liter", 4.99, volume=3.0)
        large = box("Fünf Liter", 8.32, volume=5.0)   # both 1.66 EUR/l
        assert small.price_per_litre == large.price_per_litre == 1.66
        assert sorted([large, small], key=_rank_key)[0] is small


class TestWhatIsExcluded:
    def test_gluehwein_would_otherwise_take_first_place(self):
        # METRO's cheapest box of anything is a 10-litre Glühwein at 1.23 EUR/l,
        # against 1.42 for its cheapest actual wine. Ranking them together would
        # report mulled wine as the cheapest wine at the shop.
        mulled = box("Hüttenglut Glühwein BIB", 12.29, volume=10.0,
                     product_type="gluehwein", retailer="metro")
        wine = box("Cerro de La Cruz Rotwein", 14.19, volume=10.0,
                   retailer="metro")
        assert mulled.price_per_litre < wine.price_per_litre
        assert mulled.product_type != "still"
        assert wine.product_type == "still"

    def test_a_multipack_is_not_a_single_box(self):
        # WirWinzer's "4er Paket" prices honestly per litre and cannot be bought
        # one box at a time.
        pack = box("4er Paket Riesling Bag-in-Box", 41.50, volume=3.0,
                   retailer="wirwinzer", pack_count=4)
        assert pack.is_pack
        assert pack.price_per_litre == 3.46

    def test_a_pack_is_recognised_from_its_name_alone(self):
        # NORMA's cheapest box is an "Aktionspaket" with no pack count field.
        bundle = box('Aktionspaket "Weine Südafrikas in der Bag in Box"', 22.0,
                     volume=9.0, retailer="norma")
        assert bundle.pack_count == 1
        assert bundle.is_pack

    def test_an_ordinary_box_is_not_mistaken_for_a_pack(self):
        assert not box("Vino Tinto Tempranillo Spanien 3,0-l-Bag-in-Box", 4.99).is_pack
        assert not box("Stony Cape Chenin Blanc Bag in Box 3 l", 8.99).is_pack

    def test_a_german_vintage_is_not_a_bottle_count(self):
        # "2024er Riesling" is how a German grower writes the year. Read as a
        # pack it would drop a real wine out of the ranking.
        assert not box("2024er Riesling Bag in Box", 11.99).is_pack
        assert box("4er Paket Riesling Bag-in-Box", 41.50).is_pack


class TestBottleEquivalent:
    def test_the_entry_box_is_priced_per_standard_bottle(self):
        # 4.99 EUR for 3 litres is 1.66 EUR/l, and 1.25 EUR per 0.75 l — the
        # comparison that carries the commercial argument for the format.
        entry = box("Vino Tinto Tempranillo", 4.99)
        assert entry.price_per_litre == 1.66
        assert entry.bottle_equivalent_price == 1.25
