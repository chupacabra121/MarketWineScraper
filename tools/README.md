# Reporting tools

```bash
python -m winescraper run --all       # -> data/wines.sqlite
python tools/build_workbook.py        # -> exports/romania-wine-market.xlsx + /tmp/brief_facts.json
python tools/build_rankings.py        # -> /tmp/rankings.json
npm install docx && node tools/build_issue_brief.js   # -> exports/*-issue-brief.docx
```

Run them in that order: the brief reads the JSON the first two emit, so every
figure in the document traces back to one scrape rather than being retyped.

`build_workbook.py` writes values, not formulas. Four derived columns over 7.5k
rows is 30k formula cells, which could not be recalculated for verification
here, and an unverified formula is worse than a checked number.

Both scripts apply the same cleaning the scraper does — blend descriptors
("Cuvée", "Cupaj") are not grape varieties, a year inside a brand name is not a
vintage, and one 9999 placeholder price is dropped — so a report built from an
older database matches one built from a fresh scrape.
