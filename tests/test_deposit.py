"""The SGR deposit: which containers carry it, and who has already added it."""

from __future__ import annotations

import pytest

from winescraper import deposit, pricing


class TestContainer:
    """Which packaging the deposit is charged on."""

    @pytest.mark.parametrize("volume_l, name", [
        (0.75, "Vin alb sec Cotnari 0.75L"),
        (2.0, "BABANU VIN ALB DEMIDULCE 2,0"),
        (1.5, "Sange de Taur 1.5L"),
        (0.187, "Vin Alb Budureasca Clasic 0.187l"),
        (0.1, "miniature"),
        (3.0, "BOTTEGA Gold Prosecco SGR 3 L"),      # a 3 L bottle, marked
    ])
    def test_bottles_and_pet_carry_it(self, volume_l, name):
        assert deposit.amount(volume_l, name) == deposit.AMOUNT

    @pytest.mark.parametrize("volume_l, name", [
        (3.0, "COTNARI Eticheta Galbena Vin Alb Demisec 3 L"),   # box by size
        (3.0, "Schwaben Wein, Bag in box, 3 l"),
        (2.0, "Vin rosu Cramele Recas BIB 2L"),
        (5.0, "VAL DUNA Blanc De Roumanie 5 L"),
        (10.0, "VINEXPORT Premiat Alb Demisec 10 L"),
        (0.05, "sample"),
    ])
    def test_boxes_and_oversize_do_not(self, volume_l, name):
        assert deposit.amount(volume_l, name) == 0.0

    def test_unstated_size_is_undecidable_not_exempt(self):
        # Reading this as exempt would shave 0.50 off a bottle that has one.
        assert deposit.amount(None, "Jidvei Vin alb Sauvignon Blanc") is None

    def test_a_retailers_own_figure_wins_over_the_rule(self):
        # METRO says this 2 L Budureasca carries nothing; the rule would charge.
        assert deposit.amount(2.0, "BUDUREASCA Fume Vin Alb Demisec 2 L",
                              published=0.0) == 0.0
        # And a two-bottle pack carries two deposits, which no rule reading a
        # single volume off a title could know.
        assert deposit.amount(0.937, "MATEUS Pachet SGR 0,75 + 0,187 L",
                              published=1.0) == 1.0


class TestBasis:
    """Whether a source's published price already contains the deposit."""

    def test_every_source_has_a_recorded_basis(self):
        from winescraper.sites import all_adapters

        priced = {key for key, adapter in all_adapters().items()
                  if adapter.catalogue != "none"}
        assert priced <= set(deposit.INCLUDED_IN_PRICE), (
            "a source with no recorded deposit basis would silently be treated "
            "as deposit-exclusive: " + str(priced - set(deposit.INCLUDED_IN_PRICE)))

    def test_deposit_is_added_where_the_price_lacks_it(self):
        assert deposit.payable("metro", 0.75, "Sange de Taur SGR 0,75 L") == 0.50

    def test_nothing_is_added_to_an_exempt_container(self):
        assert deposit.payable("carrefour", 3.0, "Cotnari Eticheta Galbena 3L") == 0.0

    def test_an_unproven_source_is_unknown_rather_than_zero(self):
        assert deposit.included("sezamo") is None
        assert deposit.payable("sezamo", 0.75, "Crama Girboiu Sauvignon Blanc") is None
        # But an exempt container needs no evidence: nothing is owed either way.
        assert deposit.payable("sezamo", 5.0, "Crama Starmina 5 L") == 0.0


class TestPricing:
    """What the reports read."""

    def _row(self, **kw):
        row = {"retailer": "carrefour", "name": "Vin alb Cotnari 0.75L",
               "volume_l": 0.75, "price": 16.99, "list_price": None,
               "on_promotion": False, "deposit": 0.50}
        row.update(kw)
        return row

    def test_prices_are_what_the_shopper_hands_over(self):
        row = self._row()
        assert pricing.regular(row) == pytest.approx(17.49)
        assert pricing.paid(row) == pytest.approx(17.49)
        assert pricing.published_regular(row) == 16.99

    def test_the_deposit_rides_on_the_regular_price_too(self):
        row = self._row(price=12.99, list_price=16.99, on_promotion=True)
        assert pricing.regular(row) == pytest.approx(17.49)
        assert pricing.discounted(row) == pytest.approx(13.49)
        assert pricing.published_regular(row) == 16.99
        # The discount is a share of the price, so adding the same deposit to
        # both sides must not move it far.
        assert pricing.discount_share(row) == pytest.approx(0.2286, abs=1e-3)

    def test_an_exempt_container_is_unchanged(self):
        row = self._row(volume_l=3.0, name="Cotnari Eticheta Galbena 3L",
                        price=42.15, deposit=0.0)
        assert pricing.paid(row) == 42.15

    def test_the_stored_deposit_beats_the_rule(self):
        # Recorded at scrape time, so a later change of rule cannot rewrite
        # what a past price actually was.
        row = self._row(deposit=0.0)
        assert pricing.paid(row) == 16.99

    def test_per_litre_follows_the_price_it_is_given(self):
        row = self._row(volume_l=2.0, price=18.30, name="MUSCATEL 2,0 PET")
        assert pricing.per_litre(pricing.paid(row), 2.0) == pytest.approx(9.40)
