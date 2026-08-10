# Reporting tools

Both scripts read a completed scrape and write to `exports/`.

```bash
python -m winescraper run --all            # populates data/wines.sqlite
python tools/build_workbook.py             # -> exports/romania-wine-market.xlsx
node   tools/build_issue_brief.js          # -> exports/*-issue-brief.docx  (needs `npm install docx`)
```

`build_workbook.py` writes values, not formulas. Four derived columns over 7.5k
rows is 30k formula cells, which no spreadsheet engine available here could
recalculate for verification, and an unverified formula is worse than a checked
number. Re-run the scraper and rebuild to refresh.

`build_issue_brief.js` reads `/tmp/brief_facts.json`, emitted by the workbook
build, so every figure in the brief traces to the same snapshot.
