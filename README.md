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
- **One location per retailer**, configurable. Retailers that price per store
  record which store the price belongs to.
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

# what looks wrong in the stored data
python -m winescraper check
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
| **METRO** | Full catalogue (~1,040 wines) | Anonymous `searchdiscover`/`betty-variants` JSON APIs — no login despite the cash & carry model. Prices are VAT-inclusive and deposit-exclusive (`articleGross`); net price and SGR deposit kept in `raw`. National pricing, per-store assortment (default store: Băneasa, ~95% of the range). Grape/region/producer/vintage come structurally; ABV is not published. Many wines carry a 6-bottle minimum order. |
| **Penny via Bolt Food** (`penny_bolt`) | ~70 wines | Same Bolt Food API, PENNY Năsăud store. Measured against penny.ro on 27 shared wines: **median price difference +0.0%** — Bolt-Penny prices are shelf prices, so this mainly buys assortment (penny.ro lists only half the range). Glovo's Penny store was checked too and rejected: every one of its 70 products is also on Bolt, and its prices run ~0.50 lei higher (it folds the SGR deposit into the displayed price). |
| **Profi via Glovo** (`profi_glovo`) | ~70 wines | The only data route into Profi (own site rejects bots; ~1,700 stores, no web shop). Store page is server-rendered with the store/address ids and wine section ids embedded; tiles come from Glovo's public `content/partial` API. **Glovo prices include the 0.50-lei SGR deposit** (measured on Penny). |
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
on_promotion, offer_type, unit_price, price_per_litre, volume_l, abv, vintage,
colour, sweetness, sparkling, country, region, grape_varieties, in_stock,
category_path, url, image_url, location, scraped_at`

Attribute coverage varies by retailer because it depends on what each site puts
in its listings. Price, name, URL and volume are near-universal; grape variety
and region are dense on Auchan and sparse elsewhere. Fields that cannot be read
with confidence are left `NULL` rather than guessed.

`price_per_litre` is computed from price and volume, which makes bottles of
different sizes comparable across retailers. `wine_key` links listings of the
same wine across shops — see [Wine identity](#wine-identity).

### Storage

SQLite with three tables:

- `products` — one row per (retailer, external_id), updated in place, carrying
  the `wine_key` that links the same wine across retailers
- `price_observations` — appended **only when the price, promotion flag or stock
  status actually changes**, so history stays meaningful instead of growing by
  one identical row per product per run
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

This groups **763 wines carried by two or more retailers**, against 226 for the
exact-wording matcher it replaced. It is not infallible: identity is inferred
from text, so `winescraper check` reports any group whose prices span more than
2.5x, which is the shape of a wrong merge. On the current data that is five
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
