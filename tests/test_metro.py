"""METRO mapping tests against the betty-variants response shape.

The response nests result[article].variants[variant].bundles[bundle] and is
keyed by *article* number even when queried by variant id; prices hide three
traps (net vs gross, deposit-inclusive grossPrice, transient nulls) that these
tests pin down.
"""

import pytest

from winescraper.sites.metro import MetroAdapter

SPI = {
    "currency": "RON",
    "listNetPrice": 13.80,
    "listGrossPrice": 16.70,
    "vatPercent": 0.21,
    # grossPrice INCLUDES the SGR deposit — the classic trap.
    "grossPrice": 17.20,
    "netPrice": 14.30,
    "finalPricesInfo": {
        "articleNet": 13.80,
        "articleGross": 16.70,
        "articleVatAmount": 2.90,
        "emptiesGross": 0.50,
        "emptiesNet": 0.50,
        "sumGross": 17.20,
        "sumNet": 14.30,
    },
}

BUNDLE = {
    "description": "COTNARI Vin Feteasca Alba Demidulce SGR 0,75 L",
    "brandName": "COTNARI",
    "bundleNumber": "0021",
    "imageUrl": "https://cdn.metro-group.com/ro/ro_pim_796857001001_01.png",
    "customerDisplayId": "206296",
    "minOrderQuantity": 6,
    "contentData": {"netContentVolume": {"value": 750, "uom": "ML"}},
    "details": {
        "characteristicsTable": {
            "rows": [
                # U+0163 (t-cedilla) exactly as the live API sends it.
                {"rowLabel": "Soiul de viţă de vie",
                 "cells": [{"value": "Feteasca Alba, Cotnari"}]},
                {"rowLabel": "Tara de origine", "cells": [{"value": "România"}]},
                {"rowLabel": "Regiunea viticola", "cells": [{"value": "Podgoria Cotnari"}]},
                {"rowLabel": "Clasificare", "cells": [{"value": "Demidulce"}]},
                {"rowLabel": "An productie", "cells": [{"value": "2022"}]},
                {"rowLabel": "Crama", "cells": [{"value": "Crama Cotnari"}]},
                {"rowLabel": "Culoare", "cells": [{"value": "Alb"}]},
            ],
        },
    },
    "stores": {"00032": {"sellingPriceInfo": SPI}},
}

VARIANT = {
    "description": "COTNARI Vin Feteasca Alba Demidulce SGR 0,75 L",
    "availability": "AVAILABLE",
    "bettyVariantId": {"bettyVariantId": "BTY-X7968990032"},
    "categories": [{"name": "Alimentare / Bauturi Alcoolice, Vinuri & Bere / Vinuri Albe"}],
    "bundles": {"0021": BUNDLE},
}

RESPONSE = {"result": {"BTY-X796899": {"variants": {"0032": VARIANT}}}}


@pytest.fixture()
def adapter():
    return MetroAdapter(fetcher=None)


def test_extract_walks_article_keys_and_reads_variant_ids(adapter):
    merged, nulls = adapter._extract(RESPONSE)
    assert list(merged) == ["BTY-X7968990032"]
    assert nulls == []
    article_no, variant, bundle, spi = merged["BTY-X7968990032"]
    assert article_no == "BTY-X796899"
    assert spi["listGrossPrice"] == 16.70


def test_extract_flags_null_price_batches_for_retry(adapter):
    bundle = dict(BUNDLE, stores={"00032": {"sellingPriceInfo": None}})
    response = {"result": {"BTY-X796899": {"variants": {"0032": dict(VARIANT, bundles={"0021": bundle})}}}}
    merged, nulls = adapter._extract(response)
    assert merged == {}
    assert nulls == ["BTY-X7968990032"]


def test_price_is_article_gross_not_deposit_inclusive_gross(adapter):
    p = adapter._to_product("BTY-X796899", VARIANT, BUNDLE, SPI, "vinuri-albe")
    assert p.price == 16.70                      # VAT-incl, deposit-excl
    assert p.price != SPI["grossPrice"]          # 17.20 folds the deposit in
    assert p.raw["price_net"] == 13.80
    assert p.raw["deposit"] == 0.50
    # No strikethrough on wine: listGrossPrice == articleGross → no list_price.
    assert p.list_price is None
    assert p.on_promotion is False


def test_volume_from_net_content_volume(adapter):
    p = adapter._to_product("BTY-X796899", VARIANT, BUNDLE, SPI, "vinuri-albe")
    assert p.volume_l == 0.75
    assert p.price_per_litre == 22.27


def test_characteristics_matched_after_diacritic_folding(adapter):
    p = adapter._to_product("BTY-X796899", VARIANT, BUNDLE, SPI, "vinuri-albe")
    assert p.grape_varieties == ["Feteasca Alba", "Cotnari"]
    assert p.country == "România"
    assert p.region == "Podgoria Cotnari"
    assert p.producer == "Crama Cotnari"
    assert p.vintage == 2022
    assert p.sweetness == "demidulce"


def test_sweetness_brut_maps_to_sec(adapter):
    bundle = dict(BUNDLE)
    bundle["details"] = {"characteristicsTable": {"rows": [
        {"rowLabel": "Clasificare", "cells": [{"value": "Extra Brut"}]},
    ]}}
    p = adapter._to_product("BTY-X1", VARIANT, bundle, SPI, "vinuri-spumante")
    assert p.sweetness == "sec"
    assert p.sparkling is True


def test_title_colour_beats_wrong_characteristic(adapter):
    """~1.5% of rows have a wrong category or Culoare; the title wins."""
    bundle = dict(BUNDLE, description="GITANA WINERY LUPI Vin Rosu Sec SGR 0,75 L")
    bundle["details"] = {"characteristicsTable": {"rows": [
        {"rowLabel": "Culoare", "cells": [{"value": "Alb"}]},
    ]}}
    p = adapter._to_product("BTY-X2", VARIANT, bundle, SPI, "vinuri-rosii")
    assert p.colour == "rosu"


def test_category_colour_used_when_title_is_silent(adapter):
    bundle = dict(BUNDLE, description="PREDELLA Trebbiano SGR 0,75 L")
    bundle["details"] = {}
    p = adapter._to_product("BTY-X3", VARIANT, bundle, SPI, "vinuri-albe")
    assert p.colour == "alb"


def test_availability_and_identity(adapter):
    p = adapter._to_product("BTY-X796899", VARIANT, BUNDLE, SPI, "vinuri-albe")
    assert p.in_stock is True
    assert p.external_id == "BTY-X796899"
    assert p.raw["min_order_qty"] == 6
    assert "/shop/pv/BTY-X796899/" in p.url
    assert p.category_path == "Alimentare / Bauturi Alcoolice, Vinuri & Bere / Vinuri Albe"


def test_limited_counts_as_in_stock_unavailable_does_not(adapter):
    p = adapter._to_product("BTY-X1", dict(VARIANT, availability="LIMITED"),
                            BUNDLE, SPI, "vinuri-albe")
    assert p.in_stock is True
    p = adapter._to_product("BTY-X1", dict(VARIANT, availability="UNAVAILABLE"),
                            BUNDLE, SPI, "vinuri-albe")
    assert p.in_stock is False
