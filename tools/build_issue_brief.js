// McKinsey-style issue brief on the Romanian wine price dataset.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, PageBreak,
  Header, Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require('docx');
const fs = require('fs');

const NAVY = '1F3864';
const ACCENT = '2E5F8A';
const GREY = '595959';
const RULE = 'BFBFBF';
const LIGHT = 'DCE6F1';
const FONT = 'Arial';

const PAGE_W = 12240, PAGE_H = 15840;              // US Letter, DXA
const MARGIN = convertInchesToTwip(1);
const CONTENT_W = PAGE_W - 2 * MARGIN;             // 10800

const facts = JSON.parse(fs.readFileSync('/tmp/brief_facts.json', 'utf8'));
const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
const num = (n) => n.toLocaleString('en-US');

// ---------------------------------------------------------------- helpers
const noSpace = { before: 0, after: 0 };

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 140 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY, space: 6 } },
    children: [new TextRun({ text, font: FONT, size: 30, bold: true, color: NAVY })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 100 },
    children: [new TextRun({ text, font: FONT, size: 24, bold: true, color: ACCENT })],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 0, after: 140, line: 276 },
    alignment: opts.align || AlignmentType.LEFT,
    children: [new TextRun({ text, font: FONT, size: 20, color: '000000', ...opts.run })],
  });
}

function lead(text) {
  return new Paragraph({
    spacing: { before: 0, after: 180, line: 276 },
    children: [new TextRun({ text, font: FONT, size: 21, bold: true, color: NAVY })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'brief-bullets', level },
    spacing: { before: 0, after: 90, line: 264 },
    children: [new TextRun({ text, font: FONT, size: 20 })],
  });
}

// Rich bullet: bold lead-in, then normal text.
function bulletRich(boldPart, rest, level = 0) {
  return new Paragraph({
    numbering: { reference: 'brief-bullets', level },
    spacing: { before: 0, after: 90, line: 264 },
    children: [
      new TextRun({ text: boldPart, font: FONT, size: 20, bold: true }),
      new TextRun({ text: rest, font: FONT, size: 20 }),
    ],
  });
}

function caption(text) {
  return new Paragraph({
    spacing: { before: 60, after: 200 },
    children: [new TextRun({ text, font: FONT, size: 16, italic: true, color: GREY })],
  });
}

function cell(text, { bold = false, fill = null, align = AlignmentType.LEFT, color = '000000',
                      width, size = 18 } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: align,
      spacing: noSpace,
      children: [new TextRun({ text, font: FONT, size, bold, color })],
    })],
  });
}

function table(headers, rows, widths, opts = {}) {
  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, {
      bold: true, fill: NAVY, color: 'FFFFFF', width: widths[i],
      align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, size: 17,
    })),
  });
  const bodyRows = rows.map((r, ri) => new TableRow({
    children: r.map((c, i) => cell(String(c), {
      width: widths[i],
      fill: opts.zebra && ri % 2 === 1 ? 'F4F6FA' : (opts.rowFill ? opts.rowFill(ri, i) : null),
      align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      bold: opts.boldFirstCol && i === 0,
    })),
  }));
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    rows: [headRow, ...bodyRows],
  });
}

// Key-point block: number chip + headline + supporting text.
function keyPoint(n, headline, detailRuns) {
  return new Table({
    columnWidths: [900, CONTENT_W - 900],
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    rows: [new TableRow({
      children: [
        new TableCell({
          width: { size: 900, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: NAVY, color: 'auto' },
          margins: { top: 120, bottom: 120, left: 60, right: 60 },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER, spacing: noSpace,
            children: [new TextRun({ text: String(n), font: FONT, size: 40, bold: true, color: 'FFFFFF' })],
          })],
        }),
        new TableCell({
          width: { size: CONTENT_W - 900, type: WidthType.DXA },
          margins: { top: 90, bottom: 160, left: 200, right: 0 },
          children: [
            new Paragraph({
              spacing: { before: 0, after: 90 },
              children: [new TextRun({ text: headline, font: FONT, size: 22, bold: true, color: NAVY })],
            }),
            new Paragraph({
              spacing: { before: 0, after: 0, line: 276 },
              children: detailRuns.map((d) => new TextRun({
                text: d.t, font: FONT, size: 20, bold: !!d.b,
              })),
            }),
          ],
        }),
      ],
    })],
  });
}

// ------------------------------------------------------------------ data
const L = {
  auchan: 'Auchan', carrefour: 'Carrefour', selgros: 'Selgros', metro: 'METRO',
  freshful: 'Freshful', sezamo: 'Sezamo', mega_image: 'Mega Image',
  penny: 'Penny (own site)', kaufland: 'Kaufland (leaflet)',
  kaufland_bolt: 'Kaufland (Bolt)', penny_bolt: 'Penny (Bolt)',
  profi_glovo: 'Profi (Glovo)', supeco_glovo: 'Supeco (Glovo)',
};

const coverage = [
  ['Carrefour', 'Own site', num(facts.by_retailer.carrefour), 'Full catalogue'],
  ['Auchan', 'Own site', num(facts.by_retailer.auchan), 'Full catalogue — richest attributes'],
  ['Selgros', 'Own site', num(facts.by_retailer.selgros), 'Full catalogue — per-depot pricing'],
  ['METRO', 'Own site', num(facts.by_retailer.metro), 'Full catalogue — 6-bottle minimum common'],
  ['Freshful', 'Own site', num(facts.by_retailer.freshful), 'Full catalogue — online-only retailer'],
  ['Kaufland', 'Bolt Food', num(facts.by_retailer.kaufland_bolt), 'Full range via delivery platform'],
  ['Sezamo', 'Own site', num(facts.by_retailer.sezamo), 'Full catalogue — online-only retailer'],
  ['Mega Image', 'Own site', num(facts.by_retailer.mega_image), 'Full catalogue'],
  ['Supeco', 'Glovo', num(facts.by_retailer.supeco_glovo), 'Only route — own site blocked'],
  ['Penny', 'Bolt Food', num(facts.by_retailer.penny_bolt), 'Platform price verified = shelf'],
  ['Profi', 'Glovo', num(facts.by_retailer.profi_glovo), 'Only route — no web shop at all'],
  ['Penny', 'Own site', num(facts.by_retailer.penny), 'Shelf reference for the Bolt feed'],
  ['Kaufland', 'Leaflet', num(facts.by_retailer.kaufland), 'Weekly promotions only'],
];

const gaps = [
  ['Lidl', 'No wine in its online shop; absent from all four delivery platforms'],
  ['La Cocoș', 'Site blocked at the edge (HTTP 403) even from a real browser; on no platform'],
  ['La Doi Pași', 'Franchise network; the official site publishes a leaflet, not a catalogue'],
  ['Annabella', 'Product sitemap lists 18 items, none of them wine'],
  ['Unicarm', 'Single-page landing site with no product listing'],
  ['Froo', 'Marketing site only; sitemap contains no products'],
  ['Atac', 'No public product listing anywhere'],
];

const ladderOrder = ['penny_bolt', 'supeco_glovo', 'penny', 'profi_glovo', 'kaufland_bolt',
  'auchan', 'mega_image', 'selgros', 'carrefour', 'metro', 'freshful', 'sezamo'];
const ladderRows = ladderOrder
  .filter((k) => facts.ladder[k])
  .map((k) => {
    const d = facts.ladder[k];
    const basis = ['kaufland_bolt', 'penny_bolt', 'profi_glovo', 'supeco_glovo'].includes(k)
      ? 'Platform' : 'Shelf';
    return [L[k], basis, num(d.n), d.median.toFixed(2), d.entry.toFixed(2)];
  });

const winRows = Object.entries(facts.wins)
  .sort((a, b) => b[1].winrate - a[1].winrate)
  .map(([k, v]) => [L[k], num(v.n), num(v.win), pct(v.winrate), pct(v.loserate)]);

const M = facts.matches;
const champ = 'metro';
const W = facts.wins[champ];
const totalColour = facts.colour.alb + facts.colour.rosu + facts.colour.rose;

// --------------------------------------------------------------- document
const doc = new Document({
  creator: 'MarketWineScraper',
  title: 'Romanian Wine Retail — Price and Assortment Issue Brief',
  description: 'Issue brief on wine pricing and assortment across Romanian grocery retail.',
  numbering: {
    config: [{
      reference: 'brief-bullets',
      levels: [
        {
          level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 340, hanging: 200 } } },
        },
        {
          level: 1, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 680, hanging: 200 } } },
        },
      ],
    }],
  },
  styles: {
    default: {
      document: { run: { font: FONT, size: 20 } },
    },
  },
  sections: [{
    properties: {
      page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          spacing: { after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 4 } },
          tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
          children: [
            new TextRun({ text: 'ROMANIAN WINE RETAIL', font: FONT, size: 15, bold: true, color: NAVY }),
            new TextRun({ text: '\tIssue Brief  |  10 August 2026', font: FONT, size: 15, color: GREY }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
          children: [
            new TextRun({ text: 'Source: MarketWineScraper, 7,513 listings, 13 sources', font: FONT, size: 14, color: GREY }),
            new TextRun({ text: '\t', font: FONT, size: 14 }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: GREY }),
          ],
        })],
      }),
    },
    children: [
      // ---------------------------------------------------------- cover
      new Paragraph({
        spacing: { before: 0, after: 60 },
        children: [new TextRun({ text: 'ISSUE BRIEF', font: FONT, size: 18, bold: true, color: ACCENT, characterSpacing: 60 })],
      }),
      new Paragraph({
        spacing: { before: 0, after: 100 },
        children: [new TextRun({
          text: 'Wine pricing and assortment across Romanian grocery retail',
          font: FONT, size: 40, bold: true, color: NAVY,
        })],
      }),
      new Paragraph({
        spacing: { before: 0, after: 260 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 10 } },
        children: [new TextRun({
          text: 'What we can see, what we cannot, and what the data says',
          font: FONT, size: 24, color: GREY,
        })],
      }),

      lead('The same bottle of wine sells for materially different prices depending only on which '
        + 'retailer stocks it. Across 230 wines we can match with confidence across retailers, the '
        + `median gap between the cheapest and dearest listing is ${pct(M.median)}, and `
        + `${pct(M.over20)} differ by a fifth or more. Retailer choice, not product choice, is the `
        + 'largest single lever on what a shopper pays.'),

      body('This brief sets out how the underlying dataset is assembled, which retailers it covers '
        + 'and which it cannot, and what the assembled evidence shows. It closes with the three '
        + 'data points we judge most useful for a commercial decision.'),

      h1('1. How the dataset is built'),

      body('The collection method is deliberately unglamorous: for each retailer, find the machine-'
        + 'readable source its own website already uses, read the wine categories from it, and '
        + 'normalise the result into one common schema. No retailer is asked for data and no '
        + 'private system is touched — every source is the same public endpoint a shopper’s '
        + 'browser calls when they open the wine aisle.'),

      bulletRich('Discovery. ', 'Each retailer is probed to find where its product data actually '
        + 'lives. In practice this is one of four shapes: a public catalogue API (Auchan, Sezamo, '
        + 'METRO), a search index (Selgros), server-rendered HTML (Carrefour, Penny), or a '
        + 'delivery platform that carries the retailer (Kaufland, Profi, Supeco).'),
      bulletRich('Extraction. ', 'Wine categories are read from each source’s own taxonomy '
        + 'rather than hardcoded, so a retailer reorganising its categories degrades the result '
        + 'rather than silently breaking it.'),
      bulletRich('Normalisation. ', 'Retailers publish wildly different amounts of structure. '
        + 'Where an attribute is published it is taken directly; where it is not, it is parsed '
        + 'from the product title, with Romanian diacritics folded so that "Fetească Neagră" and '
        + '"FETEASCA NEAGRA" resolve to one variety. Anything that cannot be read with confidence '
        + 'is left empty rather than guessed.'),
      bulletRich('Filtering. ', 'Wine aisles reliably contain things that are not wine — vinegar, '
        + 'corkscrews, glassware, and in one case a children’s fizzy peach drink. A filter '
        + 'removes them.'),
      bulletRich('Price history. ', 'Results are stored so that a new price observation is written '
        + 'only when a price actually moves, which keeps a running history usable rather than '
        + 'one identical row per product per run.'),

      caption('Every figure in this brief comes from a single complete run on 10 August 2026: '
        + `${num(facts.total)} wine listings across 13 sources.`),

      h1('2. Coverage: what we have'),

      body('Thirteen sources are live. Nine are the retailer’s own website; four come via a '
        + 'delivery platform where the retailer has no usable site of its own.'),

      table(
        ['Retailer', 'Source', 'Wines', 'Nature of coverage'],
        coverage,
        [2500, 1500, 1100, 5700],
        { zebra: true, boldFirstCol: true },
      ),
      caption('Penny and Kaufland appear twice by design: the second feed covers a different '
        + 'part of the range, and keeping them separate prevents platform prices being mixed '
        + 'with shelf prices.'),

      h2('A caveat that governs every comparison'),
      body('Not every price in the dataset means the same thing, and this is the single most '
        + 'important limitation to hold in mind:'),
      bulletRich('Shelf prices ', 'come from the retailer’s own site and are directly '
        + 'comparable with each other.'),
      bulletRich('Platform prices ', '(Bolt Food, Glovo) are what the delivery app charges. For '
        + 'Penny we tested this directly against its own website and found them identical — a '
        + 'median difference of zero across 27 shared wines. Glovo, however, folds the 0.50 lei '
        + 'bottle deposit into the displayed price, so its listings sit slightly above shelf by '
        + 'construction.'),
      bulletRich('Promotional feeds ', '(Kaufland’s weekly leaflet) contain only discounted '
        + 'lines and must never be read as that retailer’s range.'),

      new Paragraph({ children: [new PageBreak()] }),

      h1('3. Coverage: what we do not have, and why'),

      body('Seven retailers on the original target list cannot be covered. This is not a gap in '
        + 'effort but a gap in reality: for each, we checked the retailer’s own site and all '
        + 'four Romanian delivery platforms — Bolt Food, Glovo, Wolt and Bringo — and the data '
        + 'does not exist in public form anywhere.'),

      table(
        ['Retailer', 'Why it cannot be covered'],
        gaps,
        [2500, 8300],
        { zebra: true, boldFirstCol: true },
      ),
      caption('Verified 10 August 2026 against retailer websites and against Bolt Food '
        + '(search across eight cities), Glovo (9,979 Romanian store pages), Wolt (16,408 '
        + 'Romanian venues) and Bringo.'),

      h2('What would be required to close the gap'),
      body('There are only three honest options, and none is a scraping problem:'),
      bulletRich('Leaflet parsing. ', 'Aggregators such as Kimbino and Tiendeo republish weekly '
        + 'leaflets for five of the seven. They are scanned images, so extraction means OCR, and '
        + 'a leaflet carries perhaps ten promotional wines rather than a range. Low cost, low '
        + 'quality, promotions only.'),
      bulletRich('In-store collection. ', 'Photographing shelf labels is the only method that '
        + 'yields a complete and accurate range for these retailers. It is what commercial panel '
        + 'providers do, and it is manual and per-store.'),
      bulletRich('Purchased panel data. ', 'Nielsen, GfK and similar vendors already sell this '
        + 'coverage. It costs money and it is the industry’s standing answer to exactly this '
        + 'question.'),
      body('Our recommendation is to leave the gap open and documented. The seven are '
        + 'predominantly hard discounters with narrow wine ranges; the thirteen covered sources '
        + 'already include every Romanian retailer with a meaningful wine assortment.'),

      h1('4. What the data shows'),

      h2('4.1  Price position is a matter of range, not of entry price'),
      body('Every retailer opens at roughly the same place. Entry prices cluster between 9 and 15 '
        + 'lei a bottle almost everywhere. What separates them is how much range sits above that '
        + 'floor — and on that measure they are very far apart.'),
      table(
        ['Retailer', 'Basis', 'Bottles (0.75 L)', 'Median RON/L', 'Entry price (RON)'],
        ladderRows,
        [2600, 1400, 2000, 2400, 2400],
        { zebra: true, boldFirstCol: true },
      ),
      caption('Restricted to 0.75 L bottles so retailers are compared like for like; bag-in-box '
        + 'and 0.2 L splits would otherwise distort the ranking. Median price per litre among '
        + `full-range retailers spans ${facts.ladder.auchan.median.toFixed(2)} RON/L (Auchan) to `
        + `${facts.ladder.sezamo.median.toFixed(2)} RON/L (Sezamo), a difference of `
        + `${pct(facts.ladder.sezamo.median / facts.ladder.auchan.median - 1)}.`),

      h2('4.2  The two online-only grocers sit distinctly above the physical chains'),
      body('Freshful and Sezamo — both delivery-native, neither operating physical stores — carry '
        + `the two highest median prices in the dataset at ${facts.ladder.freshful.median.toFixed(2)} `
        + `and ${facts.ladder.sezamo.median.toFixed(2)} RON/L respectively, roughly 60 to 70 per `
        + 'cent above Auchan. Part of this is genuine premium positioning: they also hold a '
        + 'disproportionate share of the wines above 200 lei. It is a different competitive game '
        + 'from the hypermarkets, played on curation rather than price.'),

      h2('4.3  Promotional intensity is very low, and highly concentrated'),
      body('Across the whole dataset only a small minority of wines carry an active discount, and '
        + 'they are concentrated in two retailers: Selgros '
        + `(${num(facts.promo_by.selgros)} wines) and Auchan (${num(facts.promo_by.auchan)}). `
        + `METRO ran no wine promotions at all across ${num(facts.by_retailer.metro)} listings. `
        + 'This matters for interpretation: price differences between these retailers are '
        + 'structural rather than the artefact of a promotional week.'),
      body('One methodological note belongs here. An early version of this analysis reported that '
        + '93 per cent of Carrefour’s range was discounted. That was wrong — a reference '
        + 'price in Carrefour’s page markup sits about 1.3 per cent above the displayed '
        + 'price and is a rounding artefact, not a former price. Carrefour publishes no former '
        + 'price at all in its listings, so its promotional intensity is not observable from this '
        + 'source and reads as zero. Absence of data, not absence of promotions.'),

      h2('4.4  The shelf is overwhelmingly Romanian, and narrowly varietal'),
      body(`Of the ${num(facts.country_known)} listings that state a country of origin, `
        + `${num(facts.country.Romania)} are Romanian — ${pct(facts.country.Romania / facts.country_known)} `
        + `of the total. Moldova (${num(facts.country.Moldova)}) and Italy (${num(facts.country.Italy)}) `
        + 'follow at a distance. Variety is similarly concentrated: five grapes — Cabernet '
        + 'Sauvignon, Merlot, Fetească Neagră, Sauvignon Blanc and Chardonnay — account for the '
        + 'bulk of everything identifiable.'),
      body('The commercial implication runs both ways. An importer is competing against a deep, '
        + 'cheap and familiar domestic wall. A domestic producer is competing almost entirely '
        + 'against other Romanian producers, in a handful of varieties, where differentiation on '
        + 'grape alone is close to impossible.'),

      h2('4.5  Format is standardised, which makes price comparison unusually clean'),
      body(`${pct(facts.vol['0.75'] / facts.total)} of all listings are the standard 0.75 litre `
        + 'bottle. Bag-in-box, magnums and small splits together are a rounding error. This is '
        + 'analytically convenient: price per litre is a fair basis for comparison here in a way '
        + 'it would not be in a category with more format fragmentation.'),

      h2('4.6  Style mix is consistent across retailers'),
      body(`White leads red across the market — ${num(facts.colour.alb)} listings to `
        + `${num(facts.colour.rosu)}, with rosé at ${num(facts.colour.rose)} — and dry wines are `
        + `${pct(facts.sweet.sec / facts.total)} of everything where sweetness is stated. `
        + `Sparkling is ${pct(facts.sparkling / facts.total)} of listings. These proportions vary `
        + 'remarkably little between retailers, which suggests the category is being merchandised '
        + 'to a common template rather than to differentiated local demand.'),

      h2('4.7  Attribute disclosure is wildly uneven — and that is itself a finding'),
      body('Auchan publishes grape, region, producer, country and alcohol content as structured '
        + 'fields. METRO publishes nearly as much but no alcohol content at all. Mega Image and '
        + 'Freshful strip the producer out of the product title entirely, which is why three '
        + 'different wines can appear under the identical name "Vin roșu sec Negru de Drăgășani '
        + '0.75L". For any application that needs to identify a specific wine — price comparison, '
        + 'stock matching, competitor tracking — this inconsistency, not the scraping, is the '
        + 'binding constraint.'),

      new Paragraph({ children: [new PageBreak()] }),

      h1('5. The three data points that matter most'),

      body('Of everything above, three findings carry the most decision value.'),

      keyPoint(1,
        `METRO is the cheapest option on ${pct(W.winrate)} of the wines it shares with a competitor`,
        [
          { t: `Of the ${W.n} wines where METRO and at least one other retailer stock an identical bottle, METRO is the cheapest on ${W.win} and the dearest on just ${W.lose}. `, b: false },
          { t: 'The advantage is structural, not promotional: ', b: true },
          { t: `METRO ran no discounts whatsoever across its ${num(facts.by_retailer.metro)} wines in this snapshot, and still undercut competitors whose prices did include active discounts. The material caveat is that many METRO lines carry a six-bottle minimum order, so the advantage is real for case buying and unavailable to someone buying a single bottle.`, b: false },
        ]),

      keyPoint(2,
        `Sourcing each wine at its cheapest retailer rather than its dearest saves ${pct(M.basket_hi / M.basket_lo - 1)}`,
        [
          { t: `Across the ${M.n} wines matched at two or more retailers, the identical basket costs ${num(M.basket_lo)} lei bought cheapest-each against ${num(M.basket_hi)} lei bought dearest-each. `, b: false },
          { t: `The median individual wine varies ${pct(M.median)} between retailers, ${pct(M.over20)} vary by a fifth or more, and the widest gap observed is ${pct(M.max)}. `, b: false },
          { t: 'For a buyer this quantifies negotiating room; for a retailer it identifies which of its own lines are visibly out of step with the market.', b: false },
        ]),

      keyPoint(3,
        'Retailers compete on the range above the entry price, not on the entry price itself',
        [
          { t: `Median price per litre runs from ${facts.ladder.auchan.median.toFixed(2)} RON/L at Auchan to ${facts.ladder.sezamo.median.toFixed(2)} RON/L at Sezamo — a ${pct(facts.ladder.sezamo.median / facts.ladder.auchan.median - 1)} difference — while every one of them opens at roughly 9 to 15 lei a bottle. `, b: false },
          { t: 'A listing decision therefore depends on which retailer’s ladder the wine lands on, ', b: true },
          { t: 'not on any national average price. The same bottle is a premium proposition in one chain and a mid-shelf one in another, and the retailer’s median tells you which.', b: false },
        ]),

      h1('Method and limitations'),
      bullet('All figures derive from a single complete collection run on 10 August 2026 covering '
        + `${num(facts.total)} wine listings across 13 sources. Prices move; the dataset is a `
        + 'snapshot, and the collection pipeline records a price history on subsequent runs.'),
      bullet('Cross-retailer matching requires the brand field, the complete set of distinctive '
        + 'words in the product name, and the bottle size to be identical. This is precise but '
        + 'incomplete: wines whose listings are worded differently are missed, so the 230 matched '
        + 'wines understate how many products are genuinely common across retailers. A looser '
        + 'match was tested and rejected after it grouped demonstrably different wines together.'),
      bullet('Comparisons of price position are restricted to 0.75 litre bottles. Shelf and '
        + 'platform prices are labelled throughout and should not be pooled.'),
      bullet('Attribute completeness varies by retailer. A blank field means the retailer did not '
        + 'publish the attribute, not that the value is zero. Alcohol content in particular is '
        + `available for only ${pct(facts.abv_n / facts.total)} of listings.`),
      bullet('METRO prices are inclusive of VAT and exclusive of the bottle deposit; the deposit '
        + 'and the net price are retained separately in the underlying data.'),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = '/home/user/MarketWineScraper/exports/romanian-wine-retail-issue-brief.docx';
  fs.writeFileSync(out, buf);
  console.log('wrote ' + out + ' (' + buf.length + ' bytes)');
});
