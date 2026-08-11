"""Recognising the same wine under thirteen different names.

Every title in this file was collected from a retailer's wine category. The
pairs that must merge and the pairs that must not are both real: over-merging
corrupts a price comparison, which is worse than missing one, so both directions
are pinned.
"""

import pytest

from winescraper.identity import (
    RANGE_RE, brand_lexicon, expand, group_wines, signature,
)


def listing(name, retailer="testmart", **kw):
    row = dict(retailer=retailer, external_id=name[:20] + retailer, name=name,
               brand=kw.pop("brand", None), price=kw.pop("price", 40.0),
               volume_l=kw.pop("volume_l", 0.75), colour=kw.pop("colour", None),
               sweetness=kw.pop("sweetness", None), vintage=kw.pop("vintage", None),
               grape_varieties=kw.pop("grape_varieties", None),
               sparkling=kw.pop("sparkling", None))
    row.update(kw)
    return row


def keys_for(rows):
    """``{name: wine_key}`` for a set of listings grouped together."""
    return {r["name"]: g.key for g in group_wines(rows) for r in g.rows}


def same_wine(rows):
    return len({g.key for g in group_wines(rows)}) == 1


# ------------------------------------------------------------------ expansion

@pytest.mark.parametrize("abbreviated,full", [
    ("PURCARI CAB SAUV SEC 14% IG 0.75L", "cabernet sauvignon"),
    ("CORCOVA SAUV BLANC SEC 13.7% 0.75L", "sauvignon blanc"),
    ("ZESTREA SAUVG BLANC DMS 12% 0.75L", "sauvignon blanc"),
    ("BEC DOMNESC FET N DMS 0.75L", "feteasca neagra"),
    ("MOTIV FET REG CHARD DMS 13.5% 0.75L", "feteasca regala"),
    ("COTNARI TAM. ROM DMS DOC 14% 0.75L", "tamaioasa romaneasca"),
    ("CRICOVA PRESTIGE PIN GRIG SEC14.5%0.75LS", "pinot grigio"),
    ("NAVIGO CHARD SEC DOC 13.5% 0.75L", "chardonnay"),
])
def test_cash_and_carry_abbreviations_are_expanded(abbreviated, full):
    """Kaufland and Selgros abbreviate to the point of being a different
    language; nothing matches until the words are restored."""
    assert full in expand(abbreviated)


def test_dom_is_only_expanded_when_it_is_an_abbreviation():
    """"Dom." means Domeniile. "Domnesc" does not, and rewriting it to
    "domeniile nesc" poisoned the brand lexicon for nine retailers."""
    assert expand("BEC DOMNESC ROSE DMS DOC 12% 0.75L") == "beciul domnesc rose dms doc 12% 0.75l"
    assert "domeniile" in expand("DOM. TOHANI FETEASCA NEAGRA")


# --------------------------------------------------------------------- brands

def test_brand_lexicon_learns_from_retailers_that_publish_one():
    rows = [listing("Vin rosu Purcari", brand="Purcari"),
            listing("Vin alb Purcari", brand="Purcari 1827", retailer="b"),
            listing("Odd", brand="Seen Once", retailer="c")]
    lexicon = brand_lexicon(rows)
    assert "purcari" in lexicon
    # A brand seen once is as likely to be a mis-filled field as a real brand.
    assert "seen once" not in lexicon


def test_a_missing_brand_field_is_read_from_the_title():
    """Kaufland, Penny, Profi and Supeco publish no brand at all — 1,064
    listings the previous matcher could not touch."""
    rows = [listing("Vin rose dulce Sange de Taur, 0.75 l", "auchan",
                    brand="Sange de Taur", colour="rose", sweetness="dulce"),
            listing("Vin rose dulce Sange de Taur 750ml", "carrefour",
                    brand="Sange de Taur", colour="rose", sweetness="dulce"),
            listing("SANGE DE TAUR ROSE DLC 10.5% 0.75L", "kaufland_bolt",
                    colour="rose", sweetness="dulce")]
    # "de" is dropped so that "Sange de Taur" and "Sange Taur" are one brand.
    assert signature(rows[2], brand_lexicon(rows)).brand == "sange taur"
    assert same_wine(rows)


def test_a_colour_word_inside_a_brand_survives():
    """"Casa de Rose" must not reduce to "Casa", which would merge a Recaș
    range with every other brand starting with that word."""
    row = listing("CASA DE ROSE Feteasca Neagra Vin Rose Sec", brand="Casa de Rose")
    assert signature(row).brand == "casa rose"


# ------------------------------------------------------- merging across shops

def test_nine_names_for_one_purcari_chardonnay():
    rows = [
        listing("Vin alb sec Purcari Chardonnay, 0.75 l", "auchan", brand="Purcari"),
        listing("Vin alb sec Purcari Chardonnay 0.75L", "carrefour", brand="Purcari"),
        listing("PURCARI CHARDONNAY SEC 13.5% IG 0.75L", "kaufland_bolt"),
        listing("Vin alb sec Chardonnay de Purcari 0.75L", "mega_image", brand="Purcari"),
        listing("PURCARI 1827 Chardonnay de Purcari Vin Alb Sec SGR 0,75 L",
                "metro", brand="PURCARI 1827"),
        listing("Purcari chardonnay Vin alb sec 750 ml", "penny_bolt"),
        listing("PURCARI CHARDONNAY SEC 0,75", "selgros", brand="PURCARI"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_a_producer_stripped_from_the_title_still_matches():
    """Mega Image and Freshful drop the producer, leaving "Vin roze sec 0.75L".
    The brand field is the only thing left connecting it to the others."""
    rows = [
        listing("Vin sec rose de Purcari, 0.75 l", "auchan", brand="Purcari",
                colour="rose", sweetness="sec"),
        listing("Vin roze sec 0.75L", "mega_image", brand="Purcari",
                colour="rose", sweetness="sec"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_an_unstated_grape_is_resolved_when_the_others_agree():
    """Auchan names the grape, the rest do not. One reading, so it resolves."""
    rows = [
        listing("Vin rosu sec Negru de Purcari, Cabernet Sauvignon, 0.75 l",
                "auchan", brand="Purcari", colour="rosu", sweetness="sec",
                grape_varieties="Cabernet Sauvignon"),
        listing("NEGRU DE PURCARI ROSU SEC 0,75", "selgros", brand="PURCARI",
                colour="rosu", sweetness="sec"),
        listing("Vin Negru De Purcari, Sec, 0.75l", "carrefour", brand="Purcari",
                colour="rosu", sweetness="sec"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_an_unstated_grape_is_not_guessed_when_the_others_disagree():
    """Two grapes under one brand: an unlabelled listing could be either, so it
    keeps its own identity rather than being assigned to one."""
    rows = [
        listing("Vin alb sec Purcari Chardonnay", "auchan", brand="Purcari",
                colour="alb", sweetness="sec", grape_varieties="Chardonnay"),
        listing("Vin alb sec Purcari Pinot Grigio", "carrefour", brand="Purcari",
                colour="alb", sweetness="sec", grape_varieties="Pinot Grigio"),
        listing("Vin alb sec 0.75L", "mega_image", brand="Purcari",
                colour="alb", sweetness="sec"),
    ]
    assert len({g.key for g in group_wines(rows)}) == 3, keys_for(rows)


# --------------------------------------------------------- keeping them apart

def test_a_tier_word_separates_two_wines_of_the_same_brand():
    """Tohani Premium is 2.5x plain Tohani; Villa Vinea Classic is not Villa
    Vinea Selection."""
    rows = [
        listing("TOHANI Feteasca de TOHANI Vin Rosu Sec", "metro", brand="TOHANI",
                price=35.59, colour="rosu", sweetness="sec"),
        listing("TOHANI Premium Feteasca Neagra Vin Rosu Sec", "metro",
                brand="TOHANI", price=89.99, colour="rosu", sweetness="sec"),
    ]
    assert not same_wine(rows), keys_for(rows)


def test_a_colour_named_range_is_not_the_plain_wine():
    """"Roșu de Purcari" at 110 lei is not Purcari Cabernet Sauvignon at 39.
    The colour word is the range name, and Auchan sells both."""
    rows = [
        listing("Vin rosu sec Rosu de Purcari, Cabernet Sauvignon, 0.75 l",
                "auchan", brand="Purcari", price=109.99, colour="rosu",
                sweetness="sec", grape_varieties="Cabernet Sauvignon"),
        listing("Vin rosu sec Purcari, Cabernet Sauvignon, 0.75 l", "auchan",
                brand="Purcari", price=38.79, colour="rosu", sweetness="sec",
                grape_varieties="Cabernet Sauvignon"),
        listing("PURCARI CABERNET SAUVIGNON SEC 0,75", "selgros", brand="PURCARI",
                price=42.99, colour="rosu", sweetness="sec"),
    ]
    keys = keys_for(rows)
    assert keys["Vin rosu sec Rosu de Purcari, Cabernet Sauvignon, 0.75 l"] != \
        keys["Vin rosu sec Purcari, Cabernet Sauvignon, 0.75 l"]


def test_a_range_name_merges_when_no_retailer_uses_both():
    """Four shops say "Rosé de Purcari" and five just say Purcari rosé. No shop
    says both, so it is one wine described two ways."""
    rows = [
        listing("Vin sec rose de Purcari, 0.75 l", "auchan", brand="Purcari",
                colour="rose", sweetness="sec"),
        listing("Rose De Purcari Vin Sec 0.75L", "profi_glovo", colour="rose",
                sweetness="sec"),
        listing("PURCARI ROSE SEC 0,75", "selgros", brand="PURCARI",
                colour="rose", sweetness="sec"),
        listing("Purcari Vin rose sec 750 ml", "penny_bolt", colour="rose",
                sweetness="sec"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_different_bottle_sizes_are_different_products():
    rows = [
        listing("PURCARI CHARDONNAY SEC 0,75", "selgros", brand="PURCARI"),
        listing("PURCARI CHARDONNAY SEC 0,375", "selgros", brand="PURCARI",
                volume_l=0.375),
    ]
    assert not same_wine(rows)


@pytest.mark.parametrize("title,expected", [
    ("Vin rosu sec Negru de Purcari", "negru-purcari"),
    ("ROSU DE PURCARI ROSU SEC 0,75", "rosu-purcari"),
    ("Vin Alb Davino, Faurar Alb De Ceptura, Cupaj Sec", "alb-ceptura"),
    # A description, not a range: the colour is separated from the place.
    ("Vin alb sec de Purcari, Chardonnay 0.75 l", None),
    # Table wine is not a place.
    ("PERLA HANGITEI Vin Alb de Masa Demidulce SGR 2 L", None),
])
def test_colour_named_ranges_are_recognised_but_descriptions_are_not(title, expected):
    from winescraper.normalize import fold
    match = RANGE_RE.search(fold(title))
    assert ("-".join(match.groups()) if match else None) == expected


# ------------------------------------------------------------------- vintages

def test_a_cellar_vintage_identifies_the_bottle():
    """Cotnari's 1984 is twice the price of its 2007. The year is the product."""
    rows = [
        listing("COTNARI GRASA VINOTECA 2007 ALB DULCE 0,75", "selgros",
                brand="COTNARI", price=152.51, vintage=2007),
        listing("COTNARI GRASA VINOTECA 1984 ALB DULCE 0,75", "selgros",
                brand="COTNARI", price=305.03, vintage=1984),
        listing("COTNARI GRASA VINOTECA 2024 ALB DULCE 0,75", "selgros",
                brand="COTNARI", price=90.0, vintage=2024),
    ]
    assert len({g.key for g in group_wines(rows)}) == 3, keys_for(rows)


def test_a_recent_vintage_does_not_split_current_stock():
    """A 2023 Purcari Chardonnay and an unlabelled one are the same wine on the
    same shelf; treating the year as identity would split seven shops into
    eight."""
    rows = [
        listing("PURCARI 1827 Chardonnay Vin Alb Sec", "metro", brand="PURCARI 1827",
                colour="alb", sweetness="sec", vintage=2023),
        listing("Vin alb sec Purcari Chardonnay, 0.75 l", "auchan", brand="Purcari",
                colour="alb", sweetness="sec"),
        listing("PURCARI CHARDONNAY SEC 0,75", "selgros", brand="PURCARI",
                colour="alb", sweetness="sec", vintage=2024),
    ]
    assert same_wine(rows), keys_for(rows)


def test_an_unstated_vintage_is_never_pulled_into_a_cellar_wine():
    """A 22-lei Cotnari is not the 203-lei 1994, and the only difference in the
    titles is the year."""
    rows = [
        listing("COTNARI FETEASCA ALBA 1994 ALB DULCE 0,75", "selgros",
                brand="COTNARI", price=203.35, vintage=1994, colour="alb",
                sweetness="dulce"),
        listing("COTNARI FETEASCA ALBA 2024 ALB DULCE 0,75", "selgros",
                brand="COTNARI", price=25.0, vintage=2024, colour="alb",
                sweetness="dulce"),
        listing("Vin Cotnari Feteasca Alba 0.75L", "profi_glovo", price=21.99,
                colour="alb", sweetness="dulce"),
    ]
    keys = keys_for(rows)
    assert keys["Vin Cotnari Feteasca Alba 0.75L"] != \
        keys["COTNARI FETEASCA ALBA 1994 ALB DULCE 0,75"]


# ----------------------------------------------------------------------- keys

def test_the_key_is_stable_and_readable():
    rows = [listing("Vin rosu sec Purcari Merlot, 0.75 l", brand="Purcari",
                    colour="rosu", sweetness="sec")]
    key = group_wines(rows)[0].key
    assert key.startswith("purcari-merlot-rosu-sec-0-75l-")
    # Same input, same key: price history has to survive a re-scrape.
    assert group_wines(rows)[0].key == key


def test_the_key_does_not_depend_on_the_order_rows_arrive_in():
    rows = [
        listing("Vin alb sec Purcari Chardonnay", "auchan", brand="Purcari",
                colour="alb", sweetness="sec"),
        listing("PURCARI CHARDONNAY SEC 0,75", "selgros", brand="PURCARI",
                colour="alb", sweetness="sec"),
    ]
    assert keys_for(rows) == keys_for(list(reversed(rows)))


def test_a_weak_word_alone_never_becomes_an_identity():
    """Without a brand to qualify, "Premium" would merge every retailer's
    premium tier into a single wine."""
    rows = [listing("Vin Premium 0.75L", "a", colour="rosu", sweetness="sec"),
            listing("Vin Premium 0.75L", "b", colour="rosu", sweetness="sec")]
    assert group_wines(rows)[0].signature.anchor == frozenset()


# ------------------------------------------------- gaps the retailers leave

def test_a_shorter_brand_field_is_extended_from_the_title():
    """Auchan files "Pelin Carpatin" under the brand "Pelin", which left
    "carpatin" looking like the name of one particular wine."""
    rows = [
        listing("PELIN CARPATIN Vin Alb Demisec SGR 0,75 L", "metro",
                brand="PELIN CARPATIN", colour="alb", sweetness="demisec"),
        listing("PELIN CARPATIN ALB DEMISEC 0,75", "selgros",
                brand="PELIN CARPATIN", colour="alb", sweetness="demisec"),
        listing("Pelin Carpatin, Pelin alb demisec de Urlati, 0.75 l", "auchan",
                brand="Pelin", colour="alb", sweetness="demisec"),
    ]
    assert signature(rows[2], brand_lexicon(rows)).brand == "pelin carpatin"


def test_provenance_does_not_split_a_wine_from_itself():
    """Auchan and Supeco say "de Urlati"; METRO and Penny do not. Urlați is
    where the wine comes from, not which wine it is — and no rule can tell that
    from the word, so it is settled by nobody selling it both ways."""
    rows = [
        listing("Pelin Carpatin, Pelin alb demisec de Urlati, 0.75 l", "auchan",
                brand="Pelin", price=14.19, colour="alb", sweetness="demisec"),
        listing("PELIN CARPATIN Vin Alb SGR 0,75 L", "metro", brand="PELIN CARPATIN",
                price=15.25, colour="alb", sweetness="demisec"),
        # A brand has to be seen twice to enter the lexicon, so Selgros is here
        # for the same reason it is in the real data: it publishes the brand.
        listing("PELIN CARPATIN ALB DEMISEC 0,75", "selgros", brand="PELIN CARPATIN",
                price=15.99, colour="alb", sweetness="demisec"),
        listing("Pelin Carpatin vin alb 750 ml", "penny_bolt", price=16.85,
                colour="alb"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_the_three_colours_of_one_range_stay_apart():
    """Auchan sells Pelin Carpatin 1.5 L as three products at the same price.
    They are three wines, not one."""
    rows = [
        listing("Pelin Carpatin, Pelin alb demisec de Urlati, 1.5 l", "auchan",
                brand="Pelin", price=29.49, volume_l=1.5, colour="alb",
                sweetness="demisec"),
        listing("Pelin Carpatin, Pelin rose demisec de Urlati, 1.5 l", "auchan",
                brand="Pelin", price=29.49, volume_l=1.5, colour="rose",
                sweetness="demisec"),
        listing("Pelin Carpatin, Pelin rosu demisec de Urlati, 1.5 l", "auchan",
                brand="Pelin", price=29.49, volume_l=1.5, colour="rosu",
                sweetness="demisec"),
    ]
    assert len({g.key for g in group_wines(rows)}) == 3, keys_for(rows)


def test_resolution_does_not_require_every_attribute_to_be_stated():
    """Almost no wine names a grape, so demanding a fully described variant
    resolved nothing: METRO's "Vin Alb Demisec" and Penny's "vin alb" stayed
    apart as two wines."""
    rows = [
        listing("PELIN CARPATIN Vin Alb Demisec", "metro", brand="Pelin Carpatin",
                colour="alb", sweetness="demisec"),
        listing("Pelin Carpatin vin alb 750 ml", "penny_bolt", brand="Pelin Carpatin",
                colour="alb"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_prices_veto_a_merge_the_text_could_not_settle():
    """Selgros' "LOPEZ DE HARO CRIANZA" at 40 lei and METRO's plain "LOPEZ DE
    HARO" at 139 pass every textual test. The prices are the only evidence that
    they are different wines."""
    rows = [
        listing("LOPEZ DE HARO CRIANZA ROSU SEC 0,75", "selgros",
                brand="Lopez de Haro", price=39.77, colour="rosu", sweetness="sec"),
        listing("LOPEZ DE HARO Vin Rosu Sec SGR 0,75 L", "metro",
                brand="Lopez de Haro", price=139.0, colour="rosu", sweetness="sec"),
    ]
    assert not same_wine(rows), keys_for(rows)


def test_a_normal_price_gap_still_merges():
    """The price veto applies only to merges the text left ambiguous, and only
    at a gap no real cross-retailer spread reaches."""
    rows = [
        listing("PELIN CARPATIN ALB DEMISEC de Urlati 0,75", "selgros",
                brand="Pelin Carpatin", price=14.19, colour="alb", sweetness="demisec"),
        listing("PELIN CARPATIN Vin Alb SGR 0,75 L", "metro", brand="Pelin Carpatin",
                price=18.99, colour="alb", sweetness="demisec"),
    ]
    assert same_wine(rows), keys_for(rows)


def test_the_key_does_not_repeat_a_word():
    rows = [listing("Pelin rose de Urlati 0.75L", "mega_image", brand="Pelin Carpatin",
                    colour="rose", sweetness="demisec")]
    key = group_wines(rows)[0].key
    words = key.rsplit("-", 1)[0].split("-")
    assert len(words) == len(set(words)), key
