"""Figures for the entry-segment brief: 2 L wine under 10 lei per litre.

Written to JSON so the document contains no typed numbers, for the same reason
the main brief does not: a figure with a generator behind it cannot quietly
outlive the data it came from.

    python tools/segment_facts.py    ->  /tmp/segment_facts.json
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from winescraper import pricing  # noqa: E402
from winescraper.storage import Store  # noqa: E402

#: The threshold the analysis is cut on, in RON per litre.
CEILING = 10.0
#: The format the segment actually lives in.
FORMAT_L = 2.0
#: The wine everything is measured against.
BENCHMARK = "MUSCATEL"

LABELS = {
    "metro": "METRO", "selgros": "Selgros", "carrefour": "Carrefour",
    "penny_bolt": "Penny (Bolt)", "kaufland_bolt": "Kaufland (Bolt)",
    "profi_glovo": "Profi (Glovo)", "supeco_glovo": "Supeco (Glovo)",
    "auchan": "Auchan", "penny": "Penny", "freshful": "Freshful",
    "sezamo": "Sezamo", "mega_image": "Mega Image", "kaufland": "Kaufland",
}


def shorten(name: str) -> str:
    """Trim the deposit and volume markers retailers append to every title."""
    for junk in (" SGR 2 L", " 2,0 PET", " 2L PET", " 2 l", " 2L", " 2,0"):
        if name.endswith(junk):
            name = name[: -len(junk)]
    return name.strip(" ,")


def main() -> dict:
    with Store("data/wines.sqlite") as store:
        rows = [dict(r) for r in store.latest()]
    for r in rows:
        r["ppl"] = pricing.per_litre(pricing.regular(r), r["volume_l"])

    priced = [r for r in rows if r["ppl"]]
    segment = [r for r in priced if r["ppl"] < CEILING]
    two = sorted((r for r in segment if r["volume_l"] == FORMAT_L),
                 key=lambda r: (r["ppl"], r["name"]))

    def line(r: dict) -> dict:
        return {"retailer": LABELS.get(r["retailer"], r["retailer"]),
                "name": shorten(r["name"]),
                "price": round(pricing.regular(r), 2), "ppl": round(r["ppl"], 2),
                "colour": r["colour"] or "", "sweetness": r["sweetness"] or "",
                "benchmark": r["name"].startswith(BENCHMARK)}

    benchmark = [r for r in two if r["name"].startswith(BENCHMARK)]
    rivals = [r for r in two if not r["name"].startswith(BENCHMARK)]
    bench_ppl = benchmark[0]["ppl"]
    rival_ppl = [r["ppl"] for r in rivals]

    out = {
        "collected": max((r["observed_at"] or "")[:10] for r in rows),
        "ceiling": CEILING,
        "market_median_ppl": round(statistics.median(r["ppl"] for r in priced), 2),
        "n_priced": len(priced),
        "n_segment": len(segment),
        "n_two_litre": len(two),
        "n_shops": len({r["retailer"] for r in two}),
        "rows": [line(r) for r in two],
        "benchmark": {
            "name": shorten(benchmark[0]["name"]),
            "retailer": LABELS[benchmark[0]["retailer"]],
            "ppl": round(bench_ppl, 2),
            "price": round(pricing.regular(benchmark[0]), 2),
            "listings": len(benchmark),
            "cheaper_rivals": sum(1 for p in rival_ppl if p < bench_ppl),
            "rivals": len(rivals),
            "vs_median": round(bench_ppl / statistics.median(rival_ppl) - 1, 4),
            "vs_floor": round(bench_ppl / min(rival_ppl) - 1, 4),
            "rival_median": round(statistics.median(rival_ppl), 2),
            "floor": round(min(rival_ppl), 2),
        },
    }

    # Same shelf: what else the benchmark's own retailer sells in this format.
    home = LABELS[benchmark[0]["retailer"]]
    out["same_shelf"] = [line(r) for r in two
                         if LABELS.get(r["retailer"]) == home]

    # The same wine at several retailers, which is where the format's real
    # price dispersion shows up.
    groups = defaultdict(list)
    for r in two:
        groups[r["wine_key"]].append(r)
    out["same_wine"] = []
    for key, members in groups.items():
        shops = {r["retailer"] for r in members}
        if len(shops) < 2:
            continue
        members = sorted(members, key=lambda r: r["ppl"])
        out["same_wine"].append({
            "key": key,
            "spread": round(members[-1]["ppl"] / members[0]["ppl"] - 1, 4),
            "rows": [line(r) for r in members],
        })
    out["same_wine"].sort(key=lambda g: -g["spread"])

    # Does a bigger pack buy a cheaper litre? Measured, not assumed.
    out["formats"] = []
    for volume in sorted({r["volume_l"] for r in segment}):
        vals = [r["ppl"] for r in segment if r["volume_l"] == volume]
        out["formats"].append({
            "litres": volume, "n": len(vals),
            "low": round(min(vals), 2), "high": round(max(vals), 2),
            "median": round(statistics.median(vals), 2)})

    # Sweetness and colour, inside the 2 L format only.
    def split(field: str, values: tuple) -> list:
        rows_out = []
        for value in values:
            vals = [r["ppl"] for r in two if (r[field] or "") == value]
            if vals:
                rows_out.append({"value": value, "n": len(vals),
                                 "median": round(statistics.median(vals), 2)})
        return rows_out

    out["sweetness"] = split("sweetness", ("demidulce", "demisec", "sec"))
    out["colour"] = split("colour", ("alb", "rosu", "rose"))

    # Which shops play in this format at all.
    out["shops"] = []
    for retailer in sorted({r["retailer"] for r in two}):
        vals = [r["ppl"] for r in two if r["retailer"] == retailer]
        whole = [r["ppl"] for r in priced if r["retailer"] == retailer]
        out["shops"].append({
            "retailer": LABELS.get(retailer, retailer), "n": len(vals),
            "low": round(min(vals), 2), "high": round(max(vals), 2),
            "range_median": round(statistics.median(whole), 2)})
    out["shops"].sort(key=lambda s: -s["n"])
    out["absent"] = sorted(LABELS[r] for r in
                           {x["retailer"] for x in priced} -
                           {x["retailer"] for x in two})

    # The cheapest ordinary bottle anywhere, for scale.
    bottles = sorted((r for r in priced if r["volume_l"] and 0.7 <= r["volume_l"] <= 0.8),
                     key=lambda r: r["ppl"])[:1]
    out["cheapest_bottle"] = line(bottles[0]) if bottles else None
    return out


if __name__ == "__main__":
    facts = main()
    with open("/tmp/segment_facts.json", "w", encoding="utf-8") as handle:
        json.dump(facts, handle, ensure_ascii=False, indent=1)
    print(f"wrote /tmp/segment_facts.json: {facts['n_two_litre']} listings of "
          f"{FORMAT_L:g} L under {CEILING:g} RON/L across {facts['n_shops']} shops")
