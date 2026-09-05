# Romanian wineries — marketing and leadership research

`Romanian_Wineries_Marketing_finalfinal.xlsx` is a competitive-research workbook on the
Romanian wine market: who runs these companies, who works in their marketing and sales
teams, what they are hiring for, and what they have campaigned on since 2021. It is a
separate workstream from the price scraper in this repository — nothing here reads or
writes `data/price-history.csv` — and it is committed for provenance, so the numbers in
the workbook can be traced back to the pages they came from.

## The eight sheets

| Sheet | Holds |
| --- | --- |
| **Winery Departments** | LinkedIn function breakdown per winery, plus a summary block reconciling the displayed counts against associated-member totals |
| **Open Positions** | Vacancies, internships and website/job-board reviews, one row per finding |
| **Campaign Evidence** | Interpreted marketing campaigns, 266 rows, each with a pattern reading and a source |
| **Campaign Timeline** | The dated 2021–2026 sweep, 510 rows, filterable by year, month and type |
| **CEO Research** | Leaders, titles, background, education, career domains and a standardized **Core discipline** |
| **Commercial People** | Named marketing and sales staff, 100 people, with a roster KPI block |
| **Commercial Type Split** | Marketing and sales headcount by type, computed from Commercial People |
| **Takeaways_Insights** | One summary row per winery: hiring takeaway, campaign pattern, confidence |

Everything numeric is formula-driven from the row-level sheets; nothing is a typed-in
total. The workbook recalculates clean (843 formulas, zero errors).

## Where the data came from

- **Winery news channels.** Each company's own site was crawled for its news, blog or
  events section — the WordPress REST and Shopify Atom feeds where they exist, the served
  HTML where they do not. `scripts/harvest/` holds the crawlers and
  `harvested/posts_all.json` the raw result.
- **IQads**, the Romanian marketing trade press, swept by brand for agency-signed
  campaigns. `harvested/posts_iqads_strict.json` keeps only the articles whose title names
  the winery, which is the filter that separates real coverage from a brand appearing in a
  sponsor list.
- **Company team pages**, where a winery publishes one. This is where the commercial
  rosters come from — Crama Oprișor publishes eight sales staff with direct e-mail
  addresses, Gitana and Avincis publish theirs, and most publish nothing.
- **BestJobs employer profiles**, which turned out to be the recruitment route these
  wineries actually use instead of a careers page.
- Targeted search for leadership, ownership and campaigns that no site publishes.

## What is missing, and why it is missing

Two gaps are structural rather than accidental, and the workbook says so in the cells
rather than leaving a reader to infer it.

**Coverage in Campaign Timeline is a finding, not a sample.** Seventeen wineries publish
dated news readable from outside; thirteen publish none at all. Crama Gîrboiu has 207
items and Purcari 110, while Crama Oprișor, Crama Rasova, Gitana and ten others have zero.
A low row count means the winery publishes little, not that it does little.

**The LinkedIn columns stop at the wineries captured on 2026-08-18.** Member counts and
department breakdowns for the fifteen wineries added later are blank, with the reason in
the note column and the nearest public substitute — a BestJobs alumni count — recorded
beside it. They were not estimated.

Beyond those, a zero in Commercial Type Split means no marketing or sales person could be
found in public sources, not that the function is unstaffed; and eleven names on the
61-company list — among them Vinexport, Bucium, Doina Vin, Rifco Import and Mastegariu
Florin — could not be resolved to any company at all. Their CEO Research rows say that
plainly and name what would unlock them.

## Dates that are estimates

IQads publishes no machine-readable date. Rows sourced from it carry a Year with a blank
Date, derived from that publisher's sequential article IDs and calibrated against four
articles whose real dates are known. The method was checked against three Crama Ceptura
articles held back from the calibration and reproduced their years. Treat those years as
approximate; every other date in the workbook is the publication date on the page.

## The scripts

`scripts/harvest/` crawls and classifies; `scripts/assemble/` holds the hand-written
research (`research.py`, `sweep_rows.py`, `companies.py`, `core_discipline.py`) and the
builders that wrote it into the workbook.

**These are a record of how the workbook was built, not a pipeline that rebuilds it.**
Each builder ran once, in sequence, against a workbook that the previous one had already
changed, so several carry row positions that were true only at that moment —
`build_companies.py` asserts the totals row is at 33, for instance. Read them to see how a
column was derived or to reuse a crawler; do not expect `python build.py` to regenerate
anything from the current file.

Recalculation needs LibreOffice Calc (`libreoffice-calc`), not just `libreoffice` — the
base package ships without the Calc filters and fails to load `.xlsx` at all.
