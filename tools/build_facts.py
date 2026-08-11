"""Headline figures for the issue brief: coverage, cross-retailer matches, win rates.

`build_rankings.py` produces the ranked tables; this produces the handful of
whole-dataset numbers the brief's prose depends on. It exists as a file rather
than as something typed at a prompt because the brief once carried "7,513
listings" for three re-scrapes after that stopped being true — a figure with no
generator behind it cannot go stale visibly.

    python tools/build_facts.py     ->  /tmp/brief_facts.json
"""
from __future__ import annotations

import importlib.util
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from winescraper.validate import check  # noqa: E402

spec = importlib.util.spec_from_file_location("bx", "tools/build_workbook.py")
bx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bx)

rows = bx.load_rows()
matches = bx.find_matches(rows)

out: dict = {"total": len(rows)}

# -- coverage per retailer ------------------------------------------------
out["by_retailer"] = dict(Counter(r["retailer"] for r in rows))

# -- the same wine, priced by more than one retailer ----------------------
spreads = sorted(m["spread"] for m in matches)
out["matches"] = {
    "n": len(matches),
    "median": round(statistics.median(spreads), 4),
    "over20": round(sum(1 for s in spreads if s >= 0.20) / len(spreads), 3),
    "over10": round(sum(1 for s in spreads if s >= 0.10) / len(spreads), 3),
    "max": round(spreads[-1], 3),
    # What one bottle of each matched wine costs if bought entirely at the
    # cheapest retailer for each, against entirely at the dearest.
    "basket_lo": round(sum(m["lo"] for m in matches)),
    "basket_hi": round(sum(m["hi"] for m in matches)),
}

# -- head-to-head: who is cheapest when several carry the same wine -------
appears, wins, loses = Counter(), Counter(), Counter()
for m in matches:
    for retailer in m["retailers"]:
        appears[retailer] += 1
    wins[m["cheap"]] += 1
    loses[m["dear"]] += 1
# Ten appearances is the floor at which a win rate means anything.
out["wins"] = {
    k: {"n": appears[k], "win": wins[k], "winrate": round(wins[k] / appears[k], 3),
        "lose": loses[k], "loserate": round(loses[k] / appears[k], 3)}
    for k in appears if appears[k] >= 10
}

# -- does a delivery platform price match the retailer's own shelf? -------
# Penny is the only retailer read both ways, which makes it the only test of
# whether a platform price can stand in for a shelf price. The answer moves
# between runs — Penny discounts on its own site and Bolt does not always
# follow — so it is measured on every build rather than quoted from memory.
_STOPWORDS = {"vin", "vinul", "alb", "rosu", "rose", "sec", "demisec",
              "demidulce", "dulce", "alcool"}


def _tokens(name: str) -> frozenset:
    return frozenset(w for w in re.findall(r"[a-z]+", bx.fold(name))
                     if len(w) > 2 and w not in _STOPWORDS)


def _overlap(left: str, right: str) -> dict:
    a, b = {}, {}
    for row in rows:
        if row["retailer"] == left:
            a.setdefault(_tokens(row["name"]), row)
        elif row["retailer"] == right:
            b.setdefault(_tokens(row["name"]), row)
    gaps = []
    for ka, ra in a.items():
        for kb, rb in b.items():
            shared = ka & kb
            if len(shared) >= 2 and len(shared) / max(1, min(len(ka), len(kb))) >= 0.6:
                gaps.append((rb["price"] - ra["price"]) / ra["price"])
                break
    if not gaps:
        return {"n": 0}
    return {"n": len(gaps),
            "same": sum(1 for g in gaps if abs(g) < 0.005),
            "median": round(statistics.median(gaps), 4),
            "dearer": sum(1 for g in gaps if g > 0.005)}


out["penny_overlap"] = _overlap("penny", "penny_bolt")

# -- how many rows fail the checks in winescraper.validate -----------------
_findings = check(rows)
out["unit_price_conflicts"] = sum(1 for f in _findings if f.kind == "unit price disagrees")
out["review_queue"] = sum(1 for f in _findings if f.kind == "review")
# Only rows carrying a per-litre figure can be cross-checked at all; quoting the
# whole dataset as the denominator would overstate how much has been verified.
out["unit_price_checked"] = sum(
    1 for r in rows
    if r.get("unit_price") and r.get("volume_l") and r.get("price")
    and (r.get("unit_price_unit") or "").strip().lower() in {"", "l", "1l", "litru"})

# -- attribute coverage ---------------------------------------------------
out["abv_n"] = sum(1 for r in rows if r.get("abv"))
# The collection date, so no document has to carry it as a typed constant.
out["collected"] = max((r["observed_at"] or "")[:10] for r in rows)
# Entry price: the cheapest bottle each substantial retailer actually lists.
_entry = sorted(
    min(r["price"] for r in rows
        if r["retailer"] == ret and r.get("price") and 0.7 <= (r.get("volume_l") or 0) <= 0.8)
    for ret, count in out["by_retailer"].items() if count >= 200)
out["entry_lo"], out["entry_hi"] = round(_entry[0]), round(_entry[-1])
# Most retailers cluster at the floor; two delivery-only shops start higher.
out["entry_typical_hi"] = round(_entry[len(_entry) - 3])
out["vol"] = sum(1 for r in rows if r.get("volume_l"))
out["colour"] = sum(1 for r in rows if r.get("colour"))
out["sweet"] = sum(1 for r in rows if r.get("sweetness"))
out["sparkling"] = sum(1 for r in rows if r.get("sparkling"))
out["grape_tagged"] = sum(1 for r in rows if r.get("grape_varieties"))
out["country_known"] = sum(1 for r in rows if bx.canon_country(r.get("country")))

if __name__ == "__main__":
    path = "/tmp/brief_facts.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
    print(f"wrote {path}: {out['total']:,} listings, {out['matches']['n']} matched wines, "
          f"{len(out['wins'])} retailers with a comparable win rate")
