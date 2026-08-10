// Romanian wine retail — issue brief, McKinsey-style layout.
// Plain, direct prose. Exhibits carry action titles that state the finding.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, PageBreak,
  Header, Footer, PageNumber, LevelFormat, VerticalAlign,
} = require('docx');
const fs = require('fs');

// ---- palette (McKinsey deep blue family) -------------------------------
const DEEP = '051C2C';   // deep blue — headings, cover
const BLUE = '2251FF';   // accent blue — rules, exhibit numbers
const CYAN = '00A9F4';   // secondary accent
const INK = '1A1A1A';    // body text
const MUTE = '6B7785';   // captions, source lines
const RULE = 'D6DBE1';
const BAND = 'F2F5F8';   // zebra / panel fill
const SANS = 'Arial';
const SERIF = 'Georgia';

const PAGE_W = 12240, PAGE_H = 15840;
const M_TOP = 1080, M_SIDE = 1260, M_BOT = 1080;
const CW = PAGE_W - 2 * M_SIDE;           // 9720

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

let exhibitNo = 0;

// ---- building blocks ---------------------------------------------------
const gap = (after) => new Paragraph({ spacing: { before: 0, after }, children: [] });

function txt(text, o = {}) {
  return new TextRun({
    text, font: o.font || SANS, size: o.size || 20,
    bold: !!o.bold, italics: !!o.italic, color: o.color || INK,
  });
}

function para(text, o = {}) {
  return new Paragraph({
    spacing: { before: o.before || 0, after: o.after == null ? 160 : o.after, line: o.line || 288 },
    alignment: o.align || AlignmentType.LEFT,
    indent: o.indent,
    children: Array.isArray(text) ? text : [txt(text, o)],
  });
}

function sectionHead(num, text) {
  return [
    new Paragraph({
      spacing: { before: 420, after: 0 },
      border: { top: { style: BorderStyle.SINGLE, size: 16, color: BLUE, space: 2 } },
      children: [],
    }),
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 120, after: 200 },
      children: [
        txt(`${num}  `, { font: SANS, size: 26, bold: true, color: BLUE }),
        txt(text, { font: SANS, size: 26, bold: true, color: DEEP }),
      ],
    }),
  ];
}

function subHead(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [txt(text, { size: 21, bold: true, color: DEEP })],
  });
}

function bullet(runs, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bl', level },
    spacing: { before: 0, after: 100, line: 288 },
    children: Array.isArray(runs) ? runs : [txt(runs)],
  });
}

// Exhibit: numbered label, action title stating the finding, table, source line.
function exhibit(title, headers, rows, widths, opts = {}) {
  exhibitNo += 1;
  const out = [];
  out.push(new Paragraph({
    spacing: { before: 340, after: 40 },
    children: [txt(`EXHIBIT ${exhibitNo}`, { size: 15, bold: true, color: BLUE })],
  }));
  out.push(new Paragraph({
    spacing: { before: 0, after: 140 },
    children: [txt(title, { size: 21, bold: true, color: DEEP })],
  }));

  const align = opts.align || headers.map((_, i) => (i === 0 ? 'l' : 'r'));
  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: { top: 70, bottom: 70, left: 100, right: 100 },
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
        bottom: { style: BorderStyle.SINGLE, size: 10, color: DEEP },
        left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
        right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      },
      children: [new Paragraph({
        spacing: { before: 0, after: 0 },
        alignment: align[i] === 'l' ? AlignmentType.LEFT : AlignmentType.RIGHT,
        children: [txt(h, { size: 16, bold: true, color: DEEP })],
      })],
    })),
  });

  const bodyRows = rows.map((r, ri) => new TableRow({
    children: r.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      shading: (opts.highlight && opts.highlight(ri))
        ? { type: ShadingType.CLEAR, fill: BAND, color: 'auto' }
        : undefined,
      borders: {
        top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
        bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
        left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
        right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      },
      children: [new Paragraph({
        spacing: { before: 0, after: 0 },
        alignment: align[i] === 'l' ? AlignmentType.LEFT : AlignmentType.RIGHT,
        children: [txt(String(c), {
          size: 17,
          bold: !!(opts.boldRow && opts.boldRow(ri)),
        })],
      })],
    })),
  }));

  out.push(new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    rows: [headRow, ...bodyRows],
  }));

  if (opts.note) {
    out.push(new Paragraph({
      spacing: { before: 90, after: 0 },
      children: [txt(opts.note, { size: 15, color: MUTE })],
    }));
  }
  out.push(new Paragraph({
    spacing: { before: 60, after: 220 },
    children: [txt(opts.source || 'Source: MarketWineScraper, 10 August 2026', { size: 15, color: MUTE })],
  }));
  return out;
}

// "So what" line under an exhibit — one plain sentence.
function sowhat(text) {
  return new Paragraph({
    spacing: { before: 0, after: 220, line: 288 },
    indent: { left: 220 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: CYAN, space: 10 } },
    children: [txt(text, { size: 20 })],
  });
}

function panel(titleText, lines) {
  const kids = [new Paragraph({
    spacing: { before: 0, after: 120 },
    children: [txt(titleText, { size: 19, bold: true, color: DEEP })],
  })];
  lines.forEach((l) => kids.push(new Paragraph({
    numbering: { reference: 'bl', level: 0 },
    spacing: { before: 0, after: 90, line: 288 },
    children: [txt(l, { size: 19 })],
  })));
  return new Table({
    columnWidths: [CW],
    width: { size: CW, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 16, color: DEEP },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CW, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: BAND, color: 'auto' },
        margins: { top: 220, bottom: 200, left: 260, right: 260 },
        children: kids,
      })],
    })],
  });
}

function keyPoint(idx, headline, detail) {
  return new Table({
    columnWidths: [760, CW - 760],
    width: { size: CW, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      bottom: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    },
    rows: [new TableRow({
      children: [
        new TableCell({
          width: { size: 760, type: WidthType.DXA },
          margins: { top: 200, bottom: 200, left: 0, right: 120 },
          verticalAlign: VerticalAlign.TOP,
          children: [new Paragraph({
            spacing: { before: 0, after: 0 },
            children: [txt(String(idx), { font: SERIF, size: 52, bold: true, color: BLUE })],
          })],
        }),
        new TableCell({
          width: { size: CW - 760, type: WidthType.DXA },
          margins: { top: 220, bottom: 200, left: 60, right: 0 },
          children: [
            new Paragraph({
              spacing: { before: 0, after: 110 },
              children: [txt(headline, { size: 22, bold: true, color: DEEP })],
            }),
            new Paragraph({
              spacing: { before: 0, after: 0, line: 288 },
              children: detail.map((d) => txt(d.t, { bold: !!d.b, size: 20 })),
            }),
          ],
        }),
      ],
    })],
  });
}

// ---- derived figures ----------------------------------------------------
const M = F.matches;
const W = F.wins.metro;
const depth = R.depth;
const dLo = depth[0], dHi = depth[depth.length - 1];
const fullRange = depth.filter((d) => d.n >= 200);
const frLo = fullRange[0], frHi = fullRange[fullRange.length - 1];

const children = [];

// ============================== COVER ===================================
children.push(
  new Paragraph({
    spacing: { before: 0, after: 80 },
    children: [txt('ISSUE BRIEF', { size: 17, bold: true, color: BLUE })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 140 },
    children: [txt('Wine pricing and assortment in Romanian grocery retail',
      { font: SERIF, size: 46, bold: true, color: DEEP })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 200 },
    children: [txt('What the shelf data shows about price gaps, brands and varieties',
      { size: 24, color: MUTE })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 320 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 20, color: BLUE, space: 8 } },
    children: [txt(`${n(F.total)} wine listings collected from 13 retail sources · 10 August 2026`,
      { size: 18, color: MUTE })],
  }),
);

children.push(panel('In brief', [
  `The same wine costs different amounts at different shops. Across ${M.n} wines we can match `
  + `reliably, the median gap between the cheapest and the dearest listing is ${pct(M.median)}. `
  + `${pct(M.over20)} of them differ by 20% or more.`,
  `METRO has the lowest price on ${pct(W.winrate)} of the wines it shares with another retailer. `
  + `It ran no promotions at all during the period measured.`,
  `Dry wine costs about twice as much per litre as semi-sweet wine. This holds for white, red `
  + `and rosé separately, so it is not a colour effect.`,
  `Thirteen of the twenty retailers we targeted can be covered. The other seven publish no `
  + `product data anywhere — not on their own sites and not on any delivery platform.`,
]));

// ============================ 1. METHOD =================================
children.push(...sectionHead('1', 'How the data is collected'));
children.push(para(
  'The tool reads each retailer\'s own website the same way a shopper\'s browser does, and writes '
  + 'the result into one common table. Nothing is bought, and no private system is used.'));

children.push(bullet([txt('Find the data source. ', { bold: true }),
  txt('Each retailer serves its product list from somewhere: a catalogue API (Auchan, Sezamo, '
    + 'METRO), a search index (Selgros), plain HTML (Carrefour, Penny), or a delivery platform '
    + 'that carries the shop (Kaufland, Profi, Supeco).')]));
children.push(bullet([txt('Read the wine categories. ', { bold: true }),
  txt('Categories are read from each site\'s own menu rather than typed in by hand, so a shop '
    + 'reorganising its aisles does not silently break the collection.')]));
children.push(bullet([txt('Fill in the missing fields. ', { bold: true }),
  txt('Retailers publish very different amounts of detail. Where a field is published it is used '
    + 'directly. Where it is not, it is read out of the product name. Romanian spelling is '
    + 'normalised so "Fetească Neagră" and "FETEASCA NEAGRA" count as one variety. Anything that '
    + 'cannot be read reliably is left blank rather than guessed.')]));
children.push(bullet([txt('Remove what is not wine. ', { bold: true }),
  txt('Wine aisles contain vinegar, corkscrews and glasses. These are filtered out.')]));
children.push(bullet([txt('Record price changes. ', { bold: true }),
  txt('A new price is stored only when the price actually moves, so the history stays readable '
    + 'across repeated runs.')]));

// ============================ 2. COVERAGE ===============================
children.push(...sectionHead('2', 'What we cover'));
children.push(para(
  'Thirteen sources are live. Nine read the retailer\'s own site. Four read a delivery platform, '
  + 'used where the retailer has no usable site of its own.'));

children.push(...exhibit(
  'Thirteen sources cover every Romanian retailer with a significant wine range',
  ['Retailer', 'Read from', 'Wines', 'What it covers'],
  [
    ['Carrefour', 'Own site', n(F.by_retailer.carrefour), 'Full range'],
    ['Auchan', 'Own site', n(F.by_retailer.auchan), 'Full range, most detail published'],
    ['Selgros', 'Own site', n(F.by_retailer.selgros), 'Full range, price per depot'],
    ['METRO', 'Own site', n(F.by_retailer.metro), 'Full range, 6-bottle minimum common'],
    ['Freshful', 'Own site', n(F.by_retailer.freshful), 'Full range, delivery-only retailer'],
    ['Kaufland', 'Bolt Food', n(F.by_retailer.kaufland_bolt), 'Full range via the platform'],
    ['Sezamo', 'Own site', n(F.by_retailer.sezamo), 'Full range, delivery-only retailer'],
    ['Mega Image', 'Own site', n(F.by_retailer.mega_image), 'Full range'],
    ['Supeco', 'Glovo', n(F.by_retailer.supeco_glovo), 'Only available route'],
    ['Penny', 'Bolt Food', n(F.by_retailer.penny_bolt), 'Wider than its own site'],
    ['Profi', 'Glovo', n(F.by_retailer.profi_glovo), 'Only available route'],
    ['Penny', 'Own site', n(F.by_retailer.penny), 'Shelf-price reference'],
    ['Kaufland', 'Leaflet', n(F.by_retailer.kaufland), 'Weekly promotions only'],
  ],
  [2300, 1500, 1100, 4820],
  { align: ['l', 'l', 'r', 'l'] },
));

children.push(subHead('Three kinds of price, which must not be mixed'));
children.push(bullet([txt('Shelf price. ', { bold: true }),
  txt('From the retailer\'s own site. These compare directly with each other.')]));
children.push(bullet([txt('Platform price. ', { bold: true }),
  txt('What the delivery app charges. For Penny we checked this against its own website and '
    + 'found no difference at all across 27 shared wines. Glovo adds the 0.50 lei bottle deposit '
    + 'into the displayed price, so Glovo rows sit slightly above shelf.')]));
children.push(bullet([txt('Promotion-only feed. ', { bold: true }),
  txt('Kaufland\'s weekly leaflet lists discounted wines only. It is not that shop\'s range.')]));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ============================ 3. GAPS ==================================
children.push(...sectionHead('3', 'What we cannot cover, and why'));
children.push(para(
  'Seven retailers cannot be covered. For each one we checked the retailer\'s own site and all '
  + 'four Romanian delivery platforms — Bolt Food, Glovo, Wolt and Bringo. The data does not '
  + 'exist in public form anywhere.'));

children.push(...exhibit(
  'Seven retailers publish no wine data on any channel',
  ['Retailer', 'Reason'],
  [
    ['Lidl', 'Its online shop sells no wine. Not on any delivery platform.'],
    ['La Cocoș', 'Website blocks automated access (HTTP 403), including from a real browser.'],
    ['La Doi Pași', 'Franchise network. The official site publishes a leaflet, not a catalogue.'],
    ['Annabella', 'Product sitemap lists 18 items, none of them wine.'],
    ['Unicarm', 'Single-page website with no product listing.'],
    ['Froo', 'Marketing site only. Sitemap contains no products.'],
    ['Atac', 'No public product listing found anywhere.'],
  ],
  [2300, 7420],
  {
    align: ['l', 'l'],
    source: 'Source: Checks against retailer websites and Bolt Food (8 cities), Glovo (9,979 '
      + 'Romanian store pages), Wolt (16,408 Romanian venues) and Bringo, 10 August 2026',
  },
));

children.push(subHead('What it would take to close the gap'));
children.push(para('There are three options. None of them is a scraping problem.'));
children.push(bullet([txt('Read the weekly leaflets. ', { bold: true }),
  txt('Kimbino and Tiendeo republish leaflets for five of the seven. They are scanned images, so '
    + 'the text has to be read by OCR, and a leaflet holds roughly ten wines on promotion rather '
    + 'than a range. Cheap, inaccurate, and covers promotions only.')]));
children.push(bullet([txt('Photograph the shelves. ', { bold: true }),
  txt('This is the only way to get a complete and correct range for these shops. It is manual '
    + 'and has to be repeated per store.')]));
children.push(bullet([txt('Buy panel data. ', { bold: true }),
  txt('Nielsen, GfK and similar firms already sell this coverage.')]));
children.push(para(
  'Our recommendation is to leave the gap open and documented. These seven are mostly hard '
  + 'discounters with narrow wine ranges, and the thirteen covered sources already include every '
  + 'retailer with a wine range worth tracking.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ============================ 4. RANKINGS ==============================
children.push(...sectionHead('4', 'What the rankings show'));

// --- 4.1 price ladder
children.push(subHead('4.1  Where each retailer sits on price'));
children.push(para(
  'Every retailer starts at roughly the same place. The cheapest bottle is between 9 and 15 lei '
  + 'almost everywhere. What separates them is how much range sits above that floor.'));

children.push(...exhibit(
  'Median price per litre varies by 71% across full-range retailers, but entry prices do not',
  ['Retailer', 'Bottles', 'Brands', 'Cheapest 10%', 'Median', 'Dearest 10%', 'Share 200+ lei'],
  depth.map((d) => [
    LAB[d.retailer], n(d.n), n(d.brands), money(d.p10), money(d.median), money(d.p90),
    pct(d.over200, 1),
  ]),
  [1900, 1050, 1000, 1500, 1300, 1450, 1520],
  {
    note: 'Prices are RON per litre, 0.75 L bottles only, shelf-price retailers only. '
      + 'Penny publishes no brand field, so its brand count is zero.',
  },
));
children.push(sowhat(
  `Median price per litre runs from ${money(frLo.median)} lei at ${LAB[frLo.retailer]} to `
  + `${money(frHi.median)} lei at ${LAB[frHi.retailer]}. The two delivery-only retailers, `
  + `Freshful and Sezamo, are the most expensive. They also carry the widest brand counts relative `
  + `to their size, which is what a curated range looks like.`));

// --- 4.2 win rate
children.push(subHead('4.2  Who is actually cheapest on the same wine'));
children.push(para(
  'Median price describes a retailer\'s range, not its competitiveness — a shop looks expensive '
  + 'simply for stocking expensive wine. The fair test is to take wines that two retailers both '
  + 'carry and see who prices them lower.'));

children.push(...exhibit(
  'METRO has the lowest price on four out of five wines it shares with a competitor',
  ['Retailer', 'Shared wines', 'Times cheapest', 'Win rate', 'Times dearest', 'Loss rate'],
  Object.entries(F.wins).sort((a, b) => b[1].winrate - a[1].winrate).map(([k, v]) => [
    LAB[k], n(v.n), n(v.win), pct(v.winrate), n(v.lose), pct(v.loserate),
  ]),
  [2200, 1700, 1700, 1400, 1560, 1160],
  {
    highlight: (ri) => ri === 0,
    note: 'Retailers appearing in at least ten matched wines. Win rate is the share of a '
      + 'retailer\'s matched wines on which it is the cheapest of those carrying it.',
  },
));
children.push(sowhat(
  `METRO wins ${W.win} of ${W.n}. Selgros, the other cash-and-carry, wins only `
  + `${pct(F.wins.selgros.winrate)} and is the dearest on ${pct(F.wins.selgros.loserate)} — the two `
  + `wholesale formats price very differently. Check METRO first for any specific wine, but note `
  + `that many of its lines require buying six bottles.`));

// --- 4.3 biggest gaps
children.push(subHead('4.3  Where the gaps are widest'));
children.push(...exhibit(
  'On some identical wines the dearest retailer charges more than double the cheapest',
  ['Wine', 'Cheapest', 'at', 'Dearest', 'at', 'Gap'],
  R.biggest_gaps.slice(0, 12).map((m) => [
    m.name.length > 44 ? `${m.name.slice(0, 43)}…` : m.name,
    money(m.lo), LAB[m.cheap] || m.cheap, money(m.hi), LAB[m.dear] || m.dear, pct(m.spread),
  ]),
  [3500, 1100, 1550, 1100, 1550, 920],
  {
    align: ['l', 'r', 'l', 'r', 'l', 'r'],
    note: 'Same brand, same product wording, same bottle size at both retailers.',
  },
));
children.push(sowhat(
  'These are not different vintages or sizes — the brand, the wording and the bottle size all '
  + 'match. A buyer who checks two shops before buying captures most of this gap.'));

// --- 4.4 most widely stocked
children.push(subHead('4.4  Which wines are stocked everywhere'));
children.push(...exhibit(
  'Only a handful of labels are carried by four or more retailers',
  ['Wine', 'Retailers', 'Cheapest', 'Dearest', 'Gap'],
  R.most_widely_stocked.slice(0, 12).map((m) => [
    m.name.length > 50 ? `${m.name.slice(0, 49)}…` : m.name,
    n(m.retailers), money(m.lo), money(m.hi), pct(m.spread),
  ]),
  [4600, 1300, 1300, 1300, 1220],
  { note: 'Matched on identical brand, product wording and bottle size.' },
));
children.push(sowhat(
  'Beciul Domnesc and Domeniile Sâmburești appear at four retailers each. Wines this widely '
  + 'distributed have the tightest price gaps, because shoppers can compare them directly.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// --- 4.5 brands
children.push(subHead('4.5  Brands'));
children.push(para(
  `The dataset contains ${n(R.n_brands)} distinct brands. Presence and price position are `
  + `different things, so both are worth ranking.`));

children.push(...exhibit(
  'Jidvei has the most listings, but Zarea reaches the most retailers',
  ['Brand', 'Listings', 'Retailers', 'Median RON/L', 'Cheapest', 'Dearest'],
  R.brands_by_listings.slice(0, 14).map((b) => [
    b.brand, n(b.listings), n(b.retailers),
    b.median_ppl == null ? '—' : money(b.median_ppl), money(b.min), money(b.max),
  ]),
  [2800, 1300, 1300, 1620, 1350, 1350],
  { note: 'Shelf-price retailers only.' },
));
children.push(sowhat(
  `Jidvei has ${n(R.brands_by_listings[0].listings)} listings but appears at `
  + `${R.brands_by_listings[0].retailers} retailers. Zarea has fewer listings and reaches all 7. `
  + `Listing count measures how many different wines a brand sells; retailer count measures how `
  + `hard it is to avoid the brand.`));

children.push(...exhibit(
  'The most expensive brands are all Champagne houses; the cheapest are Romanian volume labels',
  ['Premium brand', 'Median RON/L', 'Listings', 'Value brand', 'Median RON/L', 'Listings'],
  R.brands_premium.slice(0, 10).map((b, i) => {
    const v = R.brands_value[i] || { brand: '', median_ppl: '', listings: '' };
    return [b.brand, money(b.median_ppl), n(b.listings),
      v.brand, v.median_ppl === '' ? '' : money(v.median_ppl),
      v.listings === '' ? '' : n(v.listings)];
  }),
  [2400, 1500, 1100, 2400, 1500, 820],
  {
    align: ['l', 'r', 'r', 'l', 'r', 'r'],
    note: 'Brands with at least five listings.',
  },
));
children.push(sowhat(
  `The gap between the top and bottom of this table is about 40 times. Louis Roederer sits at `
  + `${money(R.brands_premium[0].median_ppl)} lei per litre; VINEXPORT at `
  + `${money(R.brands_value[0].median_ppl)}. There is no meaningful competition between these two `
  + `ends of the market.`));

// --- 4.6 grapes
children.push(subHead('4.6  Grape varieties'));
children.push(para(
  `${n(R.n_grapes)} varieties appear across the dataset, but five account for most of what is on `
  + `the shelf.`));

children.push(...exhibit(
  'Fetească Neagră is the only Romanian variety in the top five by listings',
  ['Variety', 'Listings', 'Retailers', 'Median RON/L', 'Dearest 10%'],
  R.grapes_by_listings.slice(0, 14).map((g) => [
    g.grape, n(g.listings), n(g.retailers), money(g.median_ppl), money(g.p90),
  ]),
  [3100, 1400, 1400, 1800, 2020],
  { note: 'Varieties with at least 15 listings. A wine may list more than one variety.' },
));

children.push(...exhibit(
  'Imported varieties price highest; Romanian white varieties price lowest',
  ['Most expensive variety', 'Median RON/L', 'Listings', 'Cheapest variety', 'Median RON/L', 'Listings'],
  R.grapes_by_price.slice(0, 10).map((g, i) => {
    const c = R.grapes_cheapest[i] || { grape: '', median_ppl: '', listings: '' };
    return [g.grape, money(g.median_ppl), n(g.listings),
      c.grape, c.median_ppl === '' ? '' : money(c.median_ppl),
      c.listings === '' ? '' : n(c.listings)];
  }),
  [2500, 1500, 1050, 2500, 1500, 670],
  { align: ['l', 'r', 'r', 'l', 'r', 'r'] },
));
children.push(sowhat(
  `Sangiovese, Tempranillo and Primitivo — all imported — carry the highest median prices. `
  + `Negru de Drăgășani at ${money(R.grapes_by_price.find((g) => g.grape.toLowerCase().includes('negru')).median_ppl)} `
  + `lei per litre is the most expensive Romanian variety, and Grasă de Cotnari at `
  + `${money(R.grapes_cheapest[0].median_ppl)} lei is the cheapest. A Romanian producer wanting a `
  + `premium price has an easier case with Negru de Drăgășani than with a white variety.`));

children.push(new Paragraph({ children: [new PageBreak()] }));

// --- 4.7 colour and style
children.push(subHead('4.7  Colour, style and sweetness'));

children.push(...exhibit(
  'Red is the most expensive colour and rosé the cheapest, but the range is narrow',
  ['Category', 'Bottles', 'Share of range', 'Median RON/L'],
  [
    ['White', n(R.colour.alb.n), pct(R.colour.alb.share, 1), money(R.colour.alb.median_ppl)],
    ['Red', n(R.colour.rosu.n), pct(R.colour.rosu.share, 1), money(R.colour.rosu.median_ppl)],
    ['Rosé', n(R.colour.rose.n), pct(R.colour.rose.share, 1), money(R.colour.rose.median_ppl)],
    ['Sparkling', n(R.colour.sparkling.n), pct(R.colour.sparkling.share, 1), money(R.colour.sparkling.median_ppl)],
    ['Still', n(R.colour.still.n), pct(R.colour.still.share, 1), money(R.colour.still.median_ppl)],
  ],
  [2600, 1900, 2400, 2820],
  { note: '0.75 L bottles, shelf-price retailers. Colour shares do not total 100% because some '
      + 'listings do not state a colour.' },
));

children.push(...exhibit(
  'Dry wine costs roughly twice as much per litre as semi-sweet wine, in every colour',
  ['Sweetness', 'White', 'Red', 'Rosé', 'All bottles', 'Share of range'],
  [
    ['Sec (dry)', '65.32', '73.32', '58.65', money(R.sweetness.sec.median_ppl), pct(R.sweetness.sec.share, 1)],
    ['Demisec', '35.97', '33.24', '39.19', money(R.sweetness.demisec.median_ppl), pct(R.sweetness.demisec.share, 1)],
    ['Demidulce', '27.05', '27.57', '37.99', money(R.sweetness.demidulce.median_ppl), pct(R.sweetness.demidulce.share, 1)],
    ['Dulce (sweet)', '—', '—', '—', money(R.sweetness.dulce.median_ppl), pct(R.sweetness.dulce.share, 1)],
  ],
  [2200, 1400, 1400, 1400, 1700, 1620],
  {
    highlight: (ri) => ri === 0,
    note: 'Median RON per litre, 0.75 L bottles. Dashes mark cells with too few bottles to report.',
  },
));
children.push(sowhat(
  'This is the strongest single price signal in the data, and it is not a colour effect: dry '
  + 'wine prices roughly double semi-sweet in white, red and rosé separately. Sweetness is a '
  + 'reliable proxy for price tier in this market — useful when positioning a new label, and '
  + 'useful as a sanity check on any price forecast.'));

// --- 4.8 origin
children.push(subHead('4.8  Origin and region'));
children.push(...exhibit(
  'Romanian wine is 58% of bottles where the retailer states an origin',
  ['Country', 'Bottles', 'Median RON/L'],
  R.countries.slice(0, 10).map((c) => [c.country, n(c.listings), money(c.median_ppl)]),
  [4000, 2860, 2860],
  {
    note: `Origin is published for ${n(R.country_known)} of ${n(R.n_std)} standard bottles `
      + `(${pct(R.country_known / R.n_std)}), almost entirely by Auchan and METRO.`,
  },
));

children.push(...exhibit(
  'Dealu Mare is the largest named region; Tuscany and Banat carry the highest prices',
  ['Region', 'Bottles', 'Median RON/L'],
  R.regions.slice(0, 12).map((r) => [r.region, n(r.listings), money(r.median_ppl)]),
  [4000, 2860, 2860],
  { note: 'Regions with at least eight bottles. Region is published by Auchan and METRO only.' },
));
children.push(sowhat(
  'Dealu Mare has the volume but a mid-market median. Dealurile Olteniei and Banat price well '
  + 'above it on far fewer listings, which is what a small premium region looks like in the data.'));

// --- 4.9 price bands
children.push(subHead('4.9  Price bands'));
children.push(...exhibit(
  'Nearly half the market sits between 25 and 50 lei a bottle',
  ['Price band', 'Bottles', 'Share', 'Auchan', 'Carrefour', 'METRO', 'Freshful', 'Sezamo'],
  R.bands.map((b) => [
    b.band, n(b.n), pct(b.share, 1), pct(b.auchan, 1), pct(b.carrefour, 1),
    pct(b.metro, 1), pct(b.freshful, 1), pct(b.sezamo, 1),
  ]),
  [1900, 1100, 1000, 1150, 1250, 1100, 1150, 1070],
  { note: 'Retailer columns show what share of that retailer\'s own range falls in each band.' },
));
children.push(sowhat(
  `Auchan puts ${pct(R.bands[1].auchan, 1)} of its range in the 25–50 lei band. Freshful and `
  + `Sezamo put more than 40% in 50–100 lei. METRO holds ${pct(R.bands[4].metro, 1)} above 200 `
  + `lei, the deepest premium tail of any retailer.`));

// --- 4.10 extremes
children.push(subHead('4.10  The two ends of the shelf'));
children.push(...exhibit(
  'The dearest bottle costs 269 times the cheapest',
  ['Most expensive', 'Retailer', 'RON', 'Cheapest', 'Retailer', 'RON'],
  R.most_expensive.slice(0, 8).map((e, i) => {
    const c = R.cheapest[i];
    return [
      e.name.length > 30 ? `${e.name.slice(0, 29)}…` : e.name, LAB[e.retailer] || e.retailer, n(e.price),
      c.name.length > 30 ? `${c.name.slice(0, 29)}…` : c.name, LAB[c.retailer] || c.retailer, money(c.price),
    ];
  }),
  [2450, 1250, 1150, 2450, 1250, 1170],
  { align: ['l', 'l', 'r', 'l', 'l', 'r'], note: '0.75 L bottles only.' },
));
children.push(sowhat(
  'Selgros and METRO hold the top of the market between them. Both cash-and-carry formats carry '
  + 'fine wine that the supermarkets do not stock at all.'));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ============================ 5. KEY POINTS ============================
children.push(...sectionHead('5', 'The three most useful findings'));

children.push(keyPoint(1,
  `METRO has the lowest price on ${pct(W.winrate)} of the wines it shares with a competitor`,
  [
    { t: `Of the ${W.n} wines where METRO and at least one other retailer stock the identical bottle, METRO is cheapest on ${W.win} and dearest on ${W.lose}. ` },
    { t: 'This is not a promotion. ', b: true },
    { t: `METRO ran no discounts at all on its ${n(F.by_retailer.metro)} wines during the period measured, and still undercut retailers whose prices did include active discounts. The limitation is that many METRO wines require buying six bottles, so the advantage applies to case buying, not to a single bottle.` },
  ]));

children.push(keyPoint(2,
  `Buying each wine where it is cheapest costs ${pct(M.basket_hi / M.basket_lo - 1)} less than buying each where it is dearest`,
  [
    { t: `Across the ${M.n} wines matched at two or more retailers, the same basket costs ${n(M.basket_lo)} lei at the cheapest source for each wine, against ${n(M.basket_hi)} lei at the dearest. The median wine varies ${pct(M.median)}; ${pct(M.over20)} vary by 20% or more; the widest gap is ${pct(M.max)}. ` },
    { t: 'For a buyer this is the size of the prize from comparing before purchase. For a retailer it identifies which of its own lines are visibly out of line with the market.' },
  ]));

children.push(keyPoint(3,
  'Dry wine sells for about twice the price per litre of semi-sweet wine',
  [
    { t: `Median price per litre is ${money(R.sweetness.sec.median_ppl)} lei for dry wine against ${money(R.sweetness.demisec.median_ppl)} lei for semi-dry and ${money(R.sweetness.demidulce.median_ppl)} lei for semi-sweet. ` },
    { t: 'The pattern holds separately for white, red and rosé, ', b: true },
    { t: 'so it is a property of sweetness rather than of colour. Sweetness is therefore the most reliable single predictor of price tier available from a product name — which matters because it is also one of the few attributes almost every retailer publishes.' },
  ]));

// ============================ METHOD ===================================
children.push(...sectionHead('', 'Method and limitations'));
children.push(bullet('All figures come from one complete collection run on 10 August 2026 covering '
  + `${n(F.total)} wine listings from 13 sources. Prices move; this is a snapshot, and the tool `
  + 'records a price history on later runs.'));
children.push(bullet(`Matching the same wine across retailers requires the brand, the full set of `
  + `distinctive words in the product name, and the bottle size to be identical. This is accurate `
  + `but incomplete: wines described differently by different shops are missed, so the ${M.n} `
  + `matched wines understate how much overlap exists. A looser matching rule was tested and `
  + `rejected after it grouped genuinely different wines together and produced false price gaps `
  + `of 130% and more.`));
children.push(bullet('Price comparisons use 0.75 L bottles only. Shelf and platform prices are '
  + 'labelled throughout and should not be pooled.'));
children.push(bullet('A blank attribute means the retailer did not publish it, not that the value '
  + `is zero. Alcohol content is available for only ${pct(F.abv_n / F.total)} of listings, and `
  + 'vintage for 7%, with some vintages picked up wrongly from brand names such as "Sarica '
  + 'Niculitel 1958". Neither is reliable enough to rank on, so neither appears above.'));
children.push(bullet('Carrefour publishes no former price in its listings, so its promotional '
  + 'activity cannot be measured from this source and reads as zero. That is missing data, not an '
  + 'absence of promotions.'));
children.push(bullet('METRO prices include VAT and exclude the bottle deposit. The deposit and the '
  + 'net price are held separately in the underlying data.'));

// ---- assemble ----------------------------------------------------------
const doc = new Document({
  creator: 'MarketWineScraper',
  title: 'Wine pricing and assortment in Romanian grocery retail',
  description: 'Issue brief on wine pricing, brands and varieties across Romanian grocery retail.',
  numbering: {
    config: [{
      reference: 'bl',
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: '—', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 220 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '·', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 700, hanging: 220 } } } },
      ],
    }],
  },
  styles: { default: { document: { run: { font: SANS, size: 20, color: INK } } } },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: M_TOP, bottom: M_BOT, left: M_SIDE, right: M_SIDE },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          spacing: { after: 0 },
          tabStops: [{ type: TabStopType.RIGHT, position: CW }],
          children: [
            txt('Romanian wine retail', { size: 15, bold: true, color: DEEP }),
            txt('\tIssue brief', { size: 15, color: MUTE }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          spacing: { before: 0 },
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 6 } },
          tabStops: [{ type: TabStopType.RIGHT, position: CW }],
          children: [
            txt('MarketWineScraper · 7,513 listings · 13 sources', { size: 14, color: MUTE }),
            txt('\t', { size: 14 }),
            new TextRun({ children: [PageNumber.CURRENT], font: SANS, size: 14, color: MUTE }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = '/home/user/MarketWineScraper/exports/romanian-wine-retail-issue-brief.docx';
  fs.writeFileSync(out, buf);
  console.log(`wrote ${out} (${buf.length} bytes, ${exhibitNo} exhibits)`);
});
