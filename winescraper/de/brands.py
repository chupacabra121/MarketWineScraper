"""Whether each ranked bag-in-box is a retailer's own label, and how we know.

This is hand-collected evidence, not derived data, so it lives next to the code
in the same spirit as ``decisions.jsonl`` on the Romanian side: a human read the
sources, and the file records what they read rather than a number a rerun would
regenerate.

**What counts as evidence.** Three kinds are used, in descending strength:

1. **Sold by unrelated retailers.** A private label is by definition exclusive
   to the chain that owns it. Finding the identical product at two or more
   unrelated shops settles the question against private label, and it is the
   easiest claim for a reader to check — the links are in ``sources``.
2. **The producer presents it as their own brand.** A brand page on the
   bottler's own site is the producer asserting ownership.
3. **The responsible food business operator.** German and EU food law (LMIV
   Art. 8 and 9) requires the operator under whose name the food is marketed to
   be named, and for distance selling it must appear before the purchase
   (Art. 14). Retailers publish it in the product detail.

That third field is often misread, so it is worth being explicit: naming a
winery as the operator does **not** rule out a private label. Germany's large
contract bottlers — Peter Mertes, Zimmermann-Graeff & Müller, Einig-Zenzen —
fill both their own brands and retailers' labels, and appear as the operator on
either. The operator answers "who is legally responsible", and only the first
two kinds of evidence answer "whose brand is it".

**Where the evidence runs out it says so.** ``private_label=None`` means the
sources did not settle it, and the workbook prints that rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrandEvidence:
    """One judgement about one listing, with what it rests on."""

    retailer: str
    #: Substring that identifies the listing within that retailer's rows.
    matches: str
    #: True = the retailer's own label; False = someone else's brand;
    #: None = the sources did not settle it.
    private_label: bool | None
    #: Who owns the brand, as far as the sources show.
    brand_owner: str
    #: The responsible food business operator as the listing states it.
    operator: str
    #: One sentence a reader can check against the links.
    basis: str
    sources: list[str] = field(default_factory=list)


#: Collected 14 August 2026. Ordered by retailer, then by rank in the
#: cheapest-three ranking.
EVIDENCE: list[BrandEvidence] = [
    # -- Combi ------------------------------------------------------------
    BrandEvidence(
        "combi", "Terra Molino", False,
        "Weinkellerei Einig-Zenzen GmbH & Co. KG",
        "Einig-Zenzen GmbH & Co. KG, Carl-Friedrich-Benz-Str. 8, 56759 Kaisersesch",
        "Einig-Zenzen presents Terra Molino as its own registered brand "
        "(written 'Terra Molino®'), and sells it through other retailers.",
        ["https://einig-zenzen.de/",
         "https://www.combi.de/terra_molino_airen_und_sauvignon_blanc_vino_blanc_weisswein_trocken_4504073814.html",
         "https://www.winzer24.de/weinkellerei-einig-zenzen-cape-wine-rosewein-trocken-bag-in-box-3-l-3/"]),
    BrandEvidence(
        "combi", "Weiß & Süß", None,
        "Weinkellerei Einig-Zenzen (bottler); brand owner not established",
        "Einig-Zenzen GmbH & Co. KG, 56759 Kaisersesch",
        "The name is descriptive rather than a brand, and no source found "
        "shows it at another retailer or on the bottler's brand list. Not "
        "Combi-branded, but exclusivity is unproven either way.",
        ["https://www.combi.de/weiss_und_suess_bib_weisswein_suess_4504073831.html"]),
    BrandEvidence(
        "combi", "Chenin Blanc Wine Box", None,
        "Zimmermann-Graeff & Müller (bottler); brand owner not established",
        "Zimmermann-Graeff & Müller GmbH & Co. KG, 56856 Zell/Mosel",
        "'Wine Box' is a format description, not a brand. Nothing found "
        "places it at another retailer.",
        ["https://www.combi.de/chenin_blanc_wine_box_weisswein_trocken_4504072690.html"]),

    # -- Globus -----------------------------------------------------------
    BrandEvidence(
        "globus", "BIB Blanco Vino de la Tierra de Castilla", None,
        "not established — GTIN 8410702034371 was issued by GS1 Spain",
        "not published by Globus",
        "Globus publishes no food business operator for this listing, which "
        "is the field that would settle it. The GTIN's 841 prefix is a "
        "Spanish GS1 allocation, so the barcode was not taken out by Globus "
        "in Germany — suggestive of a Spanish brand owner, not proof.",
        ["https://produkte.globus.de/getraenke/wein/weisswein/8410702034371/bib-blanco-vino-de-la-tierra-de-castilla",
         "https://www.gs1.org/standards/id-keys/company-prefix"]),
    BrandEvidence(
        "globus", "BIB Tinto Vino de la Tierra de Castilla", None,
        "not established — GTIN 8410702000789 was issued by GS1 Spain",
        "not published by Globus",
        "Same as the Blanco: no operator published, Spanish GTIN prefix, and "
        "the same GS1 company prefix 8410702 as its white sibling.",
        ["https://produkte.globus.de/getraenke/wein/rotwein/8410702000789/bib-tinto-vino-de-la-tierra-de-castilla"]),
    BrandEvidence(
        "globus", "Trevenezie Garganega Chardonnay", None,
        "not established — GTIN 8032841820433 was issued by GS1 Italy",
        "not published by Globus",
        "'Trevenezie' is the Italian IGT appellation, not a brand. No "
        "operator published; the 803 GTIN prefix is an Italian allocation.",
        ["https://produkte.globus.de/getraenke/wein/weisswein/8032841820433/trevenezie-garganega-chardonnay-3l-bib-weisswein"]),

    # -- Lidl -------------------------------------------------------------
    # The three share one retailer-defined name and come from three different
    # bottlers, which is the signature of a line the retailer controls.
    BrandEvidence(
        "lidl", "Vino Blanco Airén", True,
        "Lidl (unbranded own line; no manufacturer brand on the pack)",
        "Bodegas Isidro Milagro, R.E. CLM525/CR/ES, 13200 Manzanares, Spain",
        "Carries no manufacturer brand, appears only on lidl.de, and the "
        "identically-named line is filled by three different bottlers — "
        "Bodegas Isidro Milagro, Félix Solís and Vineris — which only "
        "happens when the retailer owns the specification.",
        ["https://www.lidl.de/p/vino-blanco-airen-3-l-bag-in-box-halbtrocken-weisswein-2025/p100396913"]),
    BrandEvidence(
        "lidl", "Vino Rosado Tempranillo", True,
        "Lidl (unbranded own line)",
        "Félix Solís, S.L., 13300 ES, Spain",
        "Same line as the Blanco and Tinto, different bottler, Lidl-only.",
        ["https://www.lidl.de/p/vino-rosado-tempranillo-3-l-bag-in-box-trocken-rosewein-2025/p100336259"]),
    BrandEvidence(
        "lidl", "Vino Tinto Tempranillo", True,
        "Lidl (unbranded own line)",
        "Vineris GmbH, D-47447 Moers-Kapellen; packed by D-NW 170 002",
        "Same line again, this time filled by a German bottler — the clearest "
        "sign that the name belongs to Lidl and not to any producer.",
        ["https://www.lidl.de/p/vino-tinto-tempranillo-spanien-3-0-l-bag-in-box-trocken-rotwein-2025/p100359207"]),

    # -- METRO ------------------------------------------------------------
    BrandEvidence(
        "metro", "Cerro de La Cruz De La Cruz Weißwein", False,
        "Cerro de la Cruz (Spanish producer brand)",
        "not published anonymously by METRO",
        "Sold by retailers unconnected to METRO — Kaufland, Weinkontor "
        "Scheucher, gute-freunde.de, MyBio — so it cannot be a METRO label.",
        ["https://www.kaufland.de/product/325859301/",
         "https://www.weinkontor-scheucher.de/de/cerro-de-la-cruz-vino-tinto-10-liter-bag-in-box",
         "https://gute-freunde.de/products/cerro-de-la-cruz-vino-blanco-spanien-weisswein-trocken-10l-bib"]),
    BrandEvidence(
        "metro", "Cerro de La Cruz Rotwein", False,
        "Cerro de la Cruz (Spanish producer brand)",
        "not published anonymously by METRO",
        "Same brand as the Weißwein; the red is the one Kaufland lists.",
        ["https://www.kaufland.de/product/325859301/",
         "https://www.weinkontor-scheucher.de/de/cerro-de-la-cruz-vino-tinto-10-liter-bag-in-box"]),
    BrandEvidence(
        "metro", "Batuta Macabeo", False,
        "Bodegas Artero, Noblejas (Toledo), Spain",
        "not published anonymously by METRO",
        "Bodegas Artero's own brand, sold at Amazon.de, wein.cc, "
        "Weinkontor Scheucher and gute-freunde.de as well as METRO.",
        ["https://www.amazon.de/Batuta-Macabeo-Sauvignon-Blanc-Wei%C3%9Fwein/dp/B0CGDV3Q1X",
         "https://www.weinkontor-scheucher.de/de/batuta-macabeo-sauvignon-blanc-bag-in-box-5l-bodegas-artero",
         "https://gute-freunde.de/products/batuta-macabeo-sauvignon-blanc-weisswein-5l-bib"]),

    # -- NORMA ------------------------------------------------------------
    BrandEvidence(
        "norma", "Adventure Tempranillo", None,
        "Zimmermann-Graeff & Müller — third-party listings write it "
        "'Zimmermann-Graeff Adventure'",
        "Zimmermann-Graeff & Müller GmbH Weinkellerei, Barlstraße 35, "
        "56856 Zell/Mosel",
        "The brand is attributed to the bottler by an independent comparison "
        "site, but no shop other than NORMA was found selling it. "
        "Producer-owned brand carried exclusively by one retailer is a "
        "genuinely intermediate case, so it is left unresolved.",
        ["https://www.norma24.de/de/p/adventure-tempranillo-bag-in-box-3-l-1097851",
         "https://www.topratgeber24.de/amp/bag-in-box-wein/adventure-tempranillo-vino-tinto-de-espana-trocken-bag-in-box"]),
    BrandEvidence(
        "norma", "Altobello Bianco", False,
        "Zimmermann-Graeff & Müller",
        "Zimmermann-Graeff & Müller GmbH Weinkellerei, 56856 Zell/Mosel",
        "The Altobello brand is also sold by Lieferello, a retailer "
        "unconnected to NORMA.",
        ["https://www.norma24.de/de/p/altobello-bianco-igp-veneto-bag-in-box-3-l-1097847",
         "https://www.lieferello.de/Rotweine-in-der-Bag-in-Box/Altobello-Vino-Rosso-Rotwein-12-5-vol-Bag-in-Box-3-0l.html"]),
    BrandEvidence(
        "norma", "Liebfraumilch", False,
        "no brand — Liebfraumilch is a protected wine designation",
        "Peter Mertes KG, In der Bornwiese 4, 54470 Bernkastel-Kues",
        "'Liebfraumilch' is a legally defined German wine designation that "
        "any producer meeting the rules may use, so the listing carries no "
        "brand at all — neither the retailer's nor a producer's.",
        ["https://www.norma24.de/de/p/liebfraumilch-30l-bag-in-box-1096599"]),

    # -- Netto ------------------------------------------------------------
    BrandEvidence(
        "netto", "Maybach Grauer Burgunder", False,
        "Peter Mertes KG",
        "Weinkellerei Peter Mertes KG, Bornwiese 4, 54470 Bernkastel-Kues",
        "Maybach is Peter Mertes' own brand — it has a product page on the "
        "producer's site and was named Top-Marke des Jahres 2025 — and it is "
        "stocked across German retail rather than by Netto alone.",
        ["https://www.mertes.de/produkte/maybach/",
         "https://www.mertes.de/ausgezeichnet-maybach-ist-top-marke-des-jahres-2025-2/",
         "https://shop.scandinavian-park.com/de/maybach-weisser-burgunder-trocken-12-30l-bag-in-box"]),
    BrandEvidence(
        "netto", "Maybach Sauvignon Blanc", False,
        "Peter Mertes KG",
        "Weinkellerei Peter Mertes KG, Bornwiese 4, 54470 Bernkastel-Kues",
        "Same brand as the Grauer Burgunder above.",
        ["https://www.mertes.de/produkte/maybach/"]),
    BrandEvidence(
        "netto", "Bree Chardonnay", False,
        "Peter Mertes KG",
        "Weinkellerei Peter Mertes KG, Bornwiese 4, DE-54470 Bernkastel-Kues",
        "Bree is a Peter Mertes brand with its own page on the producer's "
        "site, and REWE lists the identical 3-litre Chardonnay.",
        ["https://www.mertes.de/produkte/bree/",
         "https://www.rewe.de/shop/p/bree-weisswein-chardonnay-halbtrocken-3l/7718449",
         "https://www.supermarktcheck.de/rewe/sortiment/hersteller/bree-collection"]),

    # -- Wein Schäpers ----------------------------------------------------
    BrandEvidence(
        "schaepers", "Hauswein Rosé", True,
        "Wein Schäpers (own entry line; no manufacturer brand on the pack)",
        "F.S.S.L. (Félix Solís), ES-13300 Ciudad Real",
        "'Hauswein' is the shop's own house-wine line, named for the shop "
        "rather than the producer, carrying no manufacturer brand and sold "
        "nowhere else. The bottler named is a Spanish contract winery.",
        ["https://wein-schaepers.de/hauswein-rose-halbtrocken-bag-in-box-3-0l"]),
    BrandEvidence(
        "schaepers", "Hauswein Rot", True,
        "Wein Schäpers (own entry line)",
        "F.S.S.L. (Félix Solís), ES-13300 Ciudad Real",
        "Same line as the Rosé; the listing states the Inverkehrbringer "
        "outright.",
        ["https://wein-schaepers.de/hauswein-rot-halbtrocken-bag-in-box-3-0l"]),
    BrandEvidence(
        "schaepers", "Hauswein Weiß", True,
        "Wein Schäpers (own entry line)",
        "F.S.S.L. (Félix Solís), ES-13300 Ciudad Real",
        "Same line as the Rosé and Rot.",
        ["https://wein-schaepers.de/hauswein-weiss-halbtrocken-bag-in-box-3-0l"]),

    # -- Weinfreunde ------------------------------------------------------
    BrandEvidence(
        "weinfreunde", "Biqueirão Branco", False,
        "Adega Cooperativa de Carvoeira, Portugal",
        "Adega Cooperativa de Carvoeira, P-2585-138 Carvoeira, Portugal",
        "The co-operative's own brand: Weinfreunde names it as producer, and "
        "Amazon.de and Winzer24 sell the same wine.",
        ["https://www.amazon.de/-/en/895001184/dp/B0066425X4",
         "https://www.winzer24.de/biqueirao-branco-bag-in-box-50-l-adega-cooperativa-de-carvoeira-portugiesischer-weisswein/",
         "https://www.weinfreunde.de/p/biqueirao-branco-bag-in-box-5-0-l-adega-cooperativa-de-carvoeira/"]),
    BrandEvidence(
        "weinfreunde", "Biqueirão tinto", False,
        "Adega Cooperativa de Carvoeira, Portugal",
        "Adega Cooperativa de Carvoeira, P-2585-138 Carvoeira, Portugal",
        "Same producer brand as the Branco; the listing names the bottler in "
        "its Hersteller/Abfüller field.",
        ["https://www.amazon.de/Adega-Coop-Carvoeira-Biqueirao-trocken/dp/B0066424HQ",
         "https://www.winzer24.de/biqueirao-tinto-bag-in-box-50-l-adega-cooperativa-de-carvoeira-portugiesischer-rotwein/"]),
    BrandEvidence(
        "weinfreunde", "Miluna Primitivo", False,
        "Cantine San Marzano, Puglia",
        "Cantine San Marzano, San Marzano di San Giuseppe, Italy",
        "Weinfreunde names San Marzano as the producer in the listing itself; "
        "the co-operative markets its own labelled ranges.",
        ["https://www.weinfreunde.de/p/miluna-primitivo-salento-bag-in-box-5-0-l-cantine-san-marzano/"]),

    # -- WirWinzer --------------------------------------------------------
    # A marketplace rather than a retailer: the wines are the growers' own and
    # WirWinzer never puts a name of its own on a pack.
    BrandEvidence(
        "wirwinzer", "Bag-in-Box Rotweincuvée", False,
        "Winzergenossenschaft Herxheim am Berg (Pfalz)",
        "Winzergenossenschaft Herxheim am Berg",
        "WirWinzer is a winery-direct marketplace; the listing is filed under "
        "the co-operative's own producer page and sold under its name.",
        ["https://wirwinzer.de/weinherkunft/deutschland/weinregionen/pfalz/winzergenossenschaft-herxheim-am-berg",
         "https://wirwinzer.de/herxheim-am-berg-2023-bag-in-box-rotweincuvee-3-0-l-868068000.html"]),
    BrandEvidence(
        "wirwinzer", "Bag-in-Box Roséwein", False,
        "Winzergenossenschaft Herxheim am Berg (Pfalz)",
        "Winzergenossenschaft Herxheim am Berg",
        "Same grower as the Rotweincuvée.",
        ["https://wirwinzer.de/herxheim-am-berg-2024-bag-in-box-rosewein-3-0-l-868067000.html"]),
    BrandEvidence(
        "wirwinzer", "Bag-in-Box Riesling", False,
        "Winzergenossenschaft Herxheim am Berg (Pfalz)",
        "Winzergenossenschaft Herxheim am Berg",
        "Same grower again.",
        ["https://wirwinzer.de/herxheim-am-berg-2025-bag-in-box-riesling-3-0-l-868066000.html"]),
]


def lookup(retailer: str, name: str) -> BrandEvidence | None:
    """The evidence for one listing, matched on retailer and name fragment.

    Matched on a fragment rather than on an id because retailers renumber
    products between vintages — Lidl's 2025 Vino Tinto has a different page id
    from the 2024 one, and the judgement is about the line, not the vintage.
    """
    folded = (name or "").casefold()
    for record in EVIDENCE:
        if record.retailer == retailer and record.matches.casefold() in folded:
            return record
    return None
