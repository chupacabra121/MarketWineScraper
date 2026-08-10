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
| **Selgros** | Full catalogue (~1,180 wines) | Azure Cognitive Search index. Wine categories are discovered from the `categoryPath` facet, not hardcoded. |
| **Mega Image** | Full catalogue (~220 wines) | GraphQL API. Needs a browser session. |
| **Penny (REWE)** | Small permanent range (~30 wines) | Server-rendered category pages. |
| **Kaufland** | Weekly offers only | No shoppable grocery catalogue in Romania; the weekly leaflet is published as structured HTML, so promo wines are scraped and tagged `offer_type=promo`. |
| Profi | none | No e-commerce catalogue; rejects automated requests (403). |
| Lidl | none | Online shop carries no wine. |
| La Cocoș, Supeco | none | Blocked at the edge (403), including from a real browser. |
| Froo, Unicarm | none | Marketing sites; no product listings. |
| Annabella | none | Product sitemap lists 18 items, none of them wine. |
| La Doi Pași | none | Franchise network; official site publishes a leaflet, not a catalogue. |
| Attack Discount | none | No public product listing found. |

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
different sizes comparable across retailers.

### Storage

SQLite with three tables:

- `products` — one row per (retailer, external_id), updated in place
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

## Notes on fragility

Scrapers break when sites change. The design pushes back where it cheaply can:

- Auchan and Selgros **discover their wine categories at runtime**, so a
  taxonomy change shows up as fewer categories, not zero products.
- Mega Image is queried with **our own GraphQL document** rather than the site's
  persisted-query hash, which changes on every frontend deploy.
- Adapters that return nothing fail loudly in the run summary, and every run is
  recorded in the `runs` table with its error.

The Selgros Azure Search query key and the Kaufland offer-page layout are the
most likely things to need updating; both are isolated to a single constant or
selector in their adapter.

## Tests

```bash
python -m pytest
```

Covers price/volume/ABV/colour/sweetness/grape parsing against real listing
titles, the non-wine filter, and storage behaviour including the
only-on-change price history rule.
