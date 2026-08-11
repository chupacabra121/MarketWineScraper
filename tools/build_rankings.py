"""Extract every ranking worth putting in the brief, with the counts to back it."""
import json, re, statistics, unicodedata, importlib.util
from collections import Counter, defaultdict

spec = importlib.util.spec_from_file_location("bx", "tools/build_workbook.py")
bx = importlib.util.module_from_spec(spec); spec.loader.exec_module(bx)
rows = bx.load_rows()
matches = bx.find_matches(rows)
fold = bx.fold
canon = bx.canon_country

SHELF = {"auchan", "carrefour", "selgros", "metro", "freshful", "sezamo", "mega_image", "penny"}
PLATFORM = {"kaufland_bolt", "penny_bolt", "profi_glovo", "supeco_glovo"}
# Assortment rankings count every source. Restricting them to shelf-price
# retailers dropped Kaufland's 737 wines, Supeco's 101 and Profi's 69 from every
# brand, variety and style ranking, which understated the market. Price basis
# still matters for retailer-vs-retailer comparison, so `depth` carries it.
shelf_rows = [r for r in rows if r["retailer"] in SHELF or r["retailer"] in PLATFORM]
std = [r for r in shelf_rows if r.get("price") and 0.7 <= (r.get("volume_l") or 0) <= 0.8]

out = {}
out["n_all"] = len(rows)
out["n_shelf"] = len(shelf_rows)
out["n_std"] = len(std)

def brand_key(r):
    b = (r.get("brand") or "").strip()
    return b if len(b) >= 2 else None

# ---------------------------------------------------------------- BRANDS
brand_rows = defaultdict(list)
for r in shelf_rows:
    b = brand_key(r)
    if b:
        brand_rows[fold(b)].append(r)

def disp(bkey):
    names = Counter((r.get("brand") or "").strip() for r in brand_rows[bkey])
    return names.most_common(1)[0][0]

# widest distribution = number of distinct retailers carrying the brand
brand_stats = []
for bkey, rs in brand_rows.items():
    rets = {r["retailer"] for r in rs}
    prices = [r["price"] for r in rs if r.get("price")]
    ppl = [r["price"] / r["volume_l"] for r in rs
           if r.get("price") and r.get("volume_l") and 0.7 <= r["volume_l"] <= 0.8]
    if not prices:
        continue
    brand_stats.append({
        "brand": disp(bkey), "listings": len(rs), "retailers": len(rets),
        "median_price": round(statistics.median(prices), 2),
        "median_ppl": round(statistics.median(ppl), 2) if ppl else None,
        "min": round(min(prices), 2), "max": round(max(prices), 2),
    })

out["brands_by_listings"] = sorted(brand_stats, key=lambda x: -x["listings"])[:20]
out["brands_by_reach"] = sorted(
    [b for b in brand_stats if b["listings"] >= 8],
    key=lambda x: (-x["retailers"], -x["listings"]))[:15]
out["brands_premium"] = sorted(
    [b for b in brand_stats if b["listings"] >= 5 and b["median_ppl"]],
    key=lambda x: -x["median_ppl"])[:15]
out["brands_value"] = sorted(
    [b for b in brand_stats if b["listings"] >= 5 and b["median_ppl"]],
    key=lambda x: x["median_ppl"])[:15]
out["n_brands"] = len(brand_stats)

# ------------------------------------------------------------- VARIETIES
grape_rows = defaultdict(list)
for r in shelf_rows:
    for g in (r.get("grape_varieties") or "").split(","):
        g = g.strip()
        if g:
            grape_rows[g].append(r)
grape_stats = []
for g, rs in grape_rows.items():
    ppl = [r["price"] / r["volume_l"] for r in rs
           if r.get("price") and r.get("volume_l") and 0.7 <= r["volume_l"] <= 0.8]
    if len(rs) >= 15 and ppl:
        grape_stats.append({
            "grape": g, "listings": len(rs), "median_ppl": round(statistics.median(ppl), 2),
            "retailers": len({r["retailer"] for r in rs}),
            "p90": round(sorted(ppl)[int(0.9 * len(ppl))], 2),
        })
out["grapes_by_listings"] = sorted(grape_stats, key=lambda x: -x["listings"])[:20]
out["grapes_by_price"] = sorted(grape_stats, key=lambda x: -x["median_ppl"])[:15]
out["grapes_cheapest"] = sorted(grape_stats, key=lambda x: x["median_ppl"])[:10]
out["n_grapes"] = len(grape_rows)

# --------------------------------------------------------------- COLOUR
col = {}
for c in ("alb", "rosu", "rose"):
    rs = [r for r in std if r.get("colour") == c]
    ppl = [r["price"] / r["volume_l"] for r in rs]
    col[c] = {"n": len(rs), "median_ppl": round(statistics.median(ppl), 2),
              "share": round(len(rs) / len(std), 3)}
sp = [r for r in std if r.get("sparkling")]
col["sparkling"] = {"n": len(sp), "median_ppl": round(statistics.median(
    [r["price"] / r["volume_l"] for r in sp]), 2), "share": round(len(sp) / len(std), 3)}
still = [r for r in std if not r.get("sparkling")]
col["still"] = {"n": len(still), "median_ppl": round(statistics.median(
    [r["price"] / r["volume_l"] for r in still]), 2), "share": round(len(still) / len(std), 3)}
out["colour"] = col

# ------------------------------------------------------------ SWEETNESS
sw = {}
for s in ("sec", "demisec", "demidulce", "dulce"):
    rs = [r for r in std if r.get("sweetness") == s]
    if rs:
        ppl = [r["price"] / r["volume_l"] for r in rs]
        sw[s] = {"n": len(rs), "median_ppl": round(statistics.median(ppl), 2),
                 "share": round(len(rs) / len(std), 3)}
out["sweetness"] = sw

# Sweetness x colour, so the price effect can be shown to hold within each colour
# rather than being a colour effect in disguise.
sxc = {}
for c in ("alb", "rosu", "rose"):
    sxc[c] = {}
    for sname in ("sec", "demisec", "demidulce", "dulce"):
        v = [r["price"] / r["volume_l"] for r in std
             if r.get("colour") == c and r.get("sweetness") == sname]
        sxc[c][sname] = round(statistics.median(v), 2) if len(v) >= 25 else None
out["sweetness_by_colour"] = sxc

# -------------------------------------------------------------- COUNTRY
cs = defaultdict(list)
for r in std:
    c = canon(r.get("country"))
    if c:
        cs[c].append(r)
country_stats = [{
    "country": c, "listings": len(rs),
    "median_ppl": round(statistics.median([r["price"] / r["volume_l"] for r in rs]), 2),
} for c, rs in cs.items() if len(rs) >= 8]
out["countries"] = sorted(country_stats, key=lambda x: -x["listings"])[:15]
out["countries_by_price"] = sorted(country_stats, key=lambda x: -x["median_ppl"])[:12]
out["country_known"] = sum(len(v) for v in cs.values())

# --------------------------------------------------------------- REGION
rg = defaultdict(list)
for r in std:
    reg = (r.get("region") or "").strip()
    if reg:
        rg[reg].append(r)
region_stats = [{
    "region": reg, "listings": len(rs),
    "median_ppl": round(statistics.median([r["price"] / r["volume_l"] for r in rs]), 2),
} for reg, rs in rg.items() if len(rs) >= 8]
out["regions"] = sorted(region_stats, key=lambda x: -x["listings"])[:15]
out["regions_by_price"] = sorted(region_stats, key=lambda x: -x["median_ppl"])[:12]

# ------------------------------------------------------- INDIVIDUAL LABELS
priced = [r for r in std]
out["most_expensive"] = [{
    "name": r["name"][:70], "retailer": r["retailer"], "price": round(r["price"], 2),
} for r in sorted(priced, key=lambda r: -r["price"])[:15]]
out["cheapest"] = [{
    "name": r["name"][:70], "retailer": r["retailer"], "price": round(r["price"], 2),
} for r in sorted(priced, key=lambda r: r["price"])[:15]]

# labels carried by the most retailers (from strict matches)
out["most_widely_stocked"] = [{
    "name": m["name"][:70], "retailers": m["n"], "lo": round(m["lo"], 2),
    "hi": round(m["hi"], 2), "spread": round(m["spread"], 3),
} for m in sorted(matches, key=lambda m: (-m["n"], m["lo"]))[:15]]

out["biggest_gaps"] = [{
    "name": m["name"][:70], "retailers": m["n"], "lo": round(m["lo"], 2),
    "hi": round(m["hi"], 2), "spread": round(m["spread"], 3),
    "cheap": m["cheap"], "dear": m["dear"],
} for m in sorted(matches, key=lambda m: -m["spread"])[:15]]

out["tightest"] = [{
    "name": m["name"][:70], "retailers": m["n"], "lo": round(m["lo"], 2),
    "hi": round(m["hi"], 2), "spread": round(m["spread"], 3),
} for m in sorted(matches, key=lambda m: m["spread"])[:10]]

# ------------------------------------------------------------- PRICE BANDS
bands = [("Under 25 lei", 0, 25), ("25-50 lei", 25, 50), ("50-100 lei", 50, 100),
         ("100-200 lei", 100, 200), ("200+ lei", 200, 10 ** 9)]
band_tbl = []
for label, lo, hi in bands:
    rs = [r for r in std if lo <= r["price"] < hi]
    row = {"band": label, "n": len(rs), "share": round(len(rs) / len(std), 3)}
    for ret in ("auchan", "carrefour", "metro", "selgros", "freshful", "sezamo", "kaufland_bolt"):
        sub = [r for r in std if r["retailer"] == ret and lo <= r["price"] < hi]
        tot = len([r for r in std if r["retailer"] == ret]) or 1
        row[ret] = round(len(sub) / tot, 3)
    band_tbl.append(row)
out["bands"] = band_tbl

# ---------------------------------------------------------- RETAILER DEPTH
depth = []
for ret in (SHELF | PLATFORM):
    rs = [r for r in std if r["retailer"] == ret]
    if len(rs) < 25:
        continue
    ppl = sorted(r["price"] / r["volume_l"] for r in rs)
    brands = len({fold(r.get("brand") or "") for r in rs if r.get("brand")})
    depth.append({
        "retailer": ret, "basis": "Shelf" if ret in SHELF else "Platform",
        "n": len(rs), "brands": brands,
        "median": round(statistics.median(ppl), 2),
        "p10": round(ppl[len(ppl) // 10], 2), "p90": round(ppl[9 * len(ppl) // 10], 2),
        "over200": round(sum(1 for r in rs if r["price"] >= 200) / len(rs), 3),
        "under25": round(sum(1 for r in rs if r["price"] < 25) / len(rs), 3),
    })
out["depth"] = sorted(depth, key=lambda x: x["median"])

# ---------------------------------------------------------------- VINTAGE
vt = Counter(r.get("vintage") for r in rows if r.get("vintage"))
out["vintages"] = dict(sorted(vt.items(), key=lambda kv: -kv[1])[:10])
out["vintage_known"] = sum(vt.values())

# ------------------------------------------------ PROMO SENSITIVITY
# `price` is what a shopper pays on the day, discount included. Re-running the
# head-to-head on pre-discount prices shows how much of each retailer's standing
# is promotional rather than structural.
regular = [dict(r) for r in rows]
for r in regular:
    if r.get("list_price"):
        r["price"] = r["list_price"]

def _wins(match_rows):
    ap, wi, lo = Counter(), Counter(), Counter()
    for m in match_rows:
        for ret in m["retailers"]:
            ap[ret] += 1
        wi[m["cheap"]] += 1
        lo[m["dear"]] += 1
    return {k: {"n": ap[k], "win": wi[k], "winrate": round(wi[k] / ap[k], 3),
                "lose": lo[k], "loserate": round(lo[k] / ap[k], 3)}
            for k in ap if ap[k] >= 10}

reg_matches = bx.find_matches(regular)
reg_sp = sorted(m["spread"] for m in reg_matches)
out["wins_regular"] = _wins(reg_matches)
out["promo_sensitivity"] = {
    "paid_median": round(statistics.median(sorted(m["spread"] for m in matches)), 4),
    "regular_median": round(statistics.median(reg_sp), 4),
    "paid_over20": round(sum(1 for x in sorted(m["spread"] for m in matches) if x >= .2)
                         / len(matches), 3),
    "regular_over20": round(sum(1 for x in reg_sp if x >= .2) / len(reg_sp), 3),
    "paid_basket": round(sum(m["hi"] for m in matches) / sum(m["lo"] for m in matches) - 1, 3),
    "regular_basket": round(sum(m["hi"] for m in reg_matches)
                            / sum(m["lo"] for m in reg_matches) - 1, 3),
    "promo_rows": sum(1 for r in rows if r.get("on_promotion")),
    "median_discount": round(statistics.median(
        [1 - r["price"] / r["list_price"] for r in rows
         if r.get("on_promotion") and r.get("price") and r.get("list_price")]), 3),
}
out["promo_by_retailer"] = {
    k: {"promo": sum(1 for r in rows if r["retailer"] == k and r.get("on_promotion")),
        "total": sum(1 for r in rows if r["retailer"] == k)}
    for k in {r["retailer"] for r in rows}
}

json.dump(out, open("/tmp/rankings.json", "w"), ensure_ascii=False, indent=1)

# ------------------------------------------------------------------ print
def show(title, items, cols):
    print(f"\n=== {title} ===")
    for it in items:
        print("  " + "  ".join(str(it.get(c, ""))[:34].ljust(w) for c, w in cols))

print(f"rows={out['n_all']} shelf={out['n_shelf']} std0.75={out['n_std']} "
      f"brands={out['n_brands']} grapes={out['n_grapes']}")
show("BRANDS BY LISTINGS", out["brands_by_listings"][:12],
     [("brand", 26), ("listings", 4), ("retailers", 3), ("median_ppl", 7)])
show("BRANDS BY REACH", out["brands_by_reach"][:12],
     [("brand", 26), ("retailers", 3), ("listings", 4), ("median_ppl", 7)])
show("PREMIUM BRANDS", out["brands_premium"][:10], [("brand", 26), ("median_ppl", 7), ("listings", 4)])
show("VALUE BRANDS", out["brands_value"][:10], [("brand", 26), ("median_ppl", 7), ("listings", 4)])
show("GRAPES BY LISTINGS", out["grapes_by_listings"][:14],
     [("grape", 26), ("listings", 4), ("median_ppl", 7), ("retailers", 3)])
show("GRAPES BY PRICE", out["grapes_by_price"][:12], [("grape", 26), ("median_ppl", 7), ("listings", 4)])
show("GRAPES CHEAPEST", out["grapes_cheapest"][:8], [("grape", 26), ("median_ppl", 7), ("listings", 4)])
print("\n=== COLOUR ===", json.dumps(out["colour"], indent=1))
print("=== SWEETNESS ===", json.dumps(out["sweetness"], indent=1))
show("COUNTRIES", out["countries"][:12], [("country", 20), ("listings", 5), ("median_ppl", 7)])
show("REGIONS", out["regions"][:12], [("region", 26), ("listings", 5), ("median_ppl", 7)])
show("MOST EXPENSIVE", out["most_expensive"][:10], [("name", 52), ("retailer", 12), ("price", 8)])
show("CHEAPEST", out["cheapest"][:10], [("name", 52), ("retailer", 12), ("price", 8)])
show("MOST WIDELY STOCKED", out["most_widely_stocked"][:10],
     [("name", 46), ("retailers", 3), ("lo", 7), ("hi", 7), ("spread", 6)])
show("BIGGEST GAPS", out["biggest_gaps"][:10],
     [("name", 40), ("lo", 7), ("cheap", 11), ("hi", 7), ("dear", 11), ("spread", 6)])
show("DEPTH", out["depth"], [("retailer", 14), ("n", 5), ("brands", 5), ("median", 7),
                             ("p10", 7), ("p90", 8), ("over200", 6)])
print("\n=== BANDS ===")
for b in out["bands"]:
    print(f"  {b['band']:<14} n={b['n']:<5} share={b['share']:<6} "
          f"auchan={b['auchan']:<6} metro={b['metro']:<6} sezamo={b['sezamo']:<6} freshful={b['freshful']}")
print("\n=== VINTAGES ===", out["vintages"], "known:", out["vintage_known"])
