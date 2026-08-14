"""Every user-visible string in the workbook, in German and English.

The study is of the German market, so the workbook was written in German first
and the German wording is the original: where the two differ in emphasis, the
German is what was meant. English is a full translation rather than a summary —
same sheets, same rows, same footnotes — so the two files can be read side by
side and checked against each other.

Terms that are legal or trade names are not translated, because translating them
would make them unfindable: *Pfand*, *VerpackG*, *Bag-in-Box*, *Getränkekarton*,
*Literflasche*, *Grundpreis*. Each gets a gloss in the English text the first
time it appears.
"""

from __future__ import annotations

from . import packaging as pkg

LANGUAGES = ("de", "en")

#: Container names. German keeps the trade words; English glosses the two that
#: have no English equivalent on a shelf.
PACKAGING_LABELS = {
    "de": dict(pkg.LABELS),
    "en": {
        pkg.BAG_IN_BOX: "Bag-in-Box",
        pkg.PET: "PET bottle",
        pkg.CARTON: "Carton (Tetra Pak)",
        pkg.POUCH: "Stand-up pouch",
        pkg.CAN: "Can",
        pkg.GLASS: "Glass bottle",
        pkg.KEG: "Keg",
        pkg.UNKNOWN: "not stated",
    },
}

CHANNEL_LABELS = {
    "de": {
        "supermarkt": "Supermarkt", "discounter": "Discounter",
        "getraenkemarkt": "Getränkemarkt", "fachhandel": "Fachhandel",
        "cash_and_carry": "Cash & Carry", "online": "Online",
        "drogerie": "Drogerie", "bio": "Bio", "convenience": "Convenience",
    },
    "en": {
        "supermarkt": "Supermarket", "discounter": "Discounter",
        "getraenkemarkt": "Beverage store", "fachhandel": "Wine specialist",
        "cash_and_carry": "Cash & carry", "online": "Online",
        "drogerie": "Drugstore", "bio": "Organic", "convenience": "Convenience",
    },
}

COLOUR_LABELS = {
    "de": {"rot": "Rotwein", "weiss": "Weißwein", "rose": "Roséwein"},
    "en": {"rot": "Red", "weiss": "White", "rose": "Rosé"},
}

COUNTRY_LABELS = {
    "en": {
        "Deutschland": "Germany", "Italien": "Italy", "Frankreich": "France",
        "Spanien": "Spain", "Österreich": "Austria", "Südafrika": "South Africa",
        "Griechenland": "Greece", "Ungarn": "Hungary", "Rumänien": "Romania",
        "Australien": "Australia", "Neuseeland": "New Zealand",
        "Argentinien": "Argentina", "Moldawien": "Moldova",
    },
}

#: Why a retailer yielded no rows. The keys are the internal reason codes used
#: in :data:`winescraper.de.sources.UNAVAILABLE`.
REASON_HEADINGS = {
    "de": {
        "keine Preise online": "Kein Online-Sortiment mit Preisen",
        "blockiert": "Sortiment vorhanden, Zugriff gesperrt (HTTP 403)",
        "Preise clientseitig": "Erreichbar, Preise nicht im HTML",
        "nicht erreichbar": "Domain nicht erreichbar",
    },
    "en": {
        "keine Preise online": "No online catalogue with prices",
        "blockiert": "Catalogue exists, access blocked (HTTP 403)",
        "Preise clientseitig": "Reachable, prices not in the HTML",
        "nicht erreichbar": "Domain unreachable",
    },
}

STRINGS: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- sheets
    "sheet_summary": {"de": "Übersicht", "en": "Overview"},
    "sheet_segments": {"de": "Segmente", "en": "Price segments"},
    "sheet_sizes": {"de": "Nach Gebindegröße", "en": "By container size"},
    "sheet_retailers": {"de": "Nach Händler", "en": "By retailer"},
    "sheet_cheapest": {"de": "Günstigste drei je Händler",
                       "en": "Cheapest three per store"},
    "sheet_label": {"de": "Eigenmarke oder nicht",
                    "en": "Private label or not"},
    "sheet_formats": {"de": "Formatvergleich", "en": "Format comparison"},
    "sheet_pet": {"de": "PET-Prüfung", "en": "PET evidence"},
    "sheet_unavailable": {"de": "Nicht erfasst", "en": "Not covered"},
    "sheet_data": {"de": "Alle Daten", "en": "In-scope data"},
    "sheet_all": {"de": "Gesamtsortiment", "en": "Full catalogue"},
    "sheet_method": {"de": "Methodik", "en": "Method"},

    # --------------------------------------------------------------- summary
    "summary_title": {
        "de": "Deutscher Weinmarkt — PET & Bag-in-Box",
        "en": "German Wine Market — PET & Bag-in-Box"},
    "summary_sub": {
        "de": ("Preispunkte je Liter, erhoben {stamp}. Alle Preise in EUR, "
               "inkl. MwSt., ohne Pfand sofern nicht anders vermerkt."),
        "en": ("Price points per litre, collected {stamp}. All prices in EUR, "
               "VAT included, deposit excluded unless stated otherwise.")},
    "summary_headline": {
        "de": ("Kernbefund: Bag-in-Box ist in Deutschland ein etabliertes "
               "Weinformat mit klarer Preisstruktur. Wein in PET-Flaschen wird "
               "im deutschen Lebensmittel- und Fachhandel nicht verkauft — "
               "siehe Blatt „PET-Prüfung“."),
        "en": ("Headline: bag-in-box is an established German wine format with "
               "a settled price structure. Wine in PET bottles is not sold in "
               "German grocery or specialist retail at all — see the "
               "'PET evidence' sheet.")},
    "h_metric": {"de": "Kennzahl", "en": "Measure"},
    "h_value": {"de": "Wert", "en": "Value"},
    "h_note": {"de": "Erläuterung", "en": "Note"},
    "fact_total": {"de": "Erfasste Weinangebote gesamt",
                   "en": "Wine listings collected"},
    "fact_total_note": {"de": "alle Weine aller Quellen, auch Glasflaschen",
                        "en": "every wine from every source, glass included"},
    "fact_scope": {"de": "davon PET oder Bag-in-Box",
                   "en": "of those, PET or bag-in-box"},
    "fact_scope_note": {"de": "{pct} des erfassten Sortiments",
                        "en": "{pct} of the collected range"},
    "fact_bib": {"de": "davon Bag-in-Box", "en": "of those, bag-in-box"},
    "fact_pet": {"de": "davon PET-Flasche", "en": "of those, PET bottle"},
    "fact_pet_note": {"de": "kein einziges Angebot gefunden",
                      "en": "not one listing found"},
    "fact_still": {"de": "Stillwein-Angebote in der Auswertung",
                   "en": "still-wine listings in the figures"},
    "fact_still_note": {"de": "ohne Glühwein, Sangria und Schaumwein",
                        "en": "excludes mulled wine, sangria and sparkling"},
    "h_price_point": {"de": "Preispunkt (EUR/Liter)",
                      "en": "Price point (EUR/litre)"},
    "h_offers": {"de": "Angebote", "en": "Listings"},
    "h_min": {"de": "Minimum", "en": "Minimum"},
    "h_median": {"de": "Median", "en": "Median"},
    "h_mean": {"de": "Mittelwert", "en": "Mean"},
    "h_max": {"de": "Maximum", "en": "Maximum"},
    "row_all_scope": {"de": "Alle Stillweine PET/BiB",
                      "en": "All still wines, PET/BiB"},
    "row_bib_only": {"de": "nur Bag-in-Box", "en": "bag-in-box only"},
    "row_three_only": {"de": "nur 3-Liter-Bag-in-Box",
                       "en": "3-litre bag-in-box only"},
    "h_bottle_equiv": {"de": "3-Liter-Box umgerechnet auf 0,75 l",
                       "en": "3-litre box priced per 0.75 l"},
    "row_bottle_equiv": {"de": "Flaschenäquivalent", "en": "Bottle equivalent"},
    "note_pfand": {
        "de": ("Pfand: Bag-in-Box ist nach § 31 Abs. 4 VerpackG als ökologisch "
               "vorteilhafte Einweggetränkeverpackung pfandfrei. Auf "
               "PET-Flaschen von 0,1 bis 3,0 Litern lägen 0,25 € Einwegpfand — "
               "seit dem 1.1.2022 unabhängig vom Inhalt und damit auch auf "
               "Wein. Für die erhobenen Bag-in-Box-Angebote sind Regalpreis und "
               "Kassenpreis deshalb identisch."),
        "en": ("Deposit (Pfand): bag-in-box is exempt under VerpackG §31(4) as "
               "an 'ecologically advantageous' single-use beverage container. A "
               "PET bottle of 0.1 to 3.0 litres would carry the 0.25 EUR "
               "single-use deposit — since 1 January 2022 regardless of "
               "contents, which is what would bring wine into the scheme. For "
               "every bag-in-box listing here, shelf price and till price are "
               "therefore the same.")},
    "note_metro": {
        "de": ("METRO-Preise sind Netto-Handelspreise (B2B, ohne MwSt.) und "
               "werden in den Verbraucher-Kennzahlen oben nicht mitgerechnet. "
               "Sie stehen separat auf dem Blatt „Nach Händler“."),
        "en": ("METRO prices are net trade prices (B2B, excluding VAT) and are "
               "left out of the consumer figures above. They appear separately "
               "on the 'By retailer' sheet.")},

    # -------------------------------------------------------------- segments
    "segments_title": {"de": "Preissegmente der 3-Liter-Bag-in-Box",
                       "en": "Price segments of the 3-litre bag-in-box"},
    "segments_sub": {
        "de": "Das Standardgebinde, über alle Verbraucherquellen.",
        "en": "The standard container, across all consumer sources."},
    "h_segment": {"de": "Segment", "en": "Segment"},
    "h_price_band": {"de": "Preisspanne (3 l)", "en": "Price band (3 l)"},
    "h_share": {"de": "Anteil", "en": "Share"},
    "h_typical": {"de": "Typisch", "en": "Typically"},
    "seg_entry": {"de": "Einstieg", "en": "Entry"},
    "seg_mid": {"de": "Mittelfeld", "en": "Mid-range"},
    "seg_premium": {"de": "Premium", "en": "Premium"},
    "seg_top": {"de": "Hochpreis", "en": "Top end"},
    "seg_entry_note": {"de": "Eigenmarken der Discounter und Hausweine",
                       "en": "discounter own-brands and house wines"},
    "seg_mid_note": {"de": "Marken wie Grand Sud, Maybach, Mertes",
                     "en": "brands such as Grand Sud, Maybach, Mertes"},
    "seg_premium_note": {"de": "Sortenweine, Fachhandelsmarken",
                         "en": "varietal wines, specialist-trade brands"},
    "seg_top_note": {"de": "Winzer- und Bioweine, Markenrosé",
                     "en": "grower and organic wines, branded rosé"},
    "band_from": {"de": "ab {low} €", "en": "from {low} €"},
    "band_under": {"de": "bis {high} €", "en": "under {high} €"},
    "segments_note": {
        "de": ("Der Einstiegspreis für 3 Liter Wein in Deutschland liegt bei "
               "4,99 € (1,66 €/l) — bei Lidl und bei Globus. Das entspricht "
               "1,25 € je 0,75-l-Flasche und ist der Boden des Marktes."),
        "en": ("The entry price for 3 litres of wine in Germany is 4.99 € "
               "(1.66 €/l), at both Lidl and Globus. That is 1.25 € per "
               "0.75-litre-bottle equivalent, and it is the floor of the "
               "market.")},
    "h_colour_three": {"de": "Farbe (3-l-Box)", "en": "Colour (3 l box)"},
    "h_origin_three": {"de": "Herkunft (3-l-Box)", "en": "Origin (3 l box)"},

    # ----------------------------------------------------------------- sizes
    "sizes_title": {"de": "Preispunkt nach Gebindegröße",
                    "en": "Price point by container size"},
    "sizes_sub": {
        "de": "Nur Stillwein, Verbraucherpreise (ohne METRO-Nettopreise).",
        "en": "Still wine only, consumer prices (METRO net prices excluded)."},
    "h_container": {"de": "Gebinde", "en": "Container"},
    "h_packaging": {"de": "Verpackung", "en": "Packaging"},
    "h_price_min": {"de": "Preis min", "en": "Price min"},
    "h_price_med": {"de": "Preis Median", "en": "Price median"},
    "h_price_max": {"de": "Preis max", "en": "Price max"},
    "h_litre_min": {"de": "EUR/l min", "en": "EUR/l min"},
    "h_litre_med": {"de": "EUR/l Median", "en": "EUR/l median"},
    "h_litre_max": {"de": "EUR/l max", "en": "EUR/l max"},
    "not_stated": {"de": "ohne Angabe", "en": "not stated"},
    "sizes_note": {
        "de": ("Die 3-Liter-Box ist das Standardgebinde und stellt die große "
               "Mehrheit aller erfassten Bag-in-Box-Angebote. Der Preis je "
               "Liter fällt mit der Gebindegröße: 5-Liter-Gebinde liegen "
               "darunter, 1,5- und 2,25-Liter-Gebinde deutlich darüber."),
        "en": ("The 3-litre box is the standard container and accounts for the "
               "large majority of bag-in-box listings collected. Price per "
               "litre falls as the container grows: 5-litre sizes sit below it, "
               "1.5- and 2.25-litre sizes well above.")},
    "h_multipacks": {"de": "Mehrfachpakete (getrennt ausgewiesen)",
                     "en": "Multi-packs (shown separately)"},
    "multipack_note": {
        "de": ("Pakete aus mehreren Boxen. Wo der Händler nur die Gesamtmenge "
               "nennt (etwa „BiB-Paket … 9 L“) und seine Stückzahl in "
               "Flaschenäquivalenten zählt, bleibt die Einzelbox-Größe offen; "
               "die Menge wird dann als Ganzes geführt. Der Preis je Liter ist "
               "in beiden Fällen korrekt."),
        "en": ("Packs of several boxes. Where the retailer states only the "
               "total volume (\"BiB pack … 9 L\") and counts units in "
               "bottle-equivalents, the size of a single box is left unclaimed "
               "and the pack is recorded whole. Price per litre is correct "
               "either way.")},

    # ------------------------------------------------------------- retailers
    "retailers_title": {"de": "Preispunkt nach Händler und Vertriebskanal",
                        "en": "Price point by retailer and channel"},
    "retailers_sub": {"de": "Alle PET/Bag-in-Box-Angebote je Quelle.",
                      "en": "All PET/bag-in-box listings, by source."},
    "h_retailer": {"de": "Händler", "en": "Retailer"},
    "h_channel": {"de": "Kanal", "en": "Channel"},
    "h_price_basis": {"de": "Preisbasis", "en": "Price basis"},
    "basis_net": {"de": "netto (B2B)", "en": "net (B2B)"},
    "basis_gross": {"de": "brutto", "en": "gross"},
    "retailers_note": {
        "de": ("Die Preisbasis trennt die Zeilen: METRO ist Cash & Carry und "
               "zeigt Nettopreise ohne MwSt., die rund 19 % unter einem "
               "vergleichbaren Verbraucherpreis liegen. Kaufland und REWE "
               "sperren Rechenzentrums-Adressen aus (Blatt „Nicht erfasst“)."),
        "en": ("The price basis separates the rows: METRO is cash & carry and "
               "shows net prices excluding VAT, roughly 19% below a comparable "
               "consumer price. Kaufland and REWE block datacentre addresses "
               "(see the 'Not covered' sheet).")},

    # --------------------------------------------------------------- formats
    "formats_title": {"de": "Bag-in-Box im Vergleich zu den anderen Gebinden",
                      "en": "Bag-in-box against the other containers"},
    "formats_sub": {
        "de": "Alle erfassten Weine nach Verpackungsart, Verbraucherpreise.",
        "en": "Every collected wine by packaging type, consumer prices."},
    "h_deposit": {"de": "Pfand", "en": "Deposit"},
    "deposit_free": {"de": "pfandfrei", "en": "no deposit"},
    "deposit_mixed": {"de": "gemischt/unbekannt", "en": "mixed/unknown"},
    "formats_note": {
        "de": ("„unbekannt“ heißt, dass der Händler die Verpackung nicht nennt. "
               "Das ist bei der gewöhnlichen 0,75-l-Flasche der Normalfall und "
               "wird hier nicht zu „Glas“ umgedeutet — die Zeile ist als "
               "Vergleichsmaßstab gedacht, nicht als Aussage über das Material. "
               "Das Maximum der Glasflaschen (1.600 €/l) ist echt: Lidl führt "
               "Château Lafite Rothschild zu 1.200 € je 0,75 l. Für den "
               "Formatvergleich zählt der Median, nicht der Rand."),
        "en": ("'not stated' means the retailer does not name the container. "
               "That is the normal case for an ordinary 0.75 l bottle, and it "
               "is not reinterpreted as glass here — the row is a yardstick, "
               "not a claim about the material. The glass maximum (1,600 €/l) "
               "is real: Lidl lists Château Lafite Rothschild at 1,200 € per "
               "0.75 l. For comparing formats the median is what counts, not "
               "the tail.")},
    "h_direct_compare": {"de": "Direkter Vergleich (Einstiegsformate)",
                         "en": "Head to head (entry formats)"},
    "cmp_box": {"de": "3-l-Bag-in-Box", "en": "3 l bag-in-box"},
    "cmp_litre": {"de": "1-l-Flasche (Literwein)",
                  "en": "1 l bottle (German 'Literflasche')"},
    "cmp_carton": {"de": "Getränkekarton", "en": "Carton (Tetra Pak)"},

    # -------------------------------------------------------------- cheapest
    "cheapest_title": {
        "de": "Die drei günstigsten Bag-in-Box je Händler",
        "en": "The three cheapest bag-in-box wines at each store"},
    "cheapest_sub": {
        "de": ("Gereiht nach EUR je Liter. Nur Stillwein in einzelnen Boxen — "
               "was ausgeschlossen wurde, steht in der zweiten Tabelle."),
        "en": ("Ranked by EUR per litre. Still wine in single boxes only — what "
               "was excluded is listed in the second table.")},
    "cheapest_intro": {
        "de": ("Drei Dinge würden die Reihung verfälschen und sind deshalb "
               "ausgenommen. Glühwein kostet je Liter rund ein Drittel des "
               "Weins daneben und stünde sonst bei zwei Händlern auf Platz "
               "eins. Mehrfachpakete haben einen korrekten Literpreis, sind "
               "aber nichts, was man einzeln kaufen kann. Und METRO ist Cash & "
               "Carry mit Nettopreisen ohne MwSt. — die Zeilen bleiben "
               "enthalten, sind aber als netto gekennzeichnet und nicht direkt "
               "mit den übrigen vergleichbar."),
        "en": ("Three things would distort the ranking and are held out. Mulled "
               "wine runs at about a third of the litre price of the wine "
               "beside it and would otherwise take first place at two stores. "
               "Multi-packs have a correct price per litre but are not "
               "something you can buy singly. And METRO is cash & carry, "
               "quoting net prices excluding VAT — its rows stay in, marked as "
               "net, but they are not directly comparable with the rest.")},
    "h_rank": {"de": "Platz", "en": "Rank"},
    "h_wine": {"de": "Wein", "en": "Wine"},
    "h_size": {"de": "Gebinde", "en": "Size"},
    "h_price": {"de": "Preis", "en": "Price"},
    "h_per_litre": {"de": "EUR/Liter", "en": "EUR/litre"},
    "h_per_bottle": {"de": "je 0,75 l", "en": "per 0.75 l"},
    "h_colour": {"de": "Farbe", "en": "Colour"},
    "h_origin": {"de": "Herkunft", "en": "Origin"},
    "h_link": {"de": "Link", "en": "Link"},
    "h_excluded": {"de": "Ausgeschlossene günstigere Angebote",
                   "en": "Cheaper listings held out of the ranking"},
    "h_why": {"de": "Grund", "en": "Reason"},
    "excl_gluehwein": {"de": "Glühwein, nicht Stillwein",
                       "en": "mulled wine, not still wine"},
    "excl_sangria": {"de": "Sangria, nicht Stillwein",
                     "en": "sangria, not still wine"},
    "excl_sparkling": {"de": "Schaumwein, nicht Stillwein",
                       "en": "sparkling, not still wine"},
    "excl_dessert": {"de": "Süßwein, andere Preisskala",
                     "en": "dessert wine, different price scale"},
    "excl_pack": {"de": "Mehrfachpaket, nicht einzeln erhältlich",
                  "en": "multi-pack, not sold as a single box"},
    "cheapest_note": {
        "de": ("Der Einstiegspreis ist bei Lidl und Globus mit 4,99 € für 3 "
               "Liter identisch — 1,66 €/l, also 1,25 € je 0,75-l-Flasche. "
               "Beide Discounter und beide Supermärkte liegen damit unter dem "
               "günstigsten Fachhändler. Bemerkenswert ist die Spreizung "
               "innerhalb des Discountkanals: Netto beginnt erst bei 3,83 €/l, "
               "mehr als das Doppelte von Lidl, weil Netto keine Eigenmarke in "
               "der Box führt, sondern nur Marken wie Maybach und Bree."),
        "en": ("The entry price is identical at Lidl and Globus — 4.99 € for 3 "
               "litres, or 1.66 €/l, which is 1.25 € per 0.75-litre-bottle "
               "equivalent. Both discounters and both supermarkets undercut the "
               "cheapest specialist. The spread inside the discount channel is "
               "the striking part: Netto starts at 3.83 €/l, more than twice "
               "Lidl, because it carries no own-brand box at all — only brands "
               "like Maybach and Bree.")},
    "cheapest_none": {"de": "kein Angebot in dieser Auswahl",
                      "en": "no listing in this selection"},

    # ----------------------------------------------------------- own label
    "h_private_label": {"de": "Eigenmarke?", "en": "Private label?"},
    "h_brand_owner": {"de": "Markeninhaber", "en": "Brand owner"},
    "h_operator": {"de": "Verantwortl. Lebensmittelunternehmer",
                   "en": "Responsible food business operator"},
    "h_basis": {"de": "Beleg", "en": "Basis"},
    "h_sources": {"de": "Quellen", "en": "Sources"},
    "yes": {"de": "ja", "en": "yes"},
    "no": {"de": "nein", "en": "no"},
    "unresolved": {"de": "nicht belegbar", "en": "not established"},
    "label_title": {"de": "Eigenmarke oder Herstellermarke?",
                    "en": "Private label or producer brand?"},
    "label_sub": {
        "de": ("Für jeden der drei günstigsten Bag-in-Box je Händler, mit "
               "verlinkter Quelle für jede Aussage."),
        "en": ("For each of the three cheapest bag-in-box wines per store, "
               "with a linked source for every claim.")},
    "label_method": {
        "de": ("Drei Belegarten, in absteigender Stärke. (1) Wird dasselbe "
               "Produkt von unabhängigen Händlern verkauft, ist es keine "
               "Eigenmarke — eine Eigenmarke ist definitionsgemäß exklusiv. "
               "(2) Führt der Abfüller die Marke auf der eigenen Website als "
               "seine, ist das seine eigene Aussage. (3) Der verantwortliche "
               "Lebensmittelunternehmer nach Art. 8/9 LMIV, den der Händler im "
               "Fernabsatz nach Art. 14 LMIV vor dem Kauf nennen muss.\n\n"
               "Wichtig zu Punkt (3): Eine genannte Weinkellerei schließt eine "
               "Eigenmarke gerade nicht aus. Peter Mertes, Zimmermann-Graeff & "
               "Müller und Einig-Zenzen füllen sowohl eigene Marken als auch "
               "Handelsmarken ab und stehen in beiden Fällen dort. Das Feld "
               "beantwortet „wer haftet“, nicht „wem gehört die Marke“."),
        "en": ("Three kinds of evidence, strongest first. (1) If unrelated "
               "retailers sell the identical product it is not a private "
               "label — a private label is exclusive by definition. (2) If the "
               "bottler presents the brand as its own on its own site, that is "
               "the producer asserting ownership. (3) The responsible food "
               "business operator under LMIV Art. 8/9, which a distance seller "
               "must show before purchase under Art. 14.\n\n"
               "A caution on (3): naming a winery does not rule out a private "
               "label. Peter Mertes, Zimmermann-Graeff & Müller and "
               "Einig-Zenzen fill both their own brands and retailers' labels "
               "and appear as operator either way. The field answers who is "
               "liable, not whose brand it is.")},
    "label_finding": {
        "de": ("Ergebnis: Von 27 geprüften Angeboten sind sechs Eigenmarken — "
               "die drei Lidl-Weine und die drei Schäpers-Hausweine. Fünfzehn "
               "sind fremde Marken, sechs ließen sich nicht belegen. "
               "Bemerkenswert: Die beiden günstigsten Händler kommen auf "
               "entgegengesetztem Weg dorthin. Lidl führt die eigene Linie und "
               "lässt sie von drei verschiedenen Kellereien abfüllen; Netto "
               "führt in der Box gar keine Eigenmarke und liegt mit reinen "
               "Herstellermarken beim 2,3-fachen Preis."),
        "en": ("Result: of 27 listings checked, six are private labels — the "
               "three Lidl wines and the three Schäpers house wines. Fifteen "
               "are other companies' brands and six could not be established. "
               "The two ends of the price range get there by opposite routes: "
               "Lidl owns its line and has three different wineries fill it, "
               "while Netto carries no own-label box at all and sits at 2.3× "
               "the price on producer brands alone.")},

    # ------------------------------------------------------------------- PET
    "pet_title": {"de": "PET-Flaschen: gesuchte Belege",
                  "en": "PET bottles: the evidence for a nil finding"},
    "pet_sub": {"de": "Die Hälfte der Fragestellung. Ergebnis: kein Angebot im Handel.",
                "en": "Half the question asked. Answer: no retail listing exists."},
    "pet_intro": {
        "de": ("Wein in PET-Flaschen wurde in keinem der erreichten deutschen "
               "Sortimente gefunden. Weil ein Nullbefund aus einem Filter "
               "heraus wenig wert ist, steht er hier auf zwei unabhängigen "
               "Beinen: dem vollständig durchgesehenen Sortiment jeder Quelle, "
               "und einer gezielten Suche mit den Wörtern, die ein deutscher "
               "Händler benutzen würde."),
        "en": ("No wine in a PET bottle was found in any German range reached. "
               "A nil result produced by a filter is a weak claim, so it rests "
               "on two independent legs here: every listing of every source "
               "classified one by one, and a targeted search using the words a "
               "German retailer would use.")},
    "h_census": {"de": "Vollständig durchgesehenes Sortiment",
                 "en": "Full catalogue examined"},
    "h_checked": {"de": "Weine geprüft", "en": "Wines checked"},
    "h_of_pet": {"de": "davon PET", "en": "of those PET"},
    "h_of_bib": {"de": "davon Bag-in-Box", "en": "of those bag-in-box"},
    "row_total": {"de": "Gesamt", "en": "Total"},
    "h_search": {"de": "Gezielte Suche", "en": "Targeted search"},
    "h_query": {"de": "Suchbegriff", "en": "Query"},
    "h_hits": {"de": "Treffer", "en": "Hits"},
    "h_pet_wine": {"de": "davon PET-Wein", "en": "of those PET wine"},
    "h_example": {"de": "Beispieltreffer", "en": "Example hit"},
    "pet_search_note": {
        "de": ("Die Treffer, die tatsächlich PET waren, waren Himbeersirup und "
               "Mineralwasser — kein Wein."),
        "en": ("The hits that genuinely were PET turned out to be raspberry "
               "syrup and mineral water — no wine.")},
    "h_point": {"de": "Punkt", "en": "Point"},
    "h_finding": {"de": "Befund", "en": "Finding"},
    "pet_law": {"de": "Rechtslage", "en": "The law"},
    "pet_law_note": {
        "de": ("Seit 1.1.2022 gilt das Einwegpfand von 0,25 € für alle "
               "Einweg-Kunststoffgetränkeflaschen von 0,1 bis 3,0 l unabhängig "
               "vom Inhalt — Wein in PET wäre also pfandpflichtig, Bag-in-Box "
               "nicht."),
        "en": ("Since 1 January 2022 the 0.25 EUR single-use deposit applies to "
               "every single-use plastic beverage bottle of 0.1 to 3.0 l "
               "regardless of contents — so wine in PET would carry it, and "
               "bag-in-box would not.")},
    "pet_supply": {"de": "Angebotsseite", "en": "Supply side"},
    "pet_supply_note": {
        "de": ("PET-Weinflaschen (250 ml, 750 ml) werden in Deutschland als "
               "Leergut an Winzer und Caterer verkauft, etwa über Flaschenland "
               "und Plastikflaschenshop — nicht befüllt an Endkunden."),
        "en": ("PET wine bottles (250 ml, 750 ml) are sold in Germany as empty "
               "packaging to wineries and caterers — Flaschenland, "
               "Plastikflaschenshop and the like — never filled to consumers.")},
    "pet_place": {"de": "Einordnung", "en": "Where it sits"},
    "pet_place_note": {
        "de": ("Das große Gebinde ist in Deutschland die Bag-in-Box, das kleine "
               "die Glasflasche. PET besetzt dazwischen keine Position im "
               "Regal."),
        "en": ("In Germany the large container is the bag-in-box and the small "
               "one is glass. PET holds no shelf position between them.")},
    "pet_where": {"de": "Wo PET auftauchen könnte", "en": "Where PET might appear"},
    "pet_where_note": {
        "de": ("Festival- und Bordgastronomie sowie Eigenabfüllungen; beides "
               "ist kein Handelssortiment und daher hier nicht erfasst."),
        "en": ("Festival and on-board catering, and winery self-bottling. "
               "Neither is a retail range, so neither is covered here.")},

    # ----------------------------------------------------------- unavailable
    "unavailable_title": {"de": "Geprüfte, aber nicht erfasste Händler",
                          "en": "Retailers checked but not covered"},
    "unavailable_sub": {
        "de": ("Jede Kette der Wikipedia-Liste deutscher Supermarktketten wurde "
               "einzeln geprüft. Damit „nicht im Datensatz“ nicht mit „führt "
               "das Format nicht“ verwechselt wird."),
        "en": ("Every chain on Wikipedia's list of German supermarket chains "
               "was checked individually — so that 'absent from the data' is "
               "not read as 'does not stock the format'.")},
    "unavailable_note": {
        "de": ("Der Befund ist nicht in erster Linie Bot-Abwehr, sondern die "
               "Struktur des deutschen Lebensmittelhandels: die meisten Ketten "
               "betreiben überhaupt keinen Online-Katalog mit Preisen, sondern "
               "Marktfinder und Wochenprospekt. Der Preis existiert nur am "
               "Regal. Besonders relevant für diese Studie sind Getränke "
               "Hoffmann, trinkgut und Fristo: dort verkauft sich Bag-in-Box am "
               "stärksten, und dort steht kein einziger Preis im Netz."),
        "en": ("The reason is not mainly bot protection but the shape of German "
               "grocery retail: most chains run no online catalogue with prices "
               "at all, only a store finder and a weekly leaflet. The price "
               "exists on the shelf and nowhere else. The sharpest case for "
               "this study is Getränke Hoffmann, trinkgut and Fristo — the "
               "beverage chains where bag-in-box sells hardest, and where not "
               "one price is published online.")},

    # ------------------------------------------------------------------ data
    "data_title": {"de": "PET- und Bag-in-Box-Angebote — Rohdaten",
                   "en": "PET and bag-in-box listings — raw data"},
    "all_title": {"de": "Gesamtes erfasstes Weinsortiment",
                  "en": "Full collected wine range"},
    "data_sub": {
        "de": ("Eine Zeile je Angebot. Leere Felder heißen „vom Händler nicht "
               "angegeben“ und sind nicht geschätzt."),
        "en": ("One row per listing. An empty cell means the retailer did not "
               "state it; nothing is estimated.")},

    # ---------------------------------------------------------------- method
    "method_title": {"de": "Methodik und Belastbarkeit",
                     "en": "Method and how far it can be trusted"},
    "method_sub": {"de": "Erhebung {stamp}", "en": "Collected {stamp}"},
    "h_source": {"de": "Quelle", "en": "Source"},
    "h_wines_collected": {"de": "Erfasste Weine", "en": "Wines collected"},
    "h_access": {"de": "Zugang", "en": "Access"},
    "h_explanation": {"de": "Erläuterung", "en": "Explanation"},
    "m_scope": {"de": "Auswahlkriterium", "en": "Inclusion rule"},
    "m_scope_note": {
        "de": ("Aufgenommen wird ein Angebot nur, wenn die Verpackung aus "
               "Titel, Beschreibung, Kategorie oder Bildtext als PET-Flasche "
               "oder Bag-in-Box lesbar ist. Was nichts sagt, bleibt „unbekannt“ "
               "und fließt nicht in die Kennzahlen ein."),
        "en": ("A listing is included only where the container can be read as "
               "PET or bag-in-box from the title, description, category or "
               "image alt text. Anything that says nothing stays 'not stated' "
               "and is left out of the figures.")},
    "m_three_litre": {"de": "Die Drei-Liter-Regel", "en": "The three-litre rule"},
    "m_three_litre_note": {
        "de": ("Ab drei Litern gilt das Gebinde als Bag-in-Box, wenn nichts "
               "anderes dasteht. Das ist gemessen, nicht angenommen: von 216 "
               "Drei-Liter-Weinen nennen 191 die Bag-in-Box ausdrücklich, 24 "
               "nennen gar kein Gebinde, und genau einer ist eine Flasche — "
               "eine Prosecco-Jeroboam bei METRO, die „3 l Flasche“ schreibt "
               "und von der Glasregel vorher erfasst wird. Bei fünf Litern sind "
               "es 28 von 28. Unter drei Litern greift die Regel nicht: "
               "Zwei-Liter-Wein ist in Deutschland regelmäßig Glas."),
        "en": ("At three litres and above the container is taken to be a "
               "bag-in-box unless the listing says otherwise. That is measured, "
               "not assumed: of 216 three-litre wines, 191 name the bag-in-box "
               "outright, 24 name no container at all, and exactly one is a "
               "bottle — a Prosecco Jeroboam at METRO that writes '3 l Flasche' "
               "and is caught by the glass rule first. At five litres it is 28 "
               "of 28. The rule stops at three: two-litre German wine is "
               "routinely glass.")},
    "m_per_litre": {"de": "Preis je Liter", "en": "Price per litre"},
    "m_per_litre_note": {
        "de": ("Wird aus eigenem Preis und eigener Gebindegröße gerechnet, "
               "nicht vom Händler übernommen — Händler rechnen den Grundpreis "
               "unterschiedlich (mit oder ohne Pfand). Der Grundpreis des "
               "Händlers steht als unit_price daneben und dient als Gegenprobe."),
        "en": ("Computed from our own price and container size, not taken from "
               "the retailer — retailers differ on whether their Grundpreis "
               "(unit price) includes the deposit. Theirs is kept alongside as "
               "unit_price and used as the cross-check.")},
    "m_crosscheck": {"de": "Gegenprobe", "en": "Cross-check"},
    "m_crosscheck_note": {
        "de": ("Jede Zeile mit beiden Werten wird verglichen. In der aktuellen "
               "Erhebung stimmen alle {checked} vergleichbaren Zeilen überein. "
               "Der Test hat fünf echte Fehler gefunden, die sonst unsichtbar "
               "geblieben wären — darunter Globus, das einen reduzierten Preis "
               "als „3,49 € 2,49 €“ in einem Element rendert, und NORMA, das "
               "content=\"4.2\" ausliefert, was der Parser als 4 las."),
        "en": ("Every row carrying both figures is compared. In this run all "
               "{checked} comparable rows agree. The test found five real "
               "faults that were otherwise invisible — among them Globus, which "
               "renders a discounted price as '3,49 € 2,49 €' inside a single "
               "element, and NORMA, which publishes content=\"4.2\" that the "
               "price parser read as 4.")},
    "m_packs": {"de": "Gebinde vs. Packung", "en": "Container vs. pack"},
    "m_packs_note": {
        "de": ("Ein 6er-Karton mit 0,75-l-Flaschen meldet 4,5 Liter. Ohne "
               "Korrektur wäre er als Großgebinde in die Auswertung geraten; "
               "Packungsgröße und Stückzahl werden deshalb getrennt geführt."),
        "en": ("A six-bottle case of 0.75 l reports 4.5 litres. Left alone it "
               "would enter the figures as a large format, so container size "
               "and pack count are kept apart.")},
    "m_exclusions": {"de": "Abgrenzung", "en": "Exclusions"},
    "m_exclusions_note": {
        "de": ("Glühwein, Sangria, Schaumwein und Süßwein sind erfasst, aber "
               "aus den Stillwein-Kennzahlen ausgenommen: sie liegen je Liter "
               "auf einer anderen Skala und würden den Preispunkt verzerren."),
        "en": ("Mulled wine, sangria, sparkling and dessert wine are collected "
               "but held out of the still-wine figures: they sit on a different "
               "per-litre scale and would distort the price point.")},
    "m_limits": {"de": "Grenzen", "en": "Limits"},
    "m_limits_note": {
        "de": ("Die Erhebung ist eine Momentaufnahme des Online-Sortiments. Sie "
               "erfasst weder Aktionsware im Prospekt noch das Regal der "
               "Getränkemärkte. Von den großen Filialisten sind Globus, Lidl, "
               "NORMA, Netto, Combi und EDEKA enthalten; Kaufland und REWE "
               "fehlen."),
        "en": ("This is a snapshot of what is online. It covers neither leaflet "
               "promotions nor the beverage-store shelf. Of the large chains it "
               "includes Globus, Lidl, NORMA, Netto, Combi and EDEKA; Kaufland "
               "and REWE are missing.")},
}


class Texts:
    """String lookup for one language, with ``{}`` formatting."""

    def __init__(self, language: str = "de"):
        if language not in LANGUAGES:
            raise ValueError(f"unknown language {language!r}; "
                             f"known: {', '.join(LANGUAGES)}")
        self.language = language

    def __call__(self, key: str, **kwargs) -> str:
        try:
            template = STRINGS[key][self.language]
        except KeyError:
            raise KeyError(f"no {self.language} string for {key!r}") from None
        return template.format(**kwargs) if kwargs else template

    # -- value vocabularies -----------------------------------------------
    def packaging(self, value: str) -> str:
        return PACKAGING_LABELS[self.language].get(value, value)

    def channel(self, value: str) -> str:
        return CHANNEL_LABELS[self.language].get(value, value)

    def colour(self, value: str) -> str:
        return COLOUR_LABELS[self.language].get(value, value)

    def country(self, value: str) -> str:
        """Country names, which the parser records in German."""
        return COUNTRY_LABELS.get(self.language, {}).get(value, value)

    def reason(self, value: str) -> str:
        return REASON_HEADINGS[self.language].get(value, value)

    def basis(self, price_basis: str) -> str:
        return self("basis_net" if price_basis == "net" else "basis_gross")
