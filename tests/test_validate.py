"""Data checks: what each one is for, and what it must not flag."""

from winescraper.validate import check, summarise, wine_signals


def row(**kw):
    base = dict(retailer="testmart", external_id="1", name="Vin rosu sec 0.75L",
                price=40.0, volume_l=0.75, category_path="Vinuri/Vin rosu",
                colour="rosu", sweetness="sec", grape_varieties="Merlot", abv=13.0,
                unit_price=None, unit_price_unit=None,
                # Every stored observation carries one; a row without it is
                # what "deposit unknown" is there to catch.
                deposit=0.50)
    base.update(kw)
    return base


def kinds(rows):
    return {f.kind for f in check(rows)}


def test_a_clean_row_produces_nothing():
    assert check([row()]) == []


def test_unit_price_disagreement_is_caught():
    """The retailer's own per-litre figure is the only external check we have."""
    findings = check([row(price=77.99, volume_l=0.75, unit_price=51.99,
                          unit_price_unit="l")])
    assert [f.kind for f in findings] == ["unit price disagrees"]


def test_unit_price_rounding_is_tolerated():
    assert check([row(price=40.0, volume_l=0.75, unit_price=53.0,
                      unit_price_unit="l")]) == []


def test_a_per_kilo_unit_price_is_not_compared():
    """Only per-litre figures are comparable to price / volume."""
    assert check([row(unit_price=9.99, unit_price_unit="kg")]) == []


def test_duplicate_ids_are_caught():
    assert kinds([row(), row(name="Vin alb sec 0.75L")]) == {"duplicate id"}


def test_sentinel_price_is_caught():
    """Carrefour lists an unavailable wine at 9,999 lei rather than hiding it."""
    assert "price too high" in kinds([row(price=9999.0)])


def test_a_real_cheap_two_litre_wine_is_not_flagged():
    """Carrefour's 2 L PET table wine at 10.99 lei is genuine, not a misparse."""
    assert check([row(price=10.99, volume_l=2.0)]) == []


def test_review_queue_catches_a_row_nothing_recognises():
    """This is the check that found fruit wine and "Zero Alcool" — neither had
    a rule written for it."""
    findings = check([row(name="Costieres Nimes 0.75L", colour=None,
                          sweetness=None, grape_varieties=None, abv=None)])
    assert [f.kind for f in findings] == ["review"]


def test_an_ordinary_wine_does_not_reach_the_review_queue():
    assert "review" not in kinds([row(name="Geneza Rara Neagra 0.75L")])


def test_wine_signals_counts_independent_evidence():
    assert wine_signals(row()) == 5
    assert wine_signals(row(name="Bordeaux Caf 0.75L", colour=None, sweetness=None,
                            grape_varieties=None, abv=None)) == 0


def test_summarise_orders_by_frequency():
    findings = check([row(price=9999.0), row(external_id="2", price=9999.0),
                      row(external_id="3", price=-1.0)])
    assert list(summarise(findings))[0] == "price too high"
