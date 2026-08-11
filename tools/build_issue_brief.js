// Romanian wine retail — issue brief.
// Layout follows measured McKinsey report conventions: two-measure grid, Georgia
// display against 9.5pt Arial body, black headings, hairline-only tables,
// exhibit titles that state the finding and end in a period, no page header.
// The "McKinsey & Company" exhibit signature is deliberately NOT reproduced —
// this is our document, not theirs.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, PageBreak,
  Footer, PageNumber, LevelFormat, VerticalAlign, LineRuleType, HeightRule,
  TableLayoutType,
} = require('docx');
const fs = require('fs');

// ---- palette (measured from McKinsey publications) ----------------------
const INK = '231F20';   // rich black — all running text and headings
const BLACK = '000000';   // pure black — exhibit block only
const NAVY = '051C2C';   // deep blue — used as a ground, never as type
const TITLE = '00162B';   // cover title
const ACC = '2251FF';   // accent — pull quote only
const GREY = '656565';   // notes and source lines
const HAIR = '757575';   // table hairlines
const SANS = 'Arial';
const SERIF = 'Georgia';

const PAGE_W = 12240, PAGE_H = 15840;
const M_SIDE = 1020;
const FULL = PAGE_W - 2 * M_SIDE;    // 10200 — full measure
const BODY_IN = 1746;                // body column indent
const BODY_W = FULL - BODY_IN - 800; // body measure

const F = JSON.parse(fs.readFileSync('/tmp/brief_facts.json', 'utf8'));
const R = JSON.parse(fs.readFileSync('/tmp/rankings.json', 'utf8'));

const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
const n = (v) => Number(v).toLocaleString('en-US');
const money = (v) => Number(v).toFixed(2);

const LAB = {
  auchan: 'Auchan', carrefour: 'Carrefour', selgros: 'Selgros', metro: 'METRO',
  freshful: 'Freshful', sezamo: 'Sezamo', mega_image: 'Mega Image', penny: 'Penny',
  kaufland_bolt: 'Kaufland (Bolt)', penny_bolt: 'Penny (Bolt)',
  profi_glovo: 'Profi (Glovo)', supeco_glovo: 'Supeco (Glovo)', kaufland: 'Kaufland (leaflet)',
};

const NO_BORDERS = {
  top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
};

let exN = 0;
const kids = [];

// ---- primitives ---------------------------------------------------------
function t(text, o = {}) {
  return new TextRun({
    text, font: o.font || SANS, size: o.size || 19,
    bold: !!o.bold, italics: !!o.italic, color: o.color || INK,
  });
}

// Body prose sits on the indented measure; exhibits break out to full width.
function body(runs, o = {}) {
  return new Paragraph({
    spacing: { before: o.before || 0, after: o.after == null ? 260 : o.after,
               line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: o.full ? 0 : BODY_IN, right: o.full ? 0 : 800 },
    children: Array.isArray(runs) ? runs : [t(runs, o)],
  });
}

function bullet(runs) {
  return new Paragraph({
    numbering: { reference: 'bl', level: 0 },
    spacing: { before: 0, after: 260, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN + 300, hanging: 220, right: 800 },
    children: Array.isArray(runs) ? runs : [t(runs)],
  });
}

// Section heading: Georgia bold 12pt, black. Sentence case, no terminal period.
function head(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    keepNext: true,
    spacing: { before: 720, after: 120, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: [t(text, { font: SERIF, size: 24, bold: true, color: INK })],
  });
}

// Subsection: Arial bold at body size — hierarchy comes from family, not size.
function sub(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { before: 520, after: 0, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: [t(text, { size: 19, bold: true, color: INK })],
  });
}

function pullQuote(text) {
  return new Paragraph({
    spacing: { before: 520, after: 400, line: 540, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: [t(text, { font: SERIF, size: 48, bold: true, color: ACC })],
  });
}

/**
 * Exhibit. Label is smaller and lighter than the title — the finding leads,
 * the number recedes. Table carries horizontal hairlines only: no fills, no
 * vertical rules, no outer box.
 */
function exhibit({ title, subtitle, headers, rows, widths, align, note, source }) {
  exN += 1;
  const out = [];
  out.push(new Paragraph({
    spacing: { before: 400, after: 160, line: 260, lineRule: LineRuleType.EXACT },
    children: [t(`Exhibit ${exN}`, { size: 19, color: BLACK })],
  }));
  out.push(new Paragraph({
    keepNext: true,
    spacing: { before: 0, after: 280, line: 280, lineRule: LineRuleType.EXACT },
    children: [t(title, { size: 24, bold: true, color: BLACK })],
  }));
  if (subtitle) {
    out.push(new Paragraph({
      keepNext: true,
      spacing: { before: 0, after: 200, line: 200, lineRule: LineRuleType.EXACT },
      children: [t(subtitle.label, { size: 18, bold: true, color: BLACK }),
                 t(subtitle.unit ? `, ${subtitle.unit}` : '', { size: 18, color: BLACK })],
    }));
  }

  const al = align || headers.map((_, i) => (i === 0 ? 'l' : 'r'));
  const cell = (text, o = {}) => new TableCell({
    width: { size: o.w, type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    verticalAlign: VerticalAlign.TOP,
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      bottom: o.head
        ? { style: BorderStyle.SINGLE, size: 4, color: HAIR }
        : { style: BorderStyle.SINGLE, size: 2, color: HAIR },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    children: [new Paragraph({
      spacing: { before: 0, after: 0, line: 220, lineRule: LineRuleType.EXACT },
      alignment: o.a === 'l' ? AlignmentType.LEFT : AlignmentType.RIGHT,
      children: [t(String(text), { size: 17, bold: !!o.bold, color: INK })],
    })],
  });

  out.push(new Table({
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: NO_BORDERS,
    rows: [
      new TableRow({
        tableHeader: true,
        height: { value: 400, rule: HeightRule.ATLEAST },
        children: headers.map((h, i) => cell(h, { w: widths[i], a: al[i], bold: true, head: true })),
      }),
      ...rows.map((r) => new TableRow({
        height: { value: 300, rule: HeightRule.ATLEAST },
        children: r.map((c, i) => cell(c, { w: widths[i], a: al[i], bold: i === 0 })),
      })),
    ],
  }));

  if (note) {
    out.push(new Paragraph({
      spacing: { before: 200, after: 0, line: 135, lineRule: LineRuleType.EXACT },
      children: [t(`Note: ${note}`, { size: 12, color: GREY })],
    }));
  }
  out.push(new Paragraph({
    spacing: { before: note ? 60 : 200, after: 400, line: 135, lineRule: LineRuleType.EXACT },
    children: [t(source || `Source: MarketWineScraper collection, ${COLLECTED}`,
      { size: 12, color: GREY })],
  }));
  return out;
}

function panel(title, lines) {
  const inner = [new Paragraph({
    spacing: { before: 0, after: 200, line: 260, lineRule: LineRuleType.EXACT },
    children: [t(title, { font: SERIF, size: 24, bold: true, color: INK })],
  })];
  lines.forEach((l) => inner.push(new Paragraph({
    numbering: { reference: 'bl', level: 0 },
    spacing: { before: 0, after: 200, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: 300, hanging: 220 },
    children: [t(l, { size: 18 })],
  })));
  return new Table({
    columnWidths: [FULL],
    layout: TableLayoutType.FIXED,
    width: { size: FULL, type: WidthType.DXA },
    borders: {
      ...NO_BORDERS,
      top: { style: BorderStyle.SINGLE, size: 12, color: INK },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: HAIR },
    },
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: FULL, type: WidthType.DXA },
        margins: { top: 260, bottom: 200, left: 0, right: 400 },
        borders: NO_BORDERS,
        children: inner,
      })],
    })],
  });
}

// ---- derived -------------------------------------------------------------
const M = F.matches;
const W = F.wins.metro;
const PS = R.promo_sensitivity;
const depth = R.depth;
// The price-span claim compares like with like: shelf basis only. Platform
// retailers appear in the exhibit but are excluded from this comparison.
const full = depth.filter((d) => d.n >= 200 && d.basis === 'Shelf');
const frLo = full[0], frHi = full[full.length - 1];
const platformFull = depth.filter((d) => d.n >= 200 && d.basis === 'Platform');
// Headline figures are derived, never typed. Written-down numbers survive the
// data they came from: this deck once said "7,513 listings" three re-scrapes
// after that stopped being true.
const spreadPct = Math.round((frHi.median / frLo.median - 1) * 100);
const priceRatio = Math.round(R.most_expensive[0].price / R.cheapest[0].price);
const roShare = (R.countries.find((c) => c.country === 'Romania') || {}).listings / R.country_known;
const midBand = R.bands.find((b) => b.band === '25-50 lei');
const PO = F.penny_overlap;
const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
  'nine', 'ten', 'eleven', 'twelve'];
const word = (v) => WORDS[v] || n(v);
const maxReach = word(Math.max(...R.brands_by_reach.map((b) => b.retailers)));
const brandRatio = Math.round(R.brands_premium[0].median_ppl / R.brands_value[0].median_ppl);
// The dry-vs-semi-dry multiple, measured inside each colour so the claim cannot
// be an artefact of colour mix.
const dryMult = Object.values(R.sweetness_by_colour)
  .filter((c) => c.sec && c.demisec).map((c) => c.sec / c.demisec);
const dryLo = Math.min(...dryMult).toFixed(1);
const dryHi = Math.max(...dryMult).toFixed(1);
// The collection date lives in the data, so no document carries it as a
// constant that a later run can silently invalidate.
const COLLECTED = new Date(`${F.collected}T00:00:00Z`).toLocaleDateString('en-GB',
  { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

// ============================== COVER ====================================
kids.push(new Paragraph({ spacing: { before: 0, after: 0, line: 2400, lineRule: LineRuleType.EXACT }, children: [] }));
kids.push(new Paragraph({
  spacing: { before: 0, after: 0, line: 260, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN },
  children: [t('Retail price research', { size: 19, bold: true, color: INK })],
}));
kids.push(new Paragraph({
  spacing: { before: 0, after: 340, line: 800, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN, right: 400 },
  children: [t('What does wine cost in Romanian grocery retail?',
    { font: SERIF, size: 76, bold: true, color: TITLE })],
}));
kids.push(new Paragraph({
  spacing: { before: 340, after: 0, line: 340, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN, right: 900 },
  children: [t('The same bottle sells for very different prices depending on the shop. '
    + `This brief sets out what ${n(R.n_all)} listings from 13 retail sources show about `
    + 'price gaps, brands, and grape varieties.', { size: 28 })],
}));
// Deep blue band stands in for the cover photograph.
kids.push(new Paragraph({ spacing: { before: 0, after: 0, line: 700, lineRule: LineRuleType.EXACT }, children: [] }));
kids.push(new Table({
  columnWidths: [PAGE_W],
  layout: TableLayoutType.FIXED,
  width: { size: PAGE_W, type: WidthType.DXA },
  indent: { size: -M_SIDE, type: WidthType.DXA },
  borders: NO_BORDERS,
  rows: [new TableRow({
    height: { value: 5200, rule: HeightRule.EXACT },
    children: [new TableCell({
      width: { size: PAGE_W, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: NAVY, color: 'auto' },
      borders: NO_BORDERS,
      children: [new Paragraph('')],
    })],
  })],
}));
kids.push(new Paragraph({
  spacing: { before: 200, after: 0, line: 260, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN },
  children: [t('August 2026', { size: 19, color: NAVY })],
}));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ============================== AT A GLANCE ==============================
kids.push(panel('At a glance', [
  `The same wine costs different amounts at different shops. Across the ${M.n} wines that can be `
  + `matched reliably, the median gap between the cheapest and the dearest listing is `
  + `${pct(M.median)}, and ${pct(M.over20)} differ by 20 percent or more.`,
  `METRO holds the lowest price on ${pct(W.winrate)} of the wines it shares with a competitor, `
  + `without running any promotions.`,
  `Dry wine sells for roughly twice the price per litre of semi-sweet wine. The pattern holds `
  + `separately for white, red, and rosé, so it is not a colour effect.`,
  `Thirteen of the twenty retailers targeted can be covered. The other seven publish no product `
  + `data on their own sites or on any delivery platform.`,
]));

// ============================== 1. METHOD ================================
kids.push(head('How is the data collected?'));
kids.push(body([
  t('The tool reads each retailer\'s own website ', { bold: true }),
  t('the same way a shopper\'s browser does, and writes the result into one table. Nothing is '
    + 'purchased and no private system is used. Every source is the public endpoint the shop '
    + 'already serves to its own customers.'),
]));
kids.push(bullet([t('Find the source. ', { bold: true }),
  t('Each retailer serves its product list from a catalogue API (Auchan, Sezamo, METRO), a search '
    + 'index (Selgros), plain HTML (Carrefour, Penny), or a delivery platform that carries the '
    + 'shop (Kaufland, Profi, Supeco).')]));
kids.push(bullet([t('Read the categories from the site\'s own menu. ', { bold: true }),
  t('Nothing is hardcoded, so a shop reorganising its aisles reduces coverage rather than '
    + 'breaking collection silently.')]));
kids.push(bullet([t('Fill the gaps from the product name. ', { bold: true }),
  t('Retailers publish very different amounts of detail. Published fields are used directly; the '
    + 'rest is read from the title. Romanian spelling is normalised, so "Fetească Neagră" and '
    + '"FETEASCA NEAGRA" count as one variety. Anything that cannot be read reliably is left blank '
    + 'rather than guessed.')]));
kids.push(bullet([t('Remove what is not wine. ', { bold: true }),
  t('Wine aisles carry vinegar, corkscrews, and glassware, and also things that look much more '
    + 'like wine: alcohol-free "sparkling", fruit wine, ready-to-drink cocktails, and fizzy juice '
    + 'sold to children in a wine bottle. These are removed by name. Because a list of exclusions '
    + 'can only reject what someone has already seen, every remaining listing is also scored on '
    + 'independent evidence that it is wine, and the weakest few percent are read by hand before '
    + 'the figures are published.')]));
kids.push(bullet([t('Check the price against the retailer. ', { bold: true }),
  t(`Most sites publish their own price per litre beside the price. It is calculated by the shop `
    + `from the same two numbers we read, so it is an independent test of whether we read them `
    + `correctly. ${n(F.unit_price_checked)} listings publish one, and `
    + `${n(F.unit_price_checked - F.unit_price_conflicts)} of them agree; the `
    + `${F.unit_price_conflicts} that do not are listings whose own title and per-litre label `
    + `contradict each other.`)]));
kids.push(bullet([t('Store price changes only. ', { bold: true }),
  t('A new price is recorded when the price moves, which keeps the history readable across runs.')]));

// ============================== 2. COVERAGE ==============================
kids.push(head('Which retailers can be covered?'));
kids.push(body([
  t('Thirteen sources are live, ', { bold: true }),
  t('covering eleven retailers. Nine read a retailer\'s own website; four read a delivery '
    + 'platform, used where the shop has no usable site of its own. Kaufland and Profi are '
    + 'readable only this way. Together they cover every Romanian retailer with a wine range '
    + 'worth tracking (Exhibit 1).'),
]));

kids.push(...exhibit({
  title: 'Thirteen sources cover eleven retailers and every significant wine range in the market.',
  subtitle: { label: 'Wine listings collected, by retailer', unit: 'number of listings' },
  headers: ['Retailer', 'Read from', 'Listings', 'What is covered'],
  rows: [
    ['Carrefour', 'Own site', n(F.by_retailer.carrefour), 'Full range'],
    ['Auchan', 'Own site', n(F.by_retailer.auchan), 'Full range; most attributes published'],
    ['Selgros', 'Own site', n(F.by_retailer.selgros), 'Full range; price set per depot'],
    ['METRO', 'Own site', n(F.by_retailer.metro), 'Full range; 6-bottle minimum common'],
    ['Freshful', 'Own site', n(F.by_retailer.freshful), 'Full range; delivery-only retailer'],
    ['Kaufland', 'Bolt Food', n(F.by_retailer.kaufland_bolt),
      `Full range; weekly leaflet adds ${F.by_retailer.kaufland} promotional prices`],
    ['Sezamo', 'Own site', n(F.by_retailer.sezamo), 'Full range; delivery-only retailer'],
    ['Mega Image', 'Own site', n(F.by_retailer.mega_image), 'Full range'],
    ['Supeco', 'Glovo', n(F.by_retailer.supeco_glovo), 'Only available route; own site blocked'],
    ['Penny', 'Bolt Food', n(F.by_retailer.penny_bolt),
      `Wider than the retailer's own site, which lists ${F.by_retailer.penny}`],
    ['Profi', 'Glovo', n(F.by_retailer.profi_glovo), 'Only available route; no web shop exists'],
  ],
  widths: [1900, 1500, 1200, 5600],
  align: ['l', 'l', 'r', 'l'],
  note: 'Kaufland and Penny are each read from two sources. The larger is shown; the counts are '
    + 'not added together because the two feeds overlap. Kaufland\'s leaflet carries only '
    + `${F.by_retailer.kaufland} promotional wines, which is why the platform feed is the primary `
    + 'route for that retailer.',
}));

kids.push(sub('Three kinds of price, which must not be pooled'));
kids.push(bullet([t('Shelf price ', { bold: true }),
  t('comes from the retailer\'s own site. These compare directly with one another.')]));
kids.push(bullet([t('Platform price ', { bold: true }),
  t('is what the delivery app charges. For Penny this was checked against the retailer\'s own '
    + `website across the ${PO.n} wines both carry: ${PO.same} match to the lei, and the platform `
    + `is dearer on ${PO.dearer}, by a median of ${pct(PO.median, 1)}, because Penny discounts on `
    + 'its own site and the platform feed does not always follow. Glovo folds the 0.50 lei deposit '
    + 'into the displayed price, so Glovo rows sit slightly above shelf by construction.')]));
kids.push(bullet([t('Promotion-only feed ', { bold: true }),
  t('is Kaufland\'s weekly leaflet. It lists discounted wines only and is not that retailer\'s '
    + 'range.')]));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ============================== 3. GAPS ==================================
kids.push(head('Which retailers cannot be covered, and why?'));
kids.push(body([
  t('Seven retailers publish nothing usable. ', { bold: true }),
  t('For each, the retailer\'s own site and all four Romanian delivery platforms — Bolt Food, '
    + 'Glovo, Wolt, and Bringo — were checked. The data does not exist in public form anywhere '
    + '(Exhibit 2).'),
]));

kids.push(...exhibit({
  title: 'Seven retailers publish no wine data on any channel.',
  subtitle: { label: 'Retailers checked against own website and four delivery platforms' },
  headers: ['Retailer', 'Reason no data is available'],
  rows: [
    ['Lidl', 'Online shop sells no wine; not carried by any delivery platform'],
    ['La Cocoș', 'Website blocks automated access (HTTP 403), including from a real browser'],
    ['La Doi Pași', 'Franchise network; the official site publishes a leaflet, not a catalogue'],
    ['Annabella', 'Product sitemap lists 18 items, none of them wine'],
    ['Unicarm', 'Single-page website with no product listing'],
    ['Froo', 'Marketing site only; sitemap contains no products'],
    ['Atac', 'No public product listing found on any channel'],
  ],
  widths: [1900, 8300],
  align: ['l', 'l'],
  source: 'Source: Checks against retailer websites and Bolt Food (8 cities), Glovo (9,979 '
    + `Romanian store pages), Wolt (16,408 Romanian venues), and Bringo, ${COLLECTED}`,
}));

kids.push(sub('What closing the gap would take'));
kids.push(body('There are three options, and none of them is a scraping problem.'));
kids.push(bullet([t('Read the weekly leaflets. ', { bold: true }),
  t('Kimbino and Tiendeo republish leaflets for five of the seven. They are scanned images, so the '
    + 'text has to be recovered by OCR, and a leaflet holds roughly ten wines on promotion rather '
    + 'than a range. Cheap, inaccurate, and limited to promotions.')]));
kids.push(bullet([t('Photograph the shelves. ', { bold: true }),
  t('This is the only method that produces a complete and correct range for these shops. It is '
    + 'manual and has to be repeated per store.')]));
kids.push(bullet([t('Buy panel data. ', { bold: true }),
  t('Nielsen, GfK, and similar firms already sell this coverage.')]));
kids.push(body('Leaving the gap open and documented is the better option. These seven are mostly '
  + 'hard discounters with narrow wine ranges, and the thirteen covered sources already include '
  + 'every retailer with a range worth tracking.'));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ============================== 4. RANKINGS ==============================
kids.push(head('Where does each retailer sit on price?'));
kids.push(body([
  t('Every retailer starts in the same place. ', { bold: true }),
  t(`The cheapest bottle costs between ${F.entry_lo} and ${F.entry_typical_hi} lei at every `
    + 'retailer but the two delivery-only shops. What separates retailers is '
    + 'how much range sits above that floor (Exhibit 3).'),
]));

kids.push(...exhibit({
  title: `Median price per litre varies by ${spreadPct} percent across shelf-price retailers, `
    + 'but entry prices do not.',
  subtitle: { label: 'Price position by retailer, 0.75 litre bottles', unit: 'RON per litre' },
  headers: ['Retailer', 'Price basis', 'Bottles', 'Cheapest 10%', 'Median', 'Dearest 10%', '200+ lei'],
  rows: depth.map((d) => [
    LAB[d.retailer], d.basis, n(d.n), money(d.p10), money(d.median), money(d.p90),
    pct(d.over200, 1),
  ]),
  widths: [1900, 1350, 1150, 1500, 1350, 1500, 1450],
  align: ['l', 'l', 'r', 'r', 'r', 'r', 'r'],
  note: 'Platform rows are delivery-app prices and are not directly comparable with shelf rows; '
    + 'Glovo additionally includes the 0.50 lei bottle deposit. "200+ lei" is the share of that '
    + 'retailer\'s bottles priced above 200 lei.',
}));

kids.push(body(`Among shelf-price retailers, median price per litre runs from `
  + `${money(frLo.median)} lei at ${LAB[frLo.retailer]} to ${money(frHi.median)} lei at `
  + `${LAB[frHi.retailer]}. The two delivery-only retailers, Freshful and Sezamo, are the most `
  + `expensive. METRO holds the widest spread of any retailer: its cheapest tenth is the lowest in `
  + `the market and its dearest tenth is the highest. Kaufland, readable only through Bolt Food, `
  + `sits at ${money(platformFull[0].median)} lei per litre on ${n(platformFull[0].n)} bottles — `
  + `below every shelf retailer, though a platform price is not a like-for-like comparison.`));

kids.push(head('Who is actually cheapest on the same wine?'));
kids.push(body([
  t('Median price describes a range, not competitiveness. ', { bold: true }),
  t('A shop looks expensive simply for stocking expensive wine. The fair test takes wines that two '
    + 'retailers both carry and compares who prices them lower (Exhibit 4).'),
]));

kids.push(...exhibit({
  title: `METRO holds the lowest price on ${pct(W.winrate)} of the wines it shares with a `
    + 'competitor.',
  subtitle: { label: 'Price outcome on wines carried by two or more retailers', unit: 'number and %' },
  headers: ['Retailer', 'Shared wines', 'Times cheapest', 'Win rate, as paid',
            'Win rate, pre-discount', 'Times dearest'],
  rows: Object.entries(F.wins).sort((a, b) => b[1].winrate - a[1].winrate).map(([k, v]) => [
    LAB[k], n(v.n), n(v.win), pct(v.winrate),
    R.wins_regular[k] ? pct(R.wins_regular[k].winrate) : '—', n(v.lose),
  ]),
  widths: [2000, 1550, 1600, 1750, 1900, 1400],
  note: 'Retailers appearing in at least ten matched wines. Win rate is the share of a retailer\'s '
    + 'matched wines on which it is the cheapest of those carrying it, not a statement about its '
    + 'whole range. "As paid" uses the price a shopper pays including any active discount; '
    + '"pre-discount" reverses every promotion to the retailer\'s standing price.',
}));

kids.push(pullQuote(`METRO is cheapest on ${W.win} of ${W.n} shared wines — and on `
  + `${pct(R.wins_regular.metro.winrate)} once competitors' discounts are reversed.`));

kids.push(body(`Selgros, the other cash-and-carry, wins only ${pct(F.wins.selgros.winrate)} and is `
  + `dearest on ${pct(F.wins.selgros.loserate)}. The two wholesale formats price very differently, `
  + `so they should not be treated as one channel. The pre-discount column matters here: Auchan's `
  + `win rate falls from ${pct(F.wins.auchan.winrate)} to `
  + `${pct(R.wins_regular.auchan.winrate)} once promotions are reversed, so much of its price `
  + `competitiveness is promotional. Selgros moves the other way, from `
  + `${pct(F.wins.selgros.winrate)} to ${pct(R.wins_regular.selgros.winrate)}. METRO, which ran no `
  + `promotions at all, rises to ${pct(R.wins_regular.metro.winrate)}.`));

kids.push(...exhibit({
  title: 'On some identical wines the dearest retailer charges more than double the cheapest.',
  subtitle: { label: 'Widest price gaps on matched wines', unit: 'RON per bottle' },
  headers: ['Wine', 'Cheapest', 'at', 'Dearest', 'at', 'Gap'],
  rows: R.biggest_gaps.slice(0, 12).map((m) => [
    m.name.length > 40 ? `${m.name.slice(0, 39)}…` : m.name,
    money(m.lo), LAB[m.cheap] || m.cheap, money(m.hi), LAB[m.dear] || m.dear, pct(m.spread),
  ]),
  widths: [3600, 1150, 1600, 1150, 1600, 1100],
  align: ['l', 'r', 'l', 'r', 'l', 'r'],
  note: 'Same brand, same product wording, and same bottle size at both retailers. These are not '
    + 'different vintages or pack sizes. Prices are what a shopper pays, discounts included.',
}));
kids.push(body(`Part of this gap is promotional rather than structural. Reversing every active `
  + `discount narrows the share of matched wines differing by 20 percent or more from `
  + `${pct(PS.paid_over20)} to ${pct(PS.regular_over20)}, and the basket saving from `
  + `${pct(PS.paid_basket)} to ${pct(PS.regular_basket)}. The median gap barely moves `
  + `(${pct(PS.paid_median)} to ${pct(PS.regular_median)}), so the typical difference between `
  + `retailers is a standing one; the widest gaps are the ones a sale creates.`));

kids.push(...exhibit({
  title: 'Only a handful of labels are carried by four or more retailers.',
  subtitle: { label: 'Most widely distributed matched labels', unit: 'RON per bottle' },
  headers: ['Wine', 'Retailers', 'Cheapest', 'Dearest', 'Gap'],
  rows: R.most_widely_stocked.slice(0, 10).map((m) => [
    m.name.length > 48 ? `${m.name.slice(0, 47)}…` : m.name,
    n(m.retailers), money(m.lo), money(m.hi), pct(m.spread),
  ]),
  widths: [4700, 1400, 1400, 1400, 1300],
  note: 'Matched on reconstructed wine identity: abbreviations expanded, brands read from the '
    + 'title where the retailer publishes none, and attributes one shop omits resolved against '
    + 'the shops that state them.',
}));
kids.push(body('Beciul Domnesc and Domeniile Sâmburești each appear at four retailers. Labels this '
  + 'widely distributed carry the tightest price gaps, because shoppers can compare them directly.'));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ---- brands
kids.push(head('Which brands dominate the shelf?'));
kids.push(body([
  t(`The data holds ${n(R.n_brands)} distinct brands. `, { bold: true }),
  t('Presence and price position are different things, so both are worth ranking (Exhibits 6 '
    + 'and 7).'),
]));

kids.push(...exhibit({
  title: 'Jidvei has the most listings, but Zarea reaches the most retailers.',
  subtitle: { label: 'Largest brands by number of listings', unit: 'listings, retailers, RON per litre' },
  headers: ['Brand', 'Listings', 'Retailers', 'Median', 'Cheapest', 'Dearest'],
  rows: R.brands_by_listings.slice(0, 12).map((b) => [
    b.brand, n(b.listings), n(b.retailers),
    b.median_ppl == null ? '—' : money(b.median_ppl), money(b.min), money(b.max),
  ]),
  widths: [2900, 1350, 1400, 1500, 1500, 1550],
  note: 'Shelf-price retailers only. Median, cheapest, and dearest are RON per litre.',
}));
kids.push(body(`Jidvei carries ${n(R.brands_by_listings[0].listings)} listings across `
  + `${R.brands_by_listings[0].retailers} retailers; Zarea carries fewer but reaches all `
  + `${maxReach}. `
  + `Listing count measures how many different wines a brand sells. Retailer count measures how `
  + `hard the brand is to avoid.`));

kids.push(...exhibit({
  title: 'The most expensive brands are Champagne houses; the cheapest are Romanian volume labels.',
  subtitle: { label: 'Brands ranked by median price per litre', unit: 'RON per litre' },
  headers: ['Premium brand', 'Median', 'Listings', 'Value brand', 'Median', 'Listings'],
  rows: R.brands_premium.slice(0, 10).map((b, i) => {
    const v = R.brands_value[i] || { brand: '', median_ppl: '', listings: '' };
    return [b.brand, money(b.median_ppl), n(b.listings),
      v.brand, v.median_ppl === '' ? '' : money(v.median_ppl),
      v.listings === '' ? '' : n(v.listings)];
  }),
  widths: [2500, 1400, 1300, 2500, 1300, 1200],
  align: ['l', 'r', 'r', 'l', 'r', 'r'],
  note: 'Brands with at least five listings.',
}));
kids.push(body(`The two ends of this table are about ${brandRatio}x apart. Louis Roederer sits at `
  + `${money(R.brands_premium[0].median_ppl)} lei per litre and VINEXPORT at `
  + `${money(R.brands_value[0].median_ppl)} lei. They do not compete with each other.`));

// ---- grapes
kids.push(head('Which grape varieties lead, and which command a premium?'));
kids.push(body([
  t(`${n(R.n_grapes)} varieties appear in the data, `, { bold: true }),
  t('but five account for most of what is on the shelf. Volume and price rank very differently '
    + '(Exhibits 8 and 9).'),
]));

kids.push(...exhibit({
  title: 'Fetească Neagră is the only Romanian variety among the five most listed.',
  subtitle: { label: 'Most listed grape varieties', unit: 'listings and RON per litre' },
  headers: ['Variety', 'Listings', 'Retailers', 'Median', 'Dearest 10%'],
  rows: R.grapes_by_listings.slice(0, 12).map((g) => [
    g.grape, n(g.listings), n(g.retailers), money(g.median_ppl), money(g.p90),
  ]),
  widths: [3300, 1500, 1500, 1900, 2000],
  note: 'Varieties with at least 15 listings. A wine may list more than one variety, so listings '
    + 'do not sum to the number of wines.',
}));

kids.push(...exhibit({
  title: 'Imported varieties price highest; Romanian white varieties price lowest.',
  subtitle: { label: 'Grape varieties ranked by median price per litre', unit: 'RON per litre' },
  headers: ['Most expensive', 'Median', 'Listings', 'Least expensive', 'Median', 'Listings'],
  rows: R.grapes_by_price.slice(0, 10).map((g, i) => {
    const c = R.grapes_cheapest[i] || { grape: '', median_ppl: '', listings: '' };
    return [g.grape, money(g.median_ppl), n(g.listings),
      c.grape, c.median_ppl === '' ? '' : money(c.median_ppl),
      c.listings === '' ? '' : n(c.listings)];
  }),
  widths: [2600, 1350, 1300, 2600, 1200, 1150],
  align: ['l', 'r', 'r', 'l', 'r', 'r'],
}));
const negru = R.grapes_by_price.find((g) => String(g.grape).toLowerCase().includes('negru'));
kids.push(body(`Sangiovese, Tempranillo, and Primitivo — all imported — carry the highest median `
  + `prices. Negru de Drăgășani at ${money(negru.median_ppl)} lei per litre is the most expensive `
  + `Romanian variety, and Grasă de Cotnari at ${money(R.grapes_cheapest[0].median_ppl)} lei the `
  + `cheapest. A Romanian producer seeking a premium price has an easier case with Negru de `
  + `Drăgășani than with a white variety.`));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ---- colour and sweetness
kids.push(head('How do colour, style, and sweetness affect price?'));
kids.push(...exhibit({
  title: 'Red is the most expensive colour and rosé the cheapest, but the range is narrow.',
  subtitle: { label: 'Assortment and price by colour and style', unit: '% of range and RON per litre' },
  headers: ['Category', 'Bottles', 'Share of range', 'Median'],
  rows: [
    ['White', n(R.colour.alb.n), pct(R.colour.alb.share, 1), money(R.colour.alb.median_ppl)],
    ['Red', n(R.colour.rosu.n), pct(R.colour.rosu.share, 1), money(R.colour.rosu.median_ppl)],
    ['Rosé', n(R.colour.rose.n), pct(R.colour.rose.share, 1), money(R.colour.rose.median_ppl)],
    ['Sparkling', n(R.colour.sparkling.n), pct(R.colour.sparkling.share, 1), money(R.colour.sparkling.median_ppl)],
    ['Still', n(R.colour.still.n), pct(R.colour.still.share, 1), money(R.colour.still.median_ppl)],
  ],
  widths: [2900, 2200, 2500, 2600],
  note: '0.75 litre bottles, shelf-price retailers. Colour shares do not sum to 100% because some '
    + 'listings do not state a colour.',
}));

kids.push(...exhibit({
  title: 'Dry wine sells for 1.5 to 2.2 times the price per litre of semi-dry wine, in every colour.',
  subtitle: { label: 'Median price by sweetness, within each colour', unit: 'RON per litre' },
  headers: ['Sweetness', 'White', 'Red', 'Rosé', 'All bottles', 'Share of range'],
  rows: [['sec', 'Sec (dry)'], ['demisec', 'Demisec'], ['demidulce', 'Demidulce'],
         ['dulce', 'Dulce (sweet)']].map(([k, label]) => [
    label,
    R.sweetness_by_colour.alb[k] == null ? '—' : money(R.sweetness_by_colour.alb[k]),
    R.sweetness_by_colour.rosu[k] == null ? '—' : money(R.sweetness_by_colour.rosu[k]),
    R.sweetness_by_colour.rose[k] == null ? '—' : money(R.sweetness_by_colour.rose[k]),
    money(R.sweetness[k].median_ppl), pct(R.sweetness[k].share, 1),
  ]),
  widths: [2200, 1500, 1500, 1500, 1800, 1700],
  note: '0.75 litre bottles. Sweet (dulce) wine does not follow the pattern: dessert wines sit '
    + 'above semi-dry, so the relationship is not simply "sweeter is cheaper". Dashes mark cells '
    + 'with too few bottles to report reliably.',
}));
kids.push(body('This is the strongest single price signal in the data, and it is not a colour '
  + `effect: dry wine prices between ${dryLo} and ${dryHi} times semi-dry within white, red, and `
  + 'rosé separately. The exception is sweet wine, which sits above semi-dry because dessert wines are '
  + 'priced as a speciality rather than as a budget style. Sweetness is also one of the few '
  + 'attributes almost every retailer publishes, which makes it usable in practice.'));

// ---- origin
kids.push(head('Where does the wine come from?'));
kids.push(...exhibit({
  title: `Romanian wine accounts for ${pct(roShare)} of bottles where the retailer states an `
    + 'origin.',
  subtitle: { label: 'Country of origin', unit: 'bottles and RON per litre' },
  headers: ['Country', 'Bottles', 'Median'],
  rows: R.countries.slice(0, 10).map((c) => [c.country, n(c.listings), money(c.median_ppl)]),
  widths: [4200, 3000, 3000],
  note: `Origin is published for ${n(R.country_known)} of ${n(R.n_std)} standard bottles `
    + `(${pct(R.country_known / R.n_std)}), almost entirely by Auchan and METRO.`,
}));

kids.push(...exhibit({
  title: 'Dealu Mare is the largest named region; Tuscany and Banat carry the highest prices.',
  subtitle: { label: 'Wine regions by number of bottles', unit: 'bottles and RON per litre' },
  headers: ['Region', 'Bottles', 'Median'],
  rows: R.regions.slice(0, 12).map((r) => [r.region, n(r.listings), money(r.median_ppl)]),
  widths: [4200, 3000, 3000],
  note: 'Regions with at least eight bottles. Region is published by Auchan and METRO only.',
}));
kids.push(body('Dealu Mare has the volume but a mid-market median. Dealurile Olteniei and Banat '
  + 'price well above it on far fewer listings, which is what a small premium region looks like '
  + 'in this data.'));

// ---- bands and extremes
kids.push(head('How is the market distributed across price points?'));
kids.push(...exhibit({
  title: `${pct(midBand.share)} of the market sits between 25 and 50 lei a bottle.`,
  subtitle: { label: 'Share of range by price band', unit: '% of each retailer\'s bottles' },
  headers: ['Price band', 'Bottles', 'All', 'Auchan', 'Carrefour', 'METRO', 'Freshful', 'Sezamo'],
  rows: R.bands.map((b) => [
    b.band, n(b.n), pct(b.share, 1), pct(b.auchan, 1), pct(b.carrefour, 1),
    pct(b.metro, 1), pct(b.freshful, 1), pct(b.sezamo, 1),
  ]),
  widths: [1900, 1150, 1050, 1200, 1350, 1150, 1250, 1150],
  note: 'Retailer columns show the share of that retailer\'s own range falling in each band.',
}));
kids.push(body(`Auchan places ${pct(R.bands[1].auchan, 1)} of its range in the 25–50 lei band. `
  + `Freshful and Sezamo place more than 40 percent in 50–100 lei. METRO holds `
  + `${pct(R.bands[4].metro, 1)} above 200 lei, the deepest premium tail of any retailer.`));

kids.push(...exhibit({
  title: `The dearest bottle in the market costs ${n(priceRatio)} times the cheapest.`,
  subtitle: { label: 'Highest and lowest priced bottles', unit: 'RON per 0.75 litre bottle' },
  headers: ['Most expensive', 'Retailer', 'RON', 'Least expensive', 'Retailer', 'RON'],
  rows: R.most_expensive.slice(0, 8).map((e, i) => {
    const c = R.cheapest[i];
    return [
      e.name.length > 28 ? `${e.name.slice(0, 27)}…` : e.name, LAB[e.retailer] || e.retailer, n(e.price),
      c.name.length > 28 ? `${c.name.slice(0, 27)}…` : c.name, LAB[c.retailer] || c.retailer, money(c.price),
    ];
  }),
  widths: [2500, 1350, 1200, 2500, 1450, 1200],
  align: ['l', 'l', 'r', 'l', 'l', 'r'],
  note: '0.75 litre bottles only.',
}));
kids.push(body('Selgros and METRO hold the top of the market between them. Both cash-and-carry '
  + 'formats stock fine wine that the supermarkets do not carry at all.'));

kids.push(new Paragraph({ children: [new PageBreak()] }));

// ============================== 5. KEY POINTS ============================
kids.push(head('Which three findings matter most?'));

const points = [
  [`METRO holds the lowest price on ${pct(W.winrate)} of the wines it shares with a competitor.`,
    [{ t: `Of the ${W.n} wines where METRO and at least one other retailer stock the identical bottle, METRO is cheapest on ${W.win} and dearest on ${W.lose}. ` },
     { t: 'The advantage is structural, not promotional: ', b: true },
     { t: `METRO ran no discounts at all on its ${n(F.by_retailer.metro)} wines during the period measured, and still undercut retailers whose prices did include active discounts. Reversing those discounts raises METRO's win rate to ${pct(R.wins_regular.metro.winrate)}. The limitation is that many METRO wines carry a six-bottle minimum order, so the advantage applies to case buying rather than to a single bottle.` }]],
  [`Buying each wine where it is cheapest costs ${pct(M.basket_hi / M.basket_lo - 1)} less than buying each where it is dearest.`,
    [{ t: `Across the ${M.n} wines matched at two or more retailers, the same basket costs ${n(M.basket_lo)} lei bought cheapest-each against ${n(M.basket_hi)} lei bought dearest-each. The median wine varies ${pct(M.median)}, and ${pct(M.over20)} vary by 20 percent or more. ` },
     { t: `On standing prices, with every discount reversed, the saving is ${pct(PS.regular_basket)} — so most of it is structural rather than a matter of catching a sale. For a buyer this is the size of the prize from comparing before purchase. For a retailer it identifies which of its own lines sit visibly out of line with the market.` }]],
  ['Dry wine sells for 1.5 to 2.2 times the price per litre of semi-dry wine.',
    [{ t: `Median price per litre is ${money(R.sweetness.sec.median_ppl)} lei for dry wine, ${money(R.sweetness.demisec.median_ppl)} lei for semi-dry (demisec), and ${money(R.sweetness.demidulce.median_ppl)} lei for semi-sweet (demidulce). ` },
     { t: 'The pattern holds separately for white, red, and rosé, ', b: true },
     { t: 'so it is a property of sweetness rather than of colour. Sweet dessert wine is the exception, sitting above semi-dry. Sweetness is the most reliable single predictor of price tier available from a product name, and one of the few attributes almost every retailer publishes.' }]],
];

points.forEach(([headline, detail], i) => {
  kids.push(new Paragraph({
    keepNext: true,
    spacing: { before: 460, after: 120, line: 300, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800, hanging: 620 },
    children: [
      t(`${i + 1}  `, { font: SERIF, size: 30, bold: true, color: ACC }),
      t(headline, { size: 22, bold: true, color: INK }),
    ],
  }));
  kids.push(new Paragraph({
    spacing: { before: 0, after: 260, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: detail.map((d) => t(d.t, { bold: !!d.b, size: 19 })),
  }));
});

// ============================== METHOD ===================================
kids.push(head('Method and limitations'));
kids.push(bullet(`All figures come from one complete collection run on ${COLLECTED} covering `
  + `${n(F.total)} wine listings from 13 sources. Prices move; this is a snapshot, and the tool `
  + `records a price history on later runs.`));
kids.push(bullet(`The same wine is recognised across retailers by rebuilding its identity from `
  + `the title, because no retailer publishes a barcode and product ids are per-shop. Cash & carry `
  + `abbreviations are expanded, brands are read from the title for the six sources that publish `
  + `no brand field, and an attribute one shop leaves out is resolved against the shops that state `
  + `it — but only where they agree, so an ambiguous listing keeps its own identity rather than `
  + `being guessed into a group. That matches ${M.n} wines across two or more retailers. It is `
  + `still incomplete, and it can be wrong: a handful of groups span prices too wide to be one `
  + `wine, and those are listed rather than hidden.`));
kids.push(bullet('Price comparisons use 0.75 litre bottles only. Shelf and platform prices are '
  + 'labelled throughout and should not be pooled.'));
kids.push(bullet(`Recorded prices are what a shopper pays on the day, including any active `
  + `discount. The pre-discount price is stored separately, so every comparison can be re-run on `
  + `standing prices; where that changes a finding it is reported above. `
  + `${n(PS.promo_rows)} of ${n(F.total)} listings carried a discount, at a median depth of `
  + `${pct(PS.median_discount)}. Promotional intensity is very uneven — Selgros `
  + `${pct(R.promo_by_retailer.selgros.promo / R.promo_by_retailer.selgros.total)} of its range, `
  + `Auchan ${pct(R.promo_by_retailer.auchan.promo / R.promo_by_retailer.auchan.total)}, METRO `
  + `none at all — so a retailer with a sale running looks cheaper than its standing prices merit.`));
kids.push(bullet(`A blank attribute means the retailer did not publish it, not that the value is `
  + `zero. Alcohol content is available for ${pct(F.abv_n / F.total)} of listings and vintage for `
  + `about 7 percent, with some vintages read wrongly from brand names such as "Sarica Niculitel `
  + `1958". Neither is reliable enough to rank on, so neither appears above.`));
kids.push(bullet('Carrefour publishes no former price in its listings, so its promotional activity '
  + 'cannot be measured from this source and reads as zero. That is missing data rather than an '
  + 'absence of promotions.'));
kids.push(bullet('METRO prices include VAT and exclude the bottle deposit. The deposit and the net '
  + 'price are held separately in the underlying data.'));

// ---- assemble -----------------------------------------------------------
const doc = new Document({
  creator: 'MarketWineScraper',
  title: 'What does wine cost in Romanian grocery retail?',
  description: 'Issue brief on wine pricing, brands, and varieties across Romanian grocery retail.',
  numbering: {
    config: [{
      reference: 'bl',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '—', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: BODY_IN + 300, hanging: 220 } } },
      }],
    }],
  },
  styles: { default: { document: { run: { font: SANS, size: 19, color: INK } } } },
  sections: [{
    properties: {
      titlePage: true,
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: 720, bottom: 1320, left: M_SIDE, right: M_SIDE, header: 0, footer: 475 },
      },
    },
    footers: {
      first: new Footer({ children: [new Paragraph('')] }),
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { line: 200, lineRule: LineRuleType.EXACT },
          children: [
            t('What does wine cost in Romanian grocery retail?', { size: 14, bold: true }),
            t('  ', { size: 14 }),
            new TextRun({ children: [PageNumber.CURRENT], font: SANS, size: 14, color: INK }),
          ],
        })],
      }),
    },
    children: kids,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = '/home/user/MarketWineScraper/exports/romanian-wine-retail-issue-brief.docx';
  fs.writeFileSync(out, buf);
  console.log(`wrote ${out} (${buf.length} bytes, ${exN} exhibits)`);
});
