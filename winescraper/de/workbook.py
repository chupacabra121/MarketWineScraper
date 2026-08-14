"""The study's Excel deliverable.

Sheet order follows how the question gets answered rather than how the data was
collected: the headline price points first, then the cuts that explain them
(format, retailer, colour, origin), then the two sheets that say what the
numbers do *not* cover — the PET probe and the retailers that could not be
reached — and only then the raw rows.

Every figure on every summary sheet is computed from the rows on ``Alle Daten``,
so the workbook can be checked against itself.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import packaging as pkg
from .model import EXPORT_COLUMNS, Listing
from .sources import UNAVAILABLE

# --- house style -------------------------------------------------------------
INK = "1F2933"
ACCENT = "7A2E3C"          # wine red, used for headers
ACCENT_SOFT = "F2E8EA"
RULE = "D8DEE4"
MUTED = "6B7785"

TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=ACCENT)
SUB_FONT = Font(name="Calibri", size=10, color=MUTED, italic=True)
HEAD_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=10, color=INK)
STRONG = Font(name="Calibri", size=10, bold=True, color=INK)
NOTE_FONT = Font(name="Calibri", size=9, color=MUTED)

HEAD_FILL = PatternFill("solid", fgColor=ACCENT)
BAND_FILL = PatternFill("solid", fgColor=ACCENT_SOFT)
THIN = Side(style="thin", color=RULE)
CELL_BORDER = Border(bottom=THIN)

EUR = '#,##0.00\\ "€"'
EUR_L = '#,##0.00\\ "€/l"'
NUM2 = "0.00"
PCT = "0%"


def _autosize(sheet: Worksheet, widths: Sequence[int]) -> None:
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def _title(sheet: Worksheet, title: str, subtitle: str = "", *, span: int = 8) -> int:
    """Write the sheet's title block and return the next free row."""
    sheet["A1"] = title
    sheet["A1"].font = TITLE_FONT
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    row = 2
    if subtitle:
        sheet.cell(row=2, column=1, value=subtitle).font = SUB_FONT
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        row = 3
    sheet.row_dimensions[1].height = 24
    return row + 1


def _table(sheet: Worksheet, start_row: int, headers: Sequence[str],
           rows: Iterable[Sequence[Any]], formats: dict[int, str] | None = None,
           *, band: bool = True) -> int:
    """Write a header row and body, and return the row after the table."""
    formats = formats or {}
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=start_row, column=column, value=header)
        cell.font = HEAD_FONT
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    sheet.row_dimensions[start_row].height = 28

    row_number = start_row
    for offset, values in enumerate(rows):
        row_number = start_row + 1 + offset
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_number, column=column, value=value)
            cell.font = BODY_FONT
            cell.border = CELL_BORDER
            if band and offset % 2 == 1:
                cell.fill = BAND_FILL
            if column in formats:
                cell.number_format = formats[column]
    return row_number + 2


def _note(sheet: Worksheet, row: int, text: str, *, span: int = 8) -> int:
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = NOTE_FONT
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    sheet.row_dimensions[row].height = max(14, 13 * (len(text) // 110 + 1))
    return row + 2


# --- statistics --------------------------------------------------------------
def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 2),
        "median": round(statistics.median(ordered), 2),
        "mean": round(statistics.fmean(ordered), 2),
        "max": round(ordered[-1], 2),
    }


def _by(listings: list[Listing], key: Callable[[Listing], Any]) -> dict[Any, list[Listing]]:
    grouped: dict[Any, list[Listing]] = {}
    for listing in listings:
        grouped.setdefault(key(listing), []).append(listing)
    return grouped


def _litre_prices(listings: Iterable[Listing]) -> list[float]:
    return [x.price_per_litre for x in listings if x.price_per_litre is not None]


# --- sheets ------------------------------------------------------------------
def _sheet_summary(book: Workbook, scope: list[Listing], everything: list[Listing],
                   stamp: str) -> None:
    sheet = book.create_sheet("Übersicht")
    row = _title(sheet, "Deutscher Weinmarkt — PET & Bag-in-Box",
                 f"Preispunkte je Liter, erhoben {stamp}. "
                 "Alle Preise in EUR, inkl. MwSt., ohne Pfand sofern nicht anders vermerkt.")

    consumer = [x for x in scope if x.price_basis == "gross"]
    still = [x for x in consumer if x.product_type == "still"]

    row = _note(sheet, row,
                "Kernbefund: Bag-in-Box ist in Deutschland ein etabliertes "
                "Weinformat mit klarer Preisstruktur. Wein in PET-Flaschen wird "
                "im deutschen Lebensmittel- und Fachhandel nicht verkauft — siehe "
                "Blatt „PET-Prüfung“.")

    headers = ["Kennzahl", "Wert", "Erläuterung"]
    litre = _litre_prices(still)
    boxes = [x for x in still if x.packaging == pkg.BAG_IN_BOX]
    three = [x for x in boxes if x.volume_l == 3.0]
    facts = [
        ("Erfasste Weinangebote gesamt", len(everything),
         "alle Weine aller Quellen, auch Glasflaschen"),
        ("davon PET oder Bag-in-Box", len(scope),
         f"{len(scope)/len(everything):.0%} des erfassten Sortiments"),
        ("davon Bag-in-Box", sum(1 for x in scope if x.packaging == pkg.BAG_IN_BOX), ""),
        ("davon PET-Flasche", sum(1 for x in scope if x.packaging == pkg.PET),
         "kein einziges Angebot gefunden"),
        ("Stillwein-Angebote in der Auswertung", len(still),
         "ohne Glühwein, Sangria und Schaumwein"),
    ]
    row = _table(sheet, row, headers, facts, {2: "#,##0"})

    stats = _stats(litre)
    box_stats = _stats(_litre_prices(boxes))
    three_stats = _stats(_litre_prices(three))
    price_rows = [
        ("Alle Stillweine PET/BiB", stats["n"], stats["min"], stats["median"],
         stats["mean"], stats["max"]),
        ("nur Bag-in-Box", box_stats["n"], box_stats["min"], box_stats["median"],
         box_stats["mean"], box_stats["max"]),
        ("nur 3-Liter-Bag-in-Box", three_stats["n"], three_stats["min"],
         three_stats["median"], three_stats["mean"], three_stats["max"]),
    ]
    row = _table(sheet, row,
                 ["Preispunkt (EUR/Liter)", "Angebote", "Minimum", "Median",
                  "Mittelwert", "Maximum"],
                 price_rows, {3: EUR_L, 4: EUR_L, 5: EUR_L, 6: EUR_L})

    # The 0.75 L equivalent is the comparison a shopper actually makes.
    equivalents = [x.bottle_equivalent_price for x in three
                   if x.bottle_equivalent_price is not None]
    eq = _stats(equivalents)
    if eq["n"]:
        row = _table(sheet, row,
                     ["3-Liter-Box umgerechnet auf 0,75 l", "Angebote", "Minimum",
                      "Median", "Mittelwert", "Maximum"],
                     [("Flaschenäquivalent", eq["n"], eq["min"], eq["median"],
                       eq["mean"], eq["max"])],
                     {3: EUR, 4: EUR, 5: EUR, 6: EUR})

    row = _note(sheet, row,
                "Pfand: Bag-in-Box ist nach § 31 Abs. 4 VerpackG als ökologisch "
                "vorteilhafte Einweggetränkeverpackung pfandfrei. Auf PET-Flaschen "
                "von 0,1 bis 3,0 Litern lägen 0,25 € Einwegpfand — seit dem "
                "1.1.2022 unabhängig vom Inhalt und damit auch auf Wein. Für die "
                "erhobenen Bag-in-Box-Angebote sind Regalpreis und Kassenpreis "
                "deshalb identisch.")
    _note(sheet, row,
          "METRO-Preise sind Netto-Handelspreise (B2B, ohne MwSt.) und werden in "
          "den Verbraucher-Kennzahlen oben nicht mitgerechnet. Sie stehen separat "
          "auf dem Blatt „Nach Händler“.")
    _autosize(sheet, [38, 12, 14, 12, 13, 12, 12, 12])


def _sheet_by_format(book: Workbook, scope: list[Listing]) -> None:
    sheet = book.create_sheet("Nach Gebindegröße")
    row = _title(sheet, "Preispunkt nach Gebindegröße",
                 "Nur Stillwein, Verbraucherpreise (ohne METRO-Nettopreise).")

    still = [x for x in scope
             if x.product_type == "still" and x.price_basis == "gross"]
    # Single containers only. A "BiB-Paket, 9 L" is three boxes sold together,
    # and listing it as a nine-litre gebinde would invent a size nobody fills.
    singles = [x for x in still if not x.is_pack]

    def _size_rows(group_source: list[Listing]) -> list[tuple]:
        out = []
        for volume, group in sorted(_by(group_source, lambda x: x.volume_l).items(),
                                    key=lambda kv: (kv[0] is None, kv[0])):
            stats = _stats(_litre_prices(group))
            prices = sorted(x.price for x in group if x.price is not None)
            out.append((
                f"{volume:g} l" if volume else "ohne Angabe",
                pkg.LABELS.get(group[0].packaging, ""),
                stats["n"], prices[0] if prices else None,
                statistics.median(prices) if prices else None,
                prices[-1] if prices else None,
                stats["min"], stats["median"], stats["max"],
            ))
        return out

    headers = ["Gebinde", "Verpackung", "Angebote", "Preis min", "Preis Median",
               "Preis max", "EUR/l min", "EUR/l Median", "EUR/l max"]
    money = {4: EUR, 5: EUR, 6: EUR, 7: EUR_L, 8: EUR_L, 9: EUR_L}
    row = _table(sheet, row, headers, _size_rows(singles), money)

    row = _note(sheet, row,
                "Die 3-Liter-Box ist das Standardgebinde und stellt die große "
                "Mehrheit aller erfassten Bag-in-Box-Angebote. Der Preis je "
                "Liter fällt mit der Gebindegröße: 5-Liter-Gebinde liegen "
                "darunter, 1,5- und 2,25-Liter-Gebinde deutlich darüber.", span=9)

    packs = [x for x in still if x.is_pack]
    if packs:
        row = _table(sheet, row,
                     ["Mehrfachpakete (getrennt ausgewiesen)"] + headers[1:],
                     _size_rows(packs), money)
        _note(sheet, row,
              "Pakete aus mehreren Boxen. Wo der Händler nur die Gesamtmenge "
              "nennt (etwa „BiB-Paket … 9 L“) und seine Stückzahl in "
              "Flaschenäquivalenten zählt, bleibt die Einzelbox-Größe offen; "
              "die Menge wird dann als Ganzes geführt. Der Preis je Liter ist "
              "in beiden Fällen korrekt.", span=9)
    _autosize(sheet, [34, 18, 11, 12, 14, 12, 12, 14, 12])


def _sheet_by_retailer(book: Workbook, scope: list[Listing]) -> None:
    sheet = book.create_sheet("Nach Händler")
    row = _title(sheet, "Preispunkt nach Händler und Vertriebskanal",
                 "Alle PET/Bag-in-Box-Angebote je Quelle.")

    rows = []
    for label, group in sorted(_by(scope, lambda x: x.retailer_label).items()):
        stats = _stats(_litre_prices(group))
        prices = sorted(x.price for x in group if x.price is not None)
        rows.append((
            label, group[0].channel,
            "netto (B2B)" if group[0].price_basis == "net" else "brutto",
            stats["n"], prices[0] if prices else None,
            prices[-1] if prices else None,
            stats["min"], stats["median"], stats["max"],
        ))
    row = _table(sheet, row,
                 ["Händler", "Kanal", "Preisbasis", "Angebote", "Preis min",
                  "Preis max", "EUR/l min", "EUR/l Median", "EUR/l max"],
                 rows, {5: EUR, 6: EUR, 7: EUR_L, 8: EUR_L, 9: EUR_L})

    _note(sheet, row,
          "Die Preisbasis trennt die Zeilen: METRO ist Cash & Carry und zeigt "
          "Nettopreise ohne MwSt., die rund 19 % unter einem vergleichbaren "
          "Verbraucherpreis liegen. Lidl ist der einzige erreichbare Filialist; "
          "Kaufland und REWE sperren Rechenzentrums-Adressen aus (Blatt "
          "„Nicht erreichbar“).", span=9)
    _autosize(sheet, [24, 18, 14, 11, 12, 12, 12, 14, 12])


def _sheet_segments(book: Workbook, scope: list[Listing]) -> None:
    sheet = book.create_sheet("Segmente")
    row = _title(sheet, "Preissegmente der 3-Liter-Bag-in-Box",
                 "Das Standardgebinde, über alle Verbraucherquellen.")

    three = [x for x in scope
             if x.packaging == pkg.BAG_IN_BOX and x.volume_l == 3.0
             and x.product_type == "still" and x.price_basis == "gross"
             and x.price is not None]

    # Bands cut at the gaps in the observed distribution, not at round numbers.
    # The floor is 4.99; the next cluster sits at 7.12; the median is 11.99 and
    # the upper quartile 15.99. So 8, 12 and 18 fall between groups rather than
    # through the middle of one.
    bands = [
        ("Einstieg", 0.0, 8.0, "Eigenmarken der Discounter und Hausweine"),
        ("Mittelfeld", 8.0, 12.0, "Marken wie Grand Sud, Maybach, Mertes"),
        ("Premium", 12.0, 18.0, "Sortenweine, Fachhandelsmarken"),
        ("Hochpreis", 18.0, 10_000.0, "Winzer- und Bioweine, Markenrosé"),
    ]
    rows = []
    for name, low, high, comment in bands:
        group = [x for x in three if low <= x.price < high]
        stats = _stats(_litre_prices(group))
        rows.append((
            name, f"{low:.2f}–{high:.2f} €" if high < 1000 else f"ab {low:.2f} €",
            len(group),
            round(len(group) / len(three), 4) if three else 0,
            stats["min"], stats["median"], stats["max"], comment,
        ))
    row = _table(sheet, row,
                 ["Segment", "Preisspanne (3 l)", "Angebote", "Anteil",
                  "EUR/l min", "EUR/l Median", "EUR/l max", "Typisch"],
                 rows, {4: PCT, 5: EUR_L, 6: EUR_L, 7: EUR_L})

    row = _note(sheet, row,
                "Der Einstiegspreis für 3 Liter Wein in Deutschland liegt bei "
                "4,99 € (1,66 €/l) — Lidls Eigenmarken Vino Tinto, Vino Rosado "
                "und Vino Blanco. Das entspricht 1,25 € je 0,75-l-Flasche und "
                "ist der Boden des Marktes.", span=8)

    by_colour = []
    for colour, group in sorted(_by([x for x in three if x.colour],
                                    lambda x: x.colour).items()):
        stats = _stats(_litre_prices(group))
        by_colour.append((
            {"rot": "Rotwein", "weiss": "Weißwein", "rose": "Roséwein"}.get(colour, colour),
            stats["n"], stats["min"], stats["median"], stats["max"]))
    row = _table(sheet, row,
                 ["Farbe (3-l-Box)", "Angebote", "EUR/l min", "EUR/l Median", "EUR/l max"],
                 by_colour, {3: EUR_L, 4: EUR_L, 5: EUR_L})

    by_country = []
    for country, group in sorted(_by([x for x in three if x.country],
                                     lambda x: x.country).items(),
                                 key=lambda kv: -len(kv[1])):
        stats = _stats(_litre_prices(group))
        by_country.append((country, stats["n"], stats["min"], stats["median"], stats["max"]))
    _table(sheet, row,
           ["Herkunft (3-l-Box)", "Angebote", "EUR/l min", "EUR/l Median", "EUR/l max"],
           by_country, {3: EUR_L, 4: EUR_L, 5: EUR_L})
    _autosize(sheet, [18, 20, 11, 10, 12, 14, 12, 42])


def _sheet_competing_formats(book: Workbook, everything: list[Listing]) -> None:
    """What bag-in-box is priced against on the same shelf."""
    sheet = book.create_sheet("Formatvergleich")
    row = _title(sheet, "Bag-in-Box im Vergleich zu den anderen Gebinden",
                 "Alle erfassten Weine nach Verpackungsart, Verbraucherpreise.")

    consumer = [x for x in everything
                if x.price_basis == "gross" and x.product_type == "still"]
    rows = []
    for container, group in sorted(_by(consumer, lambda x: x.packaging).items(),
                                   key=lambda kv: -len(kv[1])):
        stats = _stats(_litre_prices(group))
        deposits = {x.pfand for x in group if x.pfand is not None}
        rows.append((
            pkg.LABELS.get(container, container), stats["n"],
            stats["min"], stats["median"], stats["max"],
            "0,25 €" if deposits == {0.25} else ("pfandfrei" if deposits == {0.0}
                                                 else "gemischt/unbekannt"),
        ))
    row = _table(sheet, row,
                 ["Verpackung", "Angebote", "EUR/l min", "EUR/l Median",
                  "EUR/l max", "Pfand"],
                 rows, {3: EUR_L, 4: EUR_L, 5: EUR_L})

    row = _note(sheet, row,
                "„unbekannt“ heißt, dass der Händler die Verpackung nicht nennt. "
                "Das ist bei der gewöhnlichen 0,75-l-Flasche der Normalfall und "
                "wird hier nicht zu „Glas“ umgedeutet — die Zeile ist als "
                "Vergleichsmaßstab gedacht, nicht als Aussage über das Material. "
                "Das Maximum der Glasflaschen (1.600 €/l) ist echt: Lidl führt "
                "Château Lafite Rothschild zu 1.200 € je 0,75 l. Für den "
                "Formatvergleich zählt der Median, nicht der Rand.", span=6)

    # The one comparison that decides whether the format is cheap: a 3-litre box
    # against the litre bottle and the carton, which sit in the same aisle.
    litre_bottles = [x for x in consumer if x.volume_l == 1.0]
    cartons = [x for x in consumer if x.packaging == pkg.CARTON]
    boxes3 = [x for x in consumer
              if x.packaging == pkg.BAG_IN_BOX and x.volume_l == 3.0]
    compare = []
    for name, group in (("3-l-Bag-in-Box", boxes3),
                        ("1-l-Flasche (Literwein)", litre_bottles),
                        ("Getränkekarton", cartons)):
        stats = _stats(_litre_prices(group))
        compare.append((name, stats["n"], stats["min"], stats["median"], stats["max"]))
    _table(sheet, row,
           ["Direkter Vergleich (Einstiegsformate)", "Angebote", "EUR/l min",
            "EUR/l Median", "EUR/l max"],
           compare, {3: EUR_L, 4: EUR_L, 5: EUR_L})
    _autosize(sheet, [32, 11, 12, 14, 12, 20])


def _sheet_pet(book: Workbook, probe_results: list) -> None:
    sheet = book.create_sheet("PET-Prüfung")
    row = _title(sheet, "PET-Flaschen: gesuchte Belege",
                 "Die Hälfte der Fragestellung. Ergebnis: kein Angebot im Handel.")

    row = _note(sheet, row,
                "Wein in PET-Flaschen wurde in keinem der erreichten deutschen "
                "Sortimente gefunden. Weil ein Nullbefund aus einem Filter heraus "
                "wenig wert ist, wurde gezielt danach gesucht — mit den Wörtern, "
                "die ein deutscher Händler benutzen würde. Die Treffer, die "
                "tatsächlich PET waren, waren Sirup und Mineralwasser.")

    if probe_results:
        rows = [(r.source, r.query, r.hits, r.pet_hits, r.pet_wine_hits, r.example)
                for r in probe_results]
        row = _table(sheet, row,
                     ["Quelle", "Suchbegriff", "Treffer", "davon PET",
                      "davon PET-Wein", "Beispieltreffer"], rows)

    context = [
        ("Rechtslage", "Seit 1.1.2022 gilt das Einwegpfand von 0,25 € für alle "
                       "Einweg-Kunststoffgetränkeflaschen von 0,1 bis 3,0 l "
                       "unabhängig vom Inhalt — Wein in PET wäre also "
                       "pfandpflichtig, Bag-in-Box nicht."),
        ("Angebotsseite", "PET-Weinflaschen (250 ml, 750 ml) werden in "
                          "Deutschland als Leergut an Winzer und Caterer "
                          "verkauft, etwa über Flaschenland und "
                          "Plastikflaschenshop — nicht befüllt an Endkunden."),
        ("Einordnung", "Das große Gebinde ist in Deutschland die Bag-in-Box, "
                       "das kleine die Glasflasche. PET besetzt dazwischen "
                       "keine Position im Regal."),
        ("Wo PET auftauchen könnte", "Festival- und Bordgastronomie sowie "
                                     "Eigenabfüllungen; beides ist kein "
                                     "Handelssortiment und daher hier nicht "
                                     "erfasst."),
    ]
    _table(sheet, row, ["Punkt", "Befund"], context)
    _autosize(sheet, [22, 30, 10, 11, 14, 46])


def _sheet_unavailable(book: Workbook) -> None:
    sheet = book.create_sheet("Nicht erreichbar")
    row = _title(sheet, "Nicht erfasste Händler",
                 "Damit „nicht im Datensatz“ nicht mit „führt das Format nicht“ "
                 "verwechselt wird.")
    channel_labels = {"supermarkt": "Supermarkt", "discounter": "Discounter",
                      "getraenkemarkt": "Getränkemarkt", "fachhandel": "Fachhandel",
                      "online": "Online", "drogerie": "Drogerie"}
    rows = [(label, channel_labels.get(channel, channel), reason)
            for _, label, channel, reason in UNAVAILABLE]
    row = _table(sheet, row, ["Händler", "Kanal", "Grund"], rows)
    _note(sheet, row,
          "Die drei Getränkemarktketten sind der wichtigste Fall: Getränke "
          "Hoffmann, trinkgut und Fristo führen Bag-in-Box im Regal, "
          "veröffentlichen aber grundsätzlich keine Preise im Netz. Das ist "
          "keine technische Hürde, sondern ein Merkmal des deutschen "
          "Getränkefachhandels — die Preise stehen nur im Wochenprospekt und am "
          "Regal.", span=3)
    _autosize(sheet, [26, 18, 96])


def _sheet_data(book: Workbook, listings: list[Listing], title: str,
                sheet_name: str) -> None:
    sheet = book.create_sheet(sheet_name)
    row = _title(sheet, title,
                 "Eine Zeile je Angebot. Leere Felder heißen „vom Händler nicht "
                 "angegeben“ und sind nicht geschätzt.", span=len(EXPORT_COLUMNS))

    money = {EXPORT_COLUMNS.index(c) + 1: EUR
             for c in ("price", "pfand", "price_incl_pfand", "list_price",
                       "bottle_equivalent_price") if c in EXPORT_COLUMNS}
    money.update({EXPORT_COLUMNS.index(c) + 1: EUR_L
                  for c in ("price_per_litre", "price_per_litre_incl_pfand",
                            "unit_price") if c in EXPORT_COLUMNS})
    money[EXPORT_COLUMNS.index("volume_l") + 1] = NUM2

    body = []
    for listing in sorted(listings, key=lambda x: (x.retailer_label,
                                                   x.price_per_litre or 0)):
        flat = listing.to_row()
        body.append([flat.get(column) for column in EXPORT_COLUMNS])
    _table(sheet, row, EXPORT_COLUMNS, body, money, band=False)

    sheet.freeze_panes = sheet.cell(row=row + 1, column=1)
    sheet.auto_filter.ref = (f"A{row}:"
                             f"{get_column_letter(len(EXPORT_COLUMNS))}{row + len(body)}")
    widths = [14] * len(EXPORT_COLUMNS)
    for column in ("name", "url", "packaging_evidence", "category_path"):
        if column in EXPORT_COLUMNS:
            widths[EXPORT_COLUMNS.index(column)] = 52
    _autosize(sheet, widths)


def _sheet_method(book: Workbook, stamp: str, everything: list[Listing]) -> None:
    sheet = book.create_sheet("Methodik")
    row = _title(sheet, "Methodik und Belastbarkeit", f"Erhebung {stamp}")

    from .sources import all_sources
    rows = [(cls.label, cls.channel,
             "netto (B2B)" if cls.price_basis == "net" else "brutto",
             sum(1 for x in everything if x.retailer == key), cls.note)
            for key, cls in all_sources().items()]
    row = _table(sheet, row,
                 ["Quelle", "Kanal", "Preisbasis", "Erfasste Weine", "Zugang"], rows)

    notes = [
        ("Auswahlkriterium",
         "Aufgenommen wird ein Angebot nur, wenn die Verpackung aus Titel, "
         "Beschreibung, Kategorie oder Bildtext als PET-Flasche oder "
         "Bag-in-Box lesbar ist. Was nichts sagt, bleibt „unbekannt“ und "
         "fließt nicht in die Kennzahlen ein."),
        ("Preis je Liter",
         "Wird aus eigenem Preis und eigener Gebindegröße gerechnet, nicht vom "
         "Händler übernommen — Händler rechnen den Grundpreis unterschiedlich "
         "(mit oder ohne Pfand). Der Grundpreis des Händlers steht als "
         "unit_price daneben und dient als Gegenprobe."),
        ("Gegenprobe",
         "Jede Zeile mit beiden Werten wird verglichen. In der aktuellen "
         "Erhebung stimmen alle vergleichbaren Zeilen überein. Der Test hat "
         "einen echten Fehler gefunden: bei Wein Schäpers stehen Preis und "
         "Grundpreis in benachbarten Elementen, und der Parser hatte zunächst "
         "den Grundpreis als Preis gelesen."),
        ("Gebinde vs. Packung",
         "Ein 6er-Karton mit 0,75-l-Flaschen meldet 4,5 Liter. Ohne Korrektur "
         "wäre er als Großgebinde in die Auswertung geraten; Packungsgröße und "
         "Stückzahl werden deshalb getrennt geführt."),
        ("Abgrenzung",
         "Glühwein, Sangria, Schaumwein und Süßwein sind erfasst, aber aus den "
         "Stillwein-Kennzahlen ausgenommen: sie liegen je Liter auf einer "
         "anderen Skala und würden den Preispunkt verzerren."),
        ("Grenzen",
         "Die Erhebung ist eine Momentaufnahme des Online-Sortiments. Sie "
         "erfasst weder Aktionsware im Prospekt noch das Regal der "
         "Getränkemärkte, und mit Lidl nur einen von fünf großen Filialisten."),
    ]
    _table(sheet, row, ["Punkt", "Erläuterung"], notes)
    _autosize(sheet, [26, 110, 14, 14, 60])


# --- entry point -------------------------------------------------------------
def build_workbook(listings: list[Listing], path: Path,
                   probe_results: list | None = None) -> Path:
    """Write the study workbook and return where it went."""
    scope = [x for x in listings if pkg.is_in_scope(x.packaging)]
    stamp = datetime.now(timezone.utc).strftime("%d.%m.%Y")

    book = Workbook()
    book.remove(book.active)

    _sheet_summary(book, scope, listings, stamp)
    _sheet_segments(book, scope)
    _sheet_by_format(book, scope)
    _sheet_by_retailer(book, scope)
    _sheet_competing_formats(book, listings)
    _sheet_pet(book, probe_results or [])
    _sheet_unavailable(book)
    _sheet_data(book, scope, "PET- und Bag-in-Box-Angebote — Rohdaten", "Alle Daten")
    _sheet_data(book, listings, "Gesamtes erfasstes Weinsortiment", "Gesamtsortiment")
    _sheet_method(book, stamp, listings)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
    return path
