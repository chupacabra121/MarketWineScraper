# MarketWineScraper

Scrapes wine listings and prices from Romanian supermarket, discounter and
cash & carry websites, normalises them into one comparable schema, and tracks
how prices move over time.

Scope decisions this build is based on:

- **Listing pages only** — no per-product detail crawl. Wine attributes are
  taken from structured API fields where a retailer exposes them, and otherwise
  parsed out of the product title.
- **Wine and sparkling** — still wine, sparkling, champagne, prosecco. No
  spirits, beer or cider.
- **One location per retailer**, configurable, recorded on every row. Retailers
  that price per store record which store; national e-commerce prices record
  `online`. `winescraper reenrich` fills it in for rows collected before an
  adapter declared one, without re-scraping — the location comes from how the
  scraper was configured, not from the page.
- Retailers with no online wine catalogue are registered as stubs that report
  why, rather than being silently dropped.

## Install

```bash
python -m pip install -e .
python -m playwright install chromium     # only needed for Mega Image and Selgros
```

Python 3.10+.

## Usage

```bash
# what can be scraped, and why the rest cannot
python -m winescraper list-sites

# one retailer
python -m winescraper run --site auchan

# everything scrapable, capped for a quick smoke test
python -m winescraper run --all --limit 50

# scrape without touching the database
python -m winescraper run --site carrefour --dry-run

# stored data
python -m winescraper stats
python -m winescraper export --site selgros --out exports/selgros.csv
python -m winescraper history --limit 20

# the same wine across retailers, however each of them writes its name
python -m winescraper wines --min-retailers 5
python -m winescraper wines --key purcari-chardonnay-alb-sec-0-75l-32377c

# what moved since the previous run
python -m winescraper changes

# apply the current parsing to rows already collected, without scraping
python -m winescraper reenrich

# what looks wrong in the stored data, and settling a finding for good
python -m winescraper check
python -m winescraper decide review wine --retailer auchan --id 454898 \
    --note "Moet & Chandon: real champagne, no colour or grape in the title"
python -m winescraper decisions
```

`run` writes to `data/wines.sqlite` and drops a timestamped CSV + JSONL per
retailer in `exports/`. Useful flags: `--limit N`, `--delay SECONDS`
(default 1s per host), `--no-cache`, `--format csv` / `none`, `--db`,
`--export-dir`, `--config`.

## Retailer status

Verified live on 2026-08-10.

| Retailer | Coverage | How |
| --- | --- | --- |
| **Auchan** | Full catalogue (~1,300 wines) | VTEX public catalog API. Richest source by far — grape, ABV, sweetness, country, region and producer all come back as structured fields. |
| **Carrefour** | Full catalogue (~1,400 wines) | Magento category pages, server-rendered; parsed from HTML. |
| **Freshful** | Full catalogue (927 wines) | Next.js JSON, no bot protection. Brand and unit price on every row; ABV on 95%. |
| **Sezamo** | Full catalogue (441 wines) | Rohlik-platform JSON API, no bot protection. Package size comes back structurally, so price-per-litre is exact on every row. |
| **Selgros** | Full catalogue (~1,180 wines) | Azure Cognitive Search index. Wine categories are discovered from the `categoryPath` facet, not hardcoded. |
| **Mega Image** | Full catalogue (~220 wines) | GraphQL API. Needs a browser session. |
| **Penny (REWE)** | Small permanent range (~30 wines) | Server-rendered category pages. |
| **Kaufland** | Weekly offers only | No shoppable grocery catalogue in Romania; the weekly leaflet is published as structured HTML, so promo wines are scraped and tagged `offer_type=promo`. |
| **Kaufland via Bolt Food** (`kaufland_bolt`) | Full range (~740 wines) | Bolt Food's public API for the Kaufland Tei store, Bucharest. **Delivery-platform prices**, typically at or above shelf — kept as a separate retailer key so they never mix with shelf data. `provider_id` configurable to point at another store. |
| **METRO** | Full catalogue (~1,040 wines) | Anonymous `searchdiscover`/`betty-variants` JSON APIs — no login despite the cash & carry model. Prices are VAT-inclusive and deposit-exclusive (`articleGross`); net price kept in `raw`, and the per-article deposit is published — the only source that does, which makes it the reference the packaging rule is checked against. National pricing, per-store assortment (default store: Băneasa, ~95% of the range). Grape/region/producer/vintage come structurally; ABV is not published. Many wines carry a 6-bottle minimum order. |
| **Penny via Bolt Food** (`penny_bolt`) | ~70 wines | Same Bolt Food API, PENNY Năsăud store. Measured against penny.ro on 27 shared wines: **median price difference +0.0%** — Bolt-Penny prices are shelf prices, so this mainly buys assortment (penny.ro lists only half the range). Glovo's Penny store was checked too and rejected: every one of its 70 products is also on Bolt, and its prices run ~0.50 lei higher (it folds the SGR deposit into the displayed price). |
| **Profi via Glovo** (`profi_glovo`) | ~70 wines | The only data route into Profi (own site rejects bots; ~1,700 stores, no web shop). Store page is server-rendered with the store/address ids and wine section ids embedded; tiles come from Glovo's public `content/partial` API. Prices were once assumed to fold in the 0.50-lei SGR deposit, from a measurement on Glovo's *Penny* store; the August 2026 shelf audit puts four Profi lines on our figures exactly and none 0.50 above, so this source is treated as deposit-exclusive like the rest. |
| **Supeco via Glovo** (`supeco_glovo`) | ~100 wines | Same Glovo base, Suceava store — the single Supeco on any delivery platform. Supeco's own site is blocked at the edge. |
| Profi (direct), Supeco (direct) | none | Sites reject/block automated requests — covered via the `*_glovo` adapters above instead. |
| Lidl | none | Online shop carries no wine; absent from Bolt Food and Glovo too. |
| La Cocoș | none | Blocked at the edge (403); absent from Bolt Food and Glovo (checked 2026-08-10). |
| Froo, Unicarm | none | Marketing sites; absent from Bolt Food and Glovo. |
| Annabella | none | Product sitemap lists 18 items, none of them wine; absent from both platforms. |
| La Doi Pași | none | Franchise network; leaflet-only site, absent from both platforms. |
| Atac (Auchan) | none | No public product listing; absent from Bolt Food and Glovo (checked 2026-08-10). |

Adding a retailer later is a drop-in: subclass `Adapter`, set `key`, implement
`scrape()`, and `@register` it.

## Data model

Each row is one wine at one retailer at one point in time:

`retailer, external_id, name, brand, producer, price, currency, list_price,
on_promotion, offer_type, unit_price, price_per_litre, deposit, volume_l, abv,
vintage, colour, sweetness, sparkling, country, region, grape_varieties,
in_stock, category_path, url, image_url, location, scraped_at`

Attribute coverage varies by retailer because it depends on what each site puts
in its listings. Price, name, URL and volume are near-universal; grape variety
and region are dense on Auchan and sparse elsewhere. Fields that cannot be read
with confidence are left `NULL` rather than guessed.

### The SGR deposit

`price` is what the retailer publishes. Almost none of them publish the 0.50-lei
deposit Romania charges on every bottle and PET of 0.1–3 litres, so `deposit`
records what has to be added to reach the till price, and everything the reports
show — `winescraper.pricing` — is the sum of the two. On a 2-litre wine at 12 lei
the deposit is 4% of the price, larger than most of the differences these numbers
get used to argue about.

Two questions decide it, and `winescraper/deposit.py` keeps them apart. Whether
the *container* carries a deposit is a packaging question: bottles and PET do,
bag-in-box does not, and at 3 litres the box is the rule rather than the
exception — 119 of the 122 three-litre wines here are boxes. That rule is read
off METRO, which publishes a deposit per article, and a test holds it to
reproducing 986 of those 990 figures. Whether the *retailer* has already added it
is a pricing question with a different answer per shop, so each is recorded with
its evidence; METRO's gross is `round(net × 1.21, 2)` on all 990 articles and
therefore carries no deposit, Freshful states "+ 0.5 Lei" outright, and the rest
are settled against the August 2026 shelf audit, which matches 111 of our prices
to the cent and only 2 at exactly 0.50 above.

Sezamo and Supeco (Glovo) are in neither group. No deposit is added to them and
`check` reports them as unsettled rather than guessing, so their prices may sit
0.50 low against the rest.

`price_per_litre` is computed from price and volume, which makes bottles of
different sizes comparable across retailers. `wine_key` links listings of the
same wine across shops — see [Wine identity](#wine-identity).

### Storage

SQLite with three tables:

- `products` — one row per (retailer, external_id), updated in place, carrying
  the `wine_key` that links the same wine across retailers
- `price_observations` — appended **only when the price, promotion flag or stock
  status actually changes**, so history stays meaningful instead of growing by
  one identical row per product per run. Each observation stores the name the
  wine had at the time: retailers recycle product ids, and reading the name off
  `products` when exporting rewrote past prices to match the present product
- `runs` — per-run bookkeeping and errors

## Politeness

Browser-like headers, 1 request/second per host with jitter, retries with
exponential backoff, and an on-disk response cache so repeat runs and debugging
do not re-hit the sites. `robots.txt` is treated as advisory rather than binding
(a deliberate choice for this build); the crawl is limited to public product
listings and stays well below a normal browsing rate. Raise `--delay` for a
gentler crawl.

Two sites fingerprint the TLS handshake and reject Python HTTP clients while
accepting a real browser, so Mega Image and Selgros are queried through
Chromium's network stack via Playwright.

## Configuration

Per-site settings via `--config settings.json`:

```json
{
  "selgros": { "market": 350 }
}
```

Selgros prices per depot; `market` selects which one (350 = București Berceni).
Every stored row records its `location`, so figures from different stores are
never silently mixed.

Freshful's `robots.txt` allows its category pages but disallows `/api/v2/shop`,
and only that API route paginates — the category page embeds just the first 60
wines. Following the configured "robots as advisory" posture, the adapter uses
the API by default. To stay strictly within `robots.txt` at the cost of coverage:

```json
{
  "freshful": { "respect_robots": true }
}
```

which limits the run to the 60 wines on the embedded first page.

### Third-party delivery platforms

`kaufland_bolt` reads Kaufland's range through Bolt Food rather than from
Kaufland itself. That trade has a clear shape:

- **What it buys:** the retailer's full assortment (~740 wines vs the ~5 in the
  weekly leaflet) for a chain with no web shop of its own.
- **What it costs:** the prices are the platform's, not the shelf's. Retailers
  and platforms commonly add a margin on delivery listings, so these rows are
  comparable with each other over time but not interchangeable with shelf
  prices. They therefore live under their own retailer key, with the platform
  and store named in `location` and `raw.source`.

The `BoltFoodStoreAdapter` and `GlovoStoreAdapter` base classes are
store-agnostic — another store on either platform is a subclass (or config
override) away.

### Platform survey (2026-08-10)

All four delivery platforms were swept for the retailers that have no direct
data source — Bolt Food (`deliverySearch` across 8 cities), Glovo (full
sitemap, 9,979 RO store pages), Wolt (full sitemap, 16,408 RO venues) and
Bringo (store-slug probes):

- **Lidl, La Cocoș, La Doi Pași, Annabella, Unicarm, Froo, Atac** are on none
  of them. Short of parsing weekly leaflets, they are unreachable today.
- **Profi** is on Glovo (71 cities — used by `profi_glovo`) and also on Wolt
  (~100 stores). Wolt is a viable alternative route if Glovo breaks.
- **Supeco** is on Glovo (Suceava — used by `supeco_glovo`) and also on
  Bringo (Carrefour Group's shopper platform), which serves a server-rendered
  wine listing with visible prices — an alternative route covering a
  different store.
- Wolt and Bolt both run their own dark-store groceries (Wolt Market, Bolt
  Market) that stock wine; adapters for those would be trivial subclasses if
  ever wanted.

## Tracking prices over time

One run is a snapshot. The value is in the second one, and everything here is
built for that: a price observation is written **only when the price actually
moves**, so a daily run adds a few hundred rows rather than 6,750 identical
ones, and `winescraper changes` reports what happened.

```
2026-08-10 → 2026-08-11

      1 price(s) moved   1 down, 0 up
      0 new listing(s)
      0 listing(s) no longer offered

biggest drops:
  penny             21.85 → 16.85       -23%  PELIN CARPATIN ROSE
```

`.github/workflows/scrape.yml` runs this daily. The database is **not**
committed — it is a build artefact, and a growing SQLite binary in git is a bad
trade. The price series is committed instead, as `data/price-history.csv`:

```bash
python -m winescraper history-file import   # before the scrape
python -m winescraper run --all
python -m winescraper history-file export   # after it
```

Importing first is what makes change detection work: from an empty database
every price looks new and nothing is ever recorded as having moved. The file is
text and append-mostly, so each day's commit is a readable diff of the prices
that actually changed. The workbook and the brief are rebuilt on every run and
uploaded as workflow artifacts rather than committed.

Products the latest run did not see drop out of the current prices. A delisted
wine is not a price, and without that rule it would sit in "latest" for ever at
whatever it last cost.

Two things only a second run can settle: Carrefour publishes no usable former
price, so a promotion there is invisible in a single snapshot but obvious as a
price drop between two; and the run-over-run drift check has nothing to compare
against until then.

## Decisions

Some findings are correct and will never stop being flagged. "Sampanie Moet &
Chandon" carries no colour, no grape and no sweetness, so it reaches the review
queue on every run and is wine on every run. Others are real faults the code
cannot see — Freshful lists two different Tohani wines under identical titles.
Either way, a queue that repeats itself is a queue nobody reads.

`decisions.jsonl` is where the answer goes. It is committed: these are human
judgements about a catalogue, not derived data, so they belong next to the code
rather than in a database that gets rebuilt.

```bash
winescraper decide review wine --retailer auchan --id 454898 --note "real champagne"
winescraper decide 'wine spread' noted --wine tohani-feteasca-neagra-rosu-sec-0-75l-4b8943 \
    --note "Freshful lists two unrelated Tohani wines under identical titles"
winescraper decide 'not wine' exclude --retailer carrefour --id 99 --note "fizzy juice"
```

| verdict | effect |
| --- | --- |
| `wine` | the flag was wrong; stop reporting it |
| `exclude` | the flag was right and the listing does not belong — dropped from exports and every report |
| `noted` | real but unfixable here; stop reporting it, keep the reason |

`exclude` is a denylist anyone can extend without touching the filter code. The
file is append-only, so revising a judgement means adding a line and the earlier
one stays on the record. `winescraper check --all` shows what has been settled.

## Wine identity

Thirteen retailers write the same bottle thirteen ways. Purcari's Chardonnay is
sold by nine of them, as "Vin alb sec Purcari Chardonnay", "PURCARI CHARDONNAY
SEC 0,75", "PURCARI 1827 Chardonnay de Purcari Vin Alb Sec SGR 0,75 L",
"Purcari chardonnay Vin alb sec 750 ml" and five more. No retailer publishes a
barcode and every product id is per-shop, so nothing in the source data connects
them.

`winescraper.identity` reconstructs the connection and stores it as a
**`wine_key`** — a readable, deterministic slug such as
`purcari-chardonnay-alb-sec-0-75l-32377c`. The same wine gets the same key in
every run, so price history survives a re-scrape.

```bash
python -m winescraper wines --min-retailers 5
python -m winescraper wines --key purcari-rose-purcari-cabernet-sauvignon-merlot-rose-sec-0-75-8da370
```

It works in three steps:

- **Expand.** Cash & carry titles are abbreviated to the point of being another
  language — `CAB SAUV`, `FET N`, `TAM ROM`, `PIN GRIG` — so those are restored
  first. Deposit markers, appellation codes, ABV and packaging words are dropped.
- **Separate identity from description.** What remains splits into the *anchor*
  (the producer's name for this wine) and attributes recorded in their own right:
  grape, colour, sweetness, volume. Retailers disagree about which attributes to
  print, not about the anchor. Brands are learned from the retailers that publish
  a brand field and then read out of the titles of the six that do not — 1,064
  listings that were previously unmatchable.
- **Resolve the gaps.** An unstated attribute is unknown, not absent, so it is
  resolved against the other listings of the same anchor — but only where they
  agree. If the anchor covers a Chardonnay and a Merlot, a listing naming
  neither keeps its own identity rather than being guessed into one.

Three rules exist because the naive version got them wrong:

- **A tier word is part of the name.** Tohani Premium costs 2.5x plain Tohani,
  and Villa Vinea Classic is not Villa Vinea Selection. But "Premium" with no
  brand to qualify identifies nothing, so it never forms an identity alone.
- **A colour can be the range name.** "Roșu de Purcari" at 110 lei is not
  Purcari Cabernet Sauvignon at 39. Where some shops name the range and others
  do not, what separates "two names for one wine" from "two wines" is who sells
  them: a shop lists a given wine once, so if the same retailer appears on both
  sides they are different wines.
- **A vintage matters when it is old.** Cotnari sells a 1994 Fetească Albă at
  203 lei beside an ordinary one at 22, so the year is the product. A 2023
  Purcari Chardonnay and an unlabelled one are the same wine on the same shelf,
  and treating the year as identity there would split seven retailers into eight.

Two more rules cover what the text cannot settle on its own. Auchan sells
"Pelin Carpatin ... de Urlati" and METRO sells the same bottle as "Pelin
Carpatin"; Urlați is where the wine comes from, not which wine it is, and no
rule can tell provenance from a range name by looking at the word. Who sells it
can: a shop lists a given wine once, so listings that differ only in a naming
detail are one wine when they come from entirely different shops, and two wines
when any shop appears on both sides. Where even that is inconclusive the prices
decide — Selgros' "LOPEZ DE HARO CRIANZA" at 40 lei and METRO's plain "LOPEZ DE
HARO" at 139 pass every textual test, and only the gap says they differ. Price
is used **only** for these two circumstantial steps, never where the titles are
clear, or a sale would rewrite the key.

This groups **868 wines carried by two or more retailers**, against 226 for the
exact-wording matcher it replaced. It is not infallible: identity is inferred
from text, so `winescraper check` reports any group whose prices span more than
2.5x, which is the shape of a wrong merge. On the current data that is four
groups, and one of them is a genuine Auchan duplicate listed at both 34.99 and
109.99 lei.

## Data quality

Two things can be wrong in a row: the price, and whether the thing is wine at
all. Both have been wrong in this project, so both are checked rather than
assumed. `winescraper check` runs the checks below, and a `run` performs them
automatically at the end unless `--no-check` is passed.

**Is the price right?** Every site that publishes its own price per litre gives
an independent answer, computed server-side from the same package size and price
we parsed. Disagreement means we misread the price, the volume, or both. On the
current run 6,743 of 6,749 rows agree exactly; the six that do not are all
Freshful listings whose own title and unit-price label contradict each other.

Cheap sanity limits back this up — a price per litre below 5 RON/L or above
4,000, or twelve times its retailer's median — but those only bracket a
plausible range. The unit-price cross-check is the only one that tests a scraped
price against the retailer.

**Is it wine?** The wine aisle reliably contains things that are not wine:
corkscrews, vinegar, alcohol-free "sparkling", fruit wine, RTD cocktails,
children's fizzy juice, and — in one Kaufland listing — a wheat beer. These are
excluded by name, and every rule carries the real listing that motivated it as a
test case.

A denylist only rejects what someone has already seen, so there is a second,
opposite check. Each row is scored on independent wine signals: a wine word in
the title, a parsed colour, a grape, a sweetness, an ABV of 8% or more. Rows
scoring below two go into a **review queue** — about 2.7% of a run, small enough
to read. That queue is what found fruit wine ("Vin de Coacaze") and
de-alcoholised wine ("Spumant Zero Alcool"); no hand-written rule was looking
for either.

**Did the run actually finish?** Adapters log-and-continue on a failed page so
one bad response cannot lose a whole run — which once meant Mega Image returned
146 of 218 wines and reported success. Three things now make that visible:

- adapters that know their retailer's own total refuse to publish a run below
  90% of it (`MIN_COVERAGE`)
- warnings are counted per adapter, so a run that recovered from failures is
  marked degraded in the summary and exits non-zero
- each retailer is compared against its own previous run, and a swing over 10%
  is reported — the check that needs no prediction of what might break

## Notes on fragility

Scrapers break when sites change. The design pushes back where it cheaply can:

- Auchan and Selgros **discover their wine categories at runtime**, so a
  taxonomy change shows up as fewer categories, not zero products.
- Mega Image is queried with **our own GraphQL document** rather than the site's
  persisted-query hash, which changes on every frontend deploy.
- Selgros' Azure Search query key rotates. When the proxy refuses the configured
  key — reported, unhelpfully, as `HTTP 400: Missing product ID` — the adapter
  **reads the current key off the live page** by watching the site make its own
  search request, and retries.
- Adapters that return nothing fail loudly in the run summary, and every run is
  recorded in the `runs` table with its error.

The Kaufland offer-page layout is the most likely thing to need updating, and it
is isolated to a single selector in its adapter.

## Tests

```bash
python -m pytest
```

Covers price/volume/ABV/colour/sweetness/grape parsing against real listing
titles, the non-wine filter, the data checks, and storage behaviour including
the only-on-change price history rule.

Every string in the parsing and filter tests is a listing that was actually
collected from a wine category, and every bad row found in a run is added here
before it is fixed. That is what stops a fix from being quietly undone: the
Kaufland volume rule, the alcohol-free rule that used to match `12.0% alcool`,
and the producer "Aurelia Visinescu" not being read as a cherry all survive as
tests rather than as remembered intentions.

## The German study: PET and bag-in-box

A second, self-contained study lives in `winescraper/de/`. It asks a narrower
question than the Romanian scraper does — **what does wine in a PET bottle or a
bag-in-box cost in German retail** — and answers it with its own vocabulary, its
own deposit rules and its own Excel deliverable.

```bash
python -m pip install -e .              # brotli is now a hard dependency
python -m winescraper.de.run --workbook
```

`run` writes `exports/germany/`: the in-scope rows, the full catalogue they were
separated from, JSONL, and the workbook in **both German and English** —
`Deutscher-Weinmarkt-PET-BagInBox.xlsx` and
`German-Wine-Market-PET-BagInBox.xlsx`. Same sheets, same rows, same numbers;
only the wording differs. `--language en` builds just one.

A *Private label or not* sheet judges each of those 27 wines and links a source
for every claim. The judgements are hand-collected and committed in
`winescraper/de/brands.py`, in the same spirit as `decisions.jsonl` on the
Romanian side — a human read the sources, and the file records what they read.
Three kinds of evidence are used, strongest first: the identical product sold by
unrelated retailers (a private label is exclusive by definition), the bottler
presenting the brand as its own, and the responsible food business operator that
LMIV Art. 8/9 requires and Art. 14 makes a distance seller publish before
purchase. That last field is the one people misread: naming a winery does *not*
rule out a private label, because Peter Mertes, Zimmermann-Graeff & Müller and
Einig-Zenzen fill both their own brands and retailers' labels and appear as
operator either way. Six of the 27 are private labels, fifteen are other
companies' brands, and six could not be established — which the sheet says
rather than guessing.

The *Cheapest three per store* sheet ranks by EUR/litre and states its filters
rather than applying them quietly: mulled wine is held out (it sells in the same
10-litre box at a third of the litre price and would take first place at METRO
and WirWinzer), so are multi-packs (an honest per-litre price for something you
cannot buy one of), and METRO stays in but is marked *net*. Everything a filter
removed that would otherwise have ranked is listed underneath with the reason,
so the sheet cannot quietly flatter a store.

Every user-visible string lives in `winescraper/de/text.py` rather than in the
sheet code, and `tests/test_de_text.py` holds the two vocabularies to the same
shape — a footnote added to one language has to be added to the other, and a
German string left sitting in the English column fails the suite. Trade and
legal terms are not translated, because translating them makes them
unfindable: *Pfand*, *VerpackG*, *Bag-in-Box*, *Literflasche*, *Grundpreis*
keep their German names and are glossed on first use.

Other useful flags: `--source lidl`, `--limit N`, `--delay`, `--no-cache`,
`--no-check`, `--no-pet-probe`.

### What it found

Verified live on 2026-08-14. **4,176 wines collected, 293 of them bag-in-box.**

- **Bag-in-Box is a real German format with a settled price structure**, carried
  by every reachable chain except EDEKA. The 3-litre box is the standard
  gebinde — 211 of the 259 still-wine offers. Prices run **4.99–39.00 €**
  (median 11.49), which is **1.66–13.00 €/litre, median 3.83**.
- **The entry price is 4.99 € for 3 litres**, at both Lidl and Globus. That is
  1.66 €/litre, or **1.25 € per 0.75-litre-bottle equivalent** — the floor of
  the German market, and it is now confirmed by two chains rather than one.
- **Wine in PET bottles is not sold in German retail.** Not one offer in 4,176.
  This is a null result, so it is evidenced twice over — see below.
- **Bag-in-box is a thin slice of a supermarket range but a deep one at a
  specialist.** Globus lists 2,221 wines and 26 boxes (1.2%); Netto lists 170
  and 32 (19%); Wein Schäpers sells nothing else.
- **The box undercuts the bottle it competes with.** The German 1-litre
  Literflasche — the entry format bag-in-box is priced against — runs a median
  4.99 €/litre against the 3-litre box's 3.83.
- **The cheapest wine per litre is neither format.** It is the 1.5-litre
  Getränkekarton at Lidl, 1.99 € for 1.5 l (1.33 €/l).

Ranking each store's three cheapest boxes per litre (the *Cheapest three per
store* sheet) puts the channels in an order that is not the expected one:

| Store | Cheapest box | EUR/l | per 0.75 l |
| --- | --- | ---: | ---: |
| METRO *(net, B2B)* | Cerro de La Cruz, 10 l | 1.42 | 1.06 |
| Globus | BIB Tinto de la Tierra de Castilla, 3 l | 1.66 | 1.25 |
| Lidl | Vino Tinto Tempranillo, 3 l | 1.66 | 1.25 |
| Combi | Terra Molino Airén/Sauvignon, 3 l | 1.93 | 1.45 |
| Wein Schäpers | Hauswein Rosé, 3 l | 2.37 | 1.78 |
| NORMA | Winebox Müller-Thurgau, 3 l | 3.00 | 2.25 |
| Weinfreunde | Biqueirão Branco, 5 l | 3.16 | 2.37 |
| Netto | Maybach Grauer Burgunder, 3 l | 3.83 | 2.87 |
| WirWinzer | Bag-in-Box Riesling, 3 l | 4.13 | 3.10 |

The spread *inside* the discount channel is wider than the gap between
channels: Netto's entry box costs 2.3× Lidl's, because Netto carries no
own-brand box at all — its whole bag-in-box range is Maybach, Bree, Grand Sud
and Weinhaus Müller. A specialist (Schäpers, 2.37 €/l) undercuts two of the
three discounters.

Checking who owns those brands explains the spread. **The two cheapest
consumer sources reach their price by owning the label, and the dearest
discounter by not owning one.** Lidl's three entry boxes carry no producer
brand and are filled by three different wineries — Bodegas Isidro Milagro,
Félix Solís and Vineris — which is what a retailer-controlled specification
looks like. Schäpers' Hauswein line is the same pattern at a specialist.
Netto's whole box range is Peter Mertes' Maybach and Bree, bought as branded
goods, and it sits at 3.83 €/l.

### Coverage: every chain on the Wikipedia list

Each chain on [*List of supermarket chains in
Germany*](https://en.wikipedia.org/wiki/List_of_supermarket_chains_in_Germany)
was checked individually, along with the beverage chains and wine specialists
that carry the formats.

| Retailer | Channel | Wines | Boxes | How |
| --- | --- | --- | --- | --- |
| **Globus** | Hypermarket | 2,221 | 26 | Shopware 6, the full wine catalogue across four colour categories. The largest source here and the only complete supermarket range reachable. Files boxes in the ordinary categories, marked only by "BIB" in the product name. |
| **Lidl** | Discounter | 635 | 25 | Public search API at `lidl.de/q`. States the container in the title, publishes its own price per litre, and exposes a `Flaschengröße` facet that reaches the large formats directly. |
| **NORMA** | Discounter | 458 | 40 | norma24.de, the group's online shop. schema.org microdata gives price and SKU structurally. |
| **Combi** | Hypermarket | 455 | 4 | Bartels-Langness delivery shop; stands in for famila, whose own sites carry no catalogue. |
| **Netto Marken-Discount** | Discounter | 170 | 32 | Intershop `ViewMMPStandardCatalog-Browse`, whole wine category in one call at `PageSize=500`. Needs the homepage's cookies first — every path is a 403 without them. |
| **EDEKA** | Supermarket | 67 | 0 | edeka24.de. Categories render 30 products and page by scrolling with no working page parameter, so coverage is the first 30 of each. |
| **METRO** | Cash & carry | 24 | 20 | Same `searchdiscover` API as the Romanian sibling, store 00015. **Net trade prices** — the German site returns `sellingPriceInfo: null` anonymously, so only the search response's ex-VAT price is available. Never mixed with consumer figures. |
| **Wein Schäpers** | Specialist | 66 | 66 | Shopware 6 bag-in-box category. |
| **WirWinzer** | Specialist | 66 | 66 | Winery-direct marketplace; boxes sold in multi-packs. |
| **Weinfreunde** | Specialist | 14 | 14 | Hawesko group's volume shop; stands in for hawesko.de, which blocks us. |

Twenty-seven more were checked and yielded nothing. The reasons are not
interchangeable, and the workbook's *Nicht erfasst* sheet keeps them apart:

- **No online catalogue at all** (the majority): ALDI Nord, Penny, tegut, HIT,
  famila, Selgros, Netto (Salling), Alnatura, Bio Company, CAP, nahkauf, nah &
  gut, nah & frisch — plus the beverage chains **Getränke Hoffmann, trinkgut
  and Fristo**, which is where bag-in-box sells hardest. These run a store
  finder and a weekly leaflet; the price exists only on the shelf. That is a
  fact about German grocery retail, not a scraping failure, and it is the
  single biggest limit on this study.
- **Catalogue exists, datacentre addresses refused** (HTTP 403): Kaufland,
  REWE, Marktkauf, ALDI SÜD, Hawesko, Vinatis.
- **Reachable, prices not in the response**: Amazon.de, Müller, Vinello.

### The Pfand, and why PET would have one

Germany's single-use deposit is 0.25 €, and since 1 January 2022 it applies to
**every** single-use plastic beverage bottle of 0.1–3.0 litres regardless of
contents — which is what would bring wine in PET into the scheme. Bag-in-box is
exempt under VerpackG §31(4) as an *ökologisch vorteilhafte* container, being a
carton around a foil bladder; so is the Getränkekarton, the pouch, and single-use
glass. For every offer in this study, therefore, shelf price and till price are
the same. `winescraper/de/packaging.py` keeps the container question and the
deposit question apart, exactly as the Romanian `deposit.py` does for SGR.

### Establishing a null result

Half the brief was PET, and the collection returned none. An absence produced by
a filter is a weak claim, so it rests on two independent legs:

- **A census.** Every one of the 4,176 collected wines was classified. None is
  in PET. Globus alone contributes 2,221 examined listings.
- **A targeted search.** `winescraper/de/petprobe.py` asks Lidl and METRO for it
  by name — seven phrasings a German retailer would use — and records what came
  back. 357 products, 5 genuinely PET, **none of them wine**: the PET hits are
  raspberry syrup and Acqua Panna.

The supply side confirms the shape: Flaschenland and comparable suppliers sell
empty 250 ml and 750 ml PET wine bottles to wineries and caterers, unfilled. In
German retail the large gebinde is the box and the small one is glass; PET holds
no shelf position between them.

### Reading the container off a listing

`packaging.py` classifies from title, description, category and image alt text,
in that order of preference, and leaves the field `unknown` when nothing says —
which is the common case for an ordinary 0.75 L bottle and is reported as such
rather than being counted as glass.

One rule is inferred rather than read, and it is measured rather than assumed:
**at three litres and above the container is a bag-in-box.** Of the 216
three-litre wines collected, 191 say so outright, 24 name no container, and
exactly one is a bottle — a Prosecco Jeroboam at METRO that writes "3 l Flasche"
and is caught by the glass rule first. At five litres it is 28 of 28. The
threshold stops at three: two-litre German wine is routinely glass, and
extending the rule downwards would start inventing boxes.

### Data quality

The same posture as the Romanian side: a field that cannot be read is left null,
and a price is checked against the retailer that published it.

German price-labelling law requires a Grundpreis, so most listings advertise
their own price per litre — computed server-side from the same price and size we
parsed. `winescraper.de.validate` compares it against ours on every row that has
both. **4,108 of 4,176 rows cross-check, and all of them agree.**

That check earned its place five times over. Every one of these was invisible in
the output and found only by the retailer's own arithmetic:

- **Wein Schäpers** prints price and Grundpreis in adjacent elements; the parser
  took the cheaper of the two and recorded a 15.17 € box at 5.06 €.
- **Globus** renders a discounted price as `3,49 € 2,49 €` inside one element,
  struck-through first. Taking the first was wrong on exactly the rows where
  being wrong matters most. The current price is now the one that reproduces the
  shop's own per-litre figure.
- **NORMA** publishes `itemprop="price" content="4.2"`. The price parser required
  two decimal places and fell through to an integer match, reading it as 4 — a
  20-cent error on every one-decimal price in the shop.
- **Lidl** reports a six-bottle Bordeaux case as 4.5 litres, which the
  size-implies-a-box rule read as a large format. Pack size and unit size are now
  kept apart.
- **WirWinzer**'s `data-bottle-count` counts boxes on one listing and 0.75-litre
  equivalents on the next — "4er Paket … (12 L)" reports 4, "BiB-Paket … (9 L)"
  reports 12. Dividing blindly produced a 0.75-litre bag-in-box. The count is now
  trusted only when it divides out to something that could be a box.

Two further traps are recorded as comments where they bite. Combi mistypes one
listing's size as "750 l"; the size is correctly rejected, but the fallback then
read the "/1 l" of the unit price as a one-litre bottle, so a source that names
the volume field is now believed even when its answer is `None`. And Combi's own
category path is "bier-wein-spirituosen", which the non-wine filter rejected —
dropping the entire aisle it was meant to describe.

Glühwein, Sangria, sparkling and dessert wine are collected but held out of the
still-wine figures: Glühwein sells in the same 10-litre box at a third of the
litre price, and averaging the two would describe neither.

`data/germany-pet-bib.csv` and `data/germany-wine-all.csv` are committed for the
same reason `price-history.csv` is — they are a dated observation of a market,
and re-running next month measures next month rather than reproducing this. The
workbook is not: it is rebuilt from them.
