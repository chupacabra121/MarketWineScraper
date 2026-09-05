# -*- coding: utf-8 -*-
"""Consolidate the harvest into a dated 2021-2026 campaign timeline."""
import json, re, collections

site = json.load(open("posts_all.json"))
iq = json.load(open("posts_iqads_strict.json"))

# Navigation, product-category and boilerplate rows scraped alongside real posts.
JUNK = re.compile(
    r"^(cite[sșş]te mai mult|citeşte mai mult|citește mai mult|mai multe|vezi mai multe|"
    r"politica|termeni|livrare|list[ăa] dorin|hello world|some useful links|"
    r"中文|meniu|men[uü] |co[sș]\b|\[email|cart\b|toate produsele|accesorii|"
    r"b[ăa]uturi spirtoase|pachete speciale|vin lini[sș]tit|fructe de mare|"
    r"vizitează-ne|visit vineyard|make a reservation|wine tourism|view our collection|"
    r"soiuri$|locul/terroir|punct turistic|descriere parcele|terroir$|"
    r"produce?rea |degustarea vinului|parteneriate b2b|wine collections|photo & video|"
    r"despre budureasca|medals & awards|convocator|meniu wine bar|"
    r"terrace bar|coffe corner|wellness spa|nativus mini|metoda |diamond selection|"
    r"crama de|crama h|crama o|caii de la letea)", re.I)

CLASS = [
 ("Awards / reputation", r"(medal|aur\b|argint|premi[uaei]|decanter|mundus|concours|campion|trophy|"
                         r"gold|cswwc|vinalies|berliner|challenge international|london wine|"
                         r"vinarium|best producer|top \d|distins|titlu|efie|effie|gopo)"),
 ("Trade / export",      r"(prowein|vinexpo|wine paris|winecon|expo\b|t[âa]rg|salon|pavilion|"
                         r"export|congres|fair)"),
 ("Experiential / events", r"(festival|night run|maraton|alergare|trail|weinrun|concert|gal[ăa]|"
                          r"eveniment|jazz|bal\b|design week|art safari|cules|petrecere|"
                          r"degust[ăa]ri|tur\b|ziua vinului|nocturne)"),
 ("Sponsorship / partnership", r"(partener|sponsor|vinul oficial|vin oficial|ambasador|"
                               r"colabor|al[ăa]turi de|sus[țt]ine|capital[ăa] european)"),
 ("Product launch",      r"(lans[eăa]|premier[ăa]|nou[ăa]? gam|noua colec|edi[țt]ie limitat|"
                         r"a f[ăa]cut apari|descoper[ăa] gama|introduce)"),
 ("Promotion / contest", r"(campanie|concurs|promo[țt]|c[âa][șs]tig|roata|tombol|voucher|reducer)"),
 ("CSR / sustainability", r"(sustenabil|biodiversit|burs[ăa]|educa[țt]|doneaz|masterclass|"
                          r"responsabil|mediu|risip|verde|comunit)"),
 ("Corporate / financial", r"(raport financiar|achizi[țt]|ac[țt]iun|investor|ipo\b|strategi|"
                           r"rezultate financiare|cifra de afaceri|creștere de|extinde|"
                           r"parte din grupul|director general|numi)"),
 ("Content marketing",   r"(ghid|cum (se|alegi|savurezi|potrivești|ia)|re[țt]et[ăa]|top \d|"
                         r"sfaturi|ce este|de ce|diferen[țt]|pairing|c[âa]t |c[âa]nd )"),
]

def classify(title):
    for label, pat in CLASS:
        if re.search(pat, title, re.I):
            return label
    return "Brand communication"

rows = []
for p in site:
    d = p.get("date", "")
    if not d or d < "2021-01-01":
        continue
    t = (p.get("title") or "").strip()
    if not t or JUNK.match(t) or len(t) < 12:
        continue
    rows.append({"winery": p["winery"], "date": d, "year": d[:4], "month": d[5:7],
                 "title": t, "type": classify(t), "url": p["url"],
                 "source": "Official winery news/blog"})

for p in iq:
    d = p.get("date", "")
    y = p.get("est_year")
    if d:
        year, month, exact = d[:4], d[5:7], True
    elif y:
        year, month, exact = str(y), "", False
    else:
        continue
    if year < "2021":
        continue
    t = p["title"].strip()
    rows.append({"winery": p["winery"], "date": d, "year": year, "month": month,
                 "title": t, "type": classify(t), "url": p["url"],
                 "source": "IQads (Romanian marketing press)" + ("" if exact else "; date estimated from the publisher's article sequence")})

# de-duplicate multilingual reposts of the same item
seen, uniq = set(), []
for r in sorted(rows, key=lambda x: (x["winery"], x["year"], x["month"], x["title"])):
    key = (r["winery"], r["year"], r["month"], re.sub(r"\W+", "", r["title"].lower())[:34])
    if key in seen:
        continue
    seen.add(key)
    uniq.append(r)

uniq.sort(key=lambda r: (r["winery"], r["year"], r["month"], r["title"]))
json.dump(uniq, open("timeline.json", "w"), ensure_ascii=False, indent=1)

print("timeline rows:", len(uniq))
byw = collections.Counter(r["winery"] for r in uniq)
byy = collections.Counter(r["year"] for r in uniq)
byt = collections.Counter(r["type"] for r in uniq)
print("\nby winery:")
for w, n in byw.most_common():
    yrs = collections.Counter(r["year"] for r in uniq if r["winery"] == w)
    print(f"  {w:24} {n:4}   " + " ".join(f"{y}:{c}" for y, c in sorted(yrs.items())))
print("\nby year:", dict(sorted(byy.items())))
print("\nby type:")
for t, n in byt.most_common():
    print(f"  {t:28} {n}")
