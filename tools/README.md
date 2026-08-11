# Reporting tools

```bash
python -m winescraper run --all       # -> data/wines.sqlite
python tools/build_workbook.py        # -> exports/romania-wine-market.xlsx
python tools/build_rankings.py        # -> /tmp/rankings.json
python tools/build_facts.py           # -> /tmp/brief_facts.json
npm install docx && node tools/build_issue_brief.js   # -> exports/*-issue-brief.docx
```

Run them in that order: the brief reads the two JSON files, so every figure in
the document traces back to one scrape rather than being retyped.

`build_facts.py` exists because it once did not. The facts file was produced by
an uncommitted script, so the brief kept quoting "7,513 listings" for three
re-scrapes after that stopped being true, and a claim that Penny's platform and
shelf prices "matched exactly across 27 shared wines" outlived the promotion
that made it true. Nothing in the brief's prose is a typed number now — the
collection date, the retailer spread, the entry-price floor and the Penny
comparison are all computed on each build.

`build_workbook.py` writes values, not formulas. Four derived columns over
6,750 rows is 27k formula cells, which could not be recalculated for
verification here, and an unverified formula is worse than a checked number.

The workbook's `Price by Wine` sheet and the brief's cross-retailer figures both
come from `winescraper.identity`, which reconstructs a `wine_key` so the same
wine is one row however each shop writes its name. That replaced an exact-wording
matcher: 868 wines carried by two or more retailers, against 226 before, and the
Purcari Chardonnay that nine shops sell is now one row rather than nine.

All three scripts apply the same cleaning the scraper does — blend descriptors
("Cuvée", "Cupaj") are not grape varieties, a year inside a brand name is not a
vintage, and a placeholder price of 9,999 lei is dropped — so a report built
from an older database matches one built from a fresh scrape.
