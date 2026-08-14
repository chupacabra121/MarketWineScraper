"""Container classification and Pfand, against listings actually collected.

Every string here was taken from a live German listing during the August 2026
run. The rule this file protects is the study's whole filter: a wine is included
only if it is in a PET bottle or a bag-in-box, so a classifier that drifts either
way changes the answer rather than just the data.
"""

from winescraper.de import packaging as pkg


class TestBagInBox:
    def test_lidl_writes_it_into_the_title(self):
        assert pkg.classify(
            "CIMAROSA Chardonnay Chile 3-l-Bag-in-Box trocken, Weißwein 2024",
            volume_l=3.0) == pkg.BAG_IN_BOX

    def test_the_spelling_varies_by_retailer(self):
        for name in (
            "Sauvignon Blanc feinherb 3,0 l Bag in Box - Maybach",
            "Andes Cabernet Sauvignon, trocken, 2024, Bag-in-Box, 3,0l",
            "Herxheim am Berg 4er Paket Riesling Bag-in-Box",
            "Weinschlauch Rotwein trocken 5 Liter",
            "Grauburgunder Weinbox 3 Liter trocken",
        ):
            assert pkg.classify(name) == pkg.BAG_IN_BOX, name

    def test_three_litres_and_up_is_a_box_even_when_unsaid(self):
        # Measured, not assumed: of 216 three-litre wines collected, 191 say
        # bag-in-box, 24 say nothing, and one is a bottle that says so.
        assert pkg.classify("Rotwein trocken 5 Liter", volume_l=5.0) == pkg.BAG_IN_BOX
        assert pkg.classify("Maybach Grauer Burgunder", volume_l=3.0) == pkg.BAG_IN_BOX
        assert pkg.classify("Berg in Box, Rosé feinherb, 3 L", volume_l=3.0) == pkg.BAG_IN_BOX

    def test_a_stated_bottle_beats_the_size_rule(self):
        # The one three-litre exception in the data: a Prosecco Jeroboam.
        assert pkg.classify(
            "Valdo Prosecco Valdobbiadene Superiore D.O.C.G. Marca Oro 3 l Flasche",
            volume_l=3.0) == pkg.GLASS

    def test_two_litres_is_not_assumed_to_be_a_box(self):
        # Two-litre wine in Germany is routinely glass — the Greek Imiglykos
        # lines at Globus — so the rule stops at three.
        assert pkg.classify("Black Label Imiglykos, Rotwein", volume_l=2.0) == pkg.UNKNOWN

    def test_a_six_bottle_case_is_not_a_box(self):
        # Lidl reports this case as 4.5 litres, which the size rule would read
        # as a box. The pack wording and the word Flasche both have to stop it.
        assert pkg.classify(
            "6 x 0,75-l-Flasche Château Dauzac Margaux 5er Grand Cru Classé AOC",
            volume_l=4.5) == pkg.GLASS


class TestPet:
    def test_named_outright(self):
        assert pkg.classify("Wein Rosé trocken 1 l PET-Flasche") == pkg.PET
        assert pkg.classify("Weißwein lieblich Kunststoffflasche 0,75 l") == pkg.PET

    def test_bag_in_box_wins_when_both_words_appear(self):
        # A box listing may mention the PET tap; a PET bottle never mentions a box.
        assert pkg.classify(
            "Rotwein 3 l Bag-in-Box mit PET-Zapfhahn") == pkg.BAG_IN_BOX


class TestOtherContainers:
    def test_lidl_carton_is_a_carton_not_a_box(self):
        # Title says "Packung"; only the image alt text says Karton. Both are
        # passed to the classifier, and either alone is enough.
        assert pkg.classify("Roséwein lieblich, 1,5-l-Packung, Roséwein",
                            volume_l=1.5) == pkg.CARTON
        assert pkg.classify("Roséwein lieblich 1,5 l",
                            description="Eine Karton Rosewein mit einem Weinglas.",
                            volume_l=1.5) == pkg.CARTON

    def test_the_german_litre_bottle_is_glass(self):
        assert pkg.classify(
            "Airén Spanien halbtrocken, Literflasche, Weißwein",
            volume_l=1.0) == pkg.GLASS

    def test_pouch_is_kept_apart_from_bag_in_box(self):
        assert pkg.classify(
            "Holiday Mood Pouch IGP Pays D'Oc rosé trocken, Roséwein 2025",
            volume_l=1.5) == pkg.POUCH

    def test_an_ordinary_bottle_says_nothing_and_stays_unknown(self):
        # "The retailer did not say" is not the same fact as "the retailer said
        # glass", and the report distinguishes them.
        assert pkg.classify("Rheingau Riesling QbA trocken, Weißwein 2024",
                            volume_l=0.75) == pkg.UNKNOWN


class TestScope:
    def test_only_pet_and_bag_in_box_are_in_scope(self):
        assert pkg.is_in_scope(pkg.PET)
        assert pkg.is_in_scope(pkg.BAG_IN_BOX)
        for other in (pkg.CARTON, pkg.POUCH, pkg.GLASS, pkg.CAN, pkg.UNKNOWN):
            assert not pkg.is_in_scope(other)


class TestPfand:
    def test_pet_within_the_range_carries_the_deposit(self):
        # Since 1 January 2022 the 0.25 EUR applies to every single-use plastic
        # beverage bottle, which is what brought wine in PET into the scheme.
        assert pkg.pfand(pkg.PET, 1.0) == 0.25
        assert pkg.pfand(pkg.PET, 0.75) == 0.25
        assert pkg.pfand(pkg.PET, 3.0) == 0.25

    def test_pet_outside_the_range_does_not(self):
        assert pkg.pfand(pkg.PET, 5.0) == 0.0
        assert pkg.pfand(pkg.PET, 0.05) == 0.0

    def test_bag_in_box_and_carton_are_exempt(self):
        # VerpackG §31(4) exempts "ökologisch vorteilhafte" containers: cartons
        # and pouches. A bag-in-box is both.
        assert pkg.pfand(pkg.BAG_IN_BOX, 3.0) == 0.0
        assert pkg.pfand(pkg.CARTON, 1.0) == 0.0
        assert pkg.pfand(pkg.POUCH, 1.5) == 0.0

    def test_single_use_glass_wine_is_exempt(self):
        assert pkg.pfand(pkg.GLASS, 0.75) == 0.0

    def test_an_unknown_container_has_an_unknown_deposit(self):
        assert pkg.pfand(pkg.UNKNOWN, 0.75) is None
        assert pkg.pfand(pkg.PET, None) is None

    def test_the_deposit_is_added_to_reach_the_till_price(self):
        assert pkg.price_with_pfand(2.49, pkg.PET, 1.0) == 2.74
        assert pkg.price_with_pfand(9.99, pkg.BAG_IN_BOX, 3.0) == 9.99
        assert pkg.price_with_pfand(2.49, pkg.UNKNOWN, 0.75) is None
