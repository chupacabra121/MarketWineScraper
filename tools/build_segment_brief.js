// Entry-segment brief: 2 L wine under 10 lei per litre, Muscatel against the rest.
// Same house style as build_issue_brief.js — two-measure grid, Georgia display
// against Arial body, black headings, hairline-only tables, exhibit titles that
// state the finding. Written in Romanian, because the audience and the shelf are.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  Footer, PageNumber, LevelFormat, VerticalAlign, LineRuleType, HeightRule,
  TableLayoutType,
} = require('docx');
const fs = require('fs');

const INK = '231F20';
const BLACK = '000000';
const NAVY = '051C2C';
const TITLE = '00162B';
const ACC = '2251FF';
const GREY = '656565';
const HAIR = '757575';
const SANS = 'Arial';
const SERIF = 'Georgia';

const PAGE_W = 12240, PAGE_H = 15840;
const M_SIDE = 1020;
const FULL = PAGE_W - 2 * M_SIDE;
const BODY_IN = 1746;

const F = JSON.parse(fs.readFileSync('/tmp/segment_facts.json', 'utf8'));
const B = F.benchmark;

const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
const n = (v) => Number(v).toLocaleString('ro-RO');
const lei = (v) => Number(v).toFixed(2).replace('.', ',');
// Whole numbers read badly as "10,00 lei" in running prose.
const plain = (v) => (Number.isInteger(Number(v)) ? String(Number(v)) : lei(v));
// Romanian numeral agreement: 20 and above take "de" before the noun, 1-19 do
// not. "30 de listări" but "6 magazine" — getting this wrong is immediately
// audible to a Romanian reader.
const de = (v) => {
  const value = Number(v);
  const lastTwo = Math.abs(value) % 100;
  return `${n(value)}${lastTwo === 0 || lastTwo > 19 ? ' de' : ''}`;
};
const COLLECTED = new Date(`${F.collected}T00:00:00Z`).toLocaleDateString('ro-RO',
  { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

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

function t(text, o = {}) {
  return new TextRun({
    text, font: o.font || SANS, size: o.size || 19,
    bold: !!o.bold, italics: !!o.italic, color: o.color || INK,
  });
}

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

function head(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    keepNext: true,
    spacing: { before: 720, after: 120, line: 260, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: [t(text, { font: SERIF, size: 24, bold: true, color: INK })],
  });
}

function pullQuote(text) {
  return new Paragraph({
    spacing: { before: 520, after: 400, line: 540, lineRule: LineRuleType.EXACT },
    indent: { left: BODY_IN, right: 800 },
    children: [t(text, { font: SERIF, size: 44, bold: true, color: ACC })],
  });
}

/** Exhibit: the finding leads, the number recedes. Horizontal hairlines only. */
function exhibit({ title, subtitle, headers, rows, widths, align, note, emphasis }) {
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
      children: [t(subtitle, { size: 18, bold: true, color: BLACK })],
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
        height: { value: 380, rule: HeightRule.ATLEAST },
        children: headers.map((h, i) => cell(h, { w: widths[i], a: al[i], bold: true, head: true })),
      }),
      // The benchmark row is bold throughout: it is what everything else is
      // being read against, so it should be findable without counting rows.
      ...rows.map((r, ri) => new TableRow({
        height: { value: 290, rule: HeightRule.ATLEAST },
        children: r.map((c, i) => cell(c, {
          w: widths[i], a: al[i],
          bold: (emphasis && emphasis[ri]) || i === 0,
        })),
      })),
    ],
  }));

  if (note) {
    out.push(new Paragraph({
      spacing: { before: 200, after: 0, line: 135, lineRule: LineRuleType.EXACT },
      children: [t(`Notă: ${note}`, { size: 12, color: GREY })],
    }));
  }
  out.push(new Paragraph({
    spacing: { before: note ? 60 : 200, after: 400, line: 135, lineRule: LineRuleType.EXACT },
    children: [t(`Sursă: MarketWineScraper, colectare ${COLLECTED}`, { size: 12, color: GREY })],
  }));
  return out;
}

// ============================== COVER ====================================
kids.push(new Paragraph({ spacing: { before: 0, after: 0, line: 2000, lineRule: LineRuleType.EXACT }, children: [] }));
kids.push(new Paragraph({
  spacing: { before: 0, after: 0, line: 260, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN },
  children: [t('Analiză de preț — segmentul de intrare', { size: 19, bold: true, color: INK })],
}));
kids.push(new Paragraph({
  spacing: { before: 200, after: 0, line: 620, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN, right: 900 },
  children: [t('Cât costă Muscatel față de tot ce stă lângă el pe raft?',
    { font: SERIF, size: 68, bold: true, color: TITLE })],
}));
kids.push(new Paragraph({
  spacing: { before: 340, after: 0, line: 340, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN, right: 900 },
  children: [t(`Vinul la bidon de 2 litri sub ${plain(F.ceiling)} lei litrul: `
    + `${de(F.n_two_litre)} listări în ${de(F.n_shops)} magazine, și unde se așază `
    + 'Muscatel între ele.', { size: 28 })],
}));
kids.push(new Paragraph({ spacing: { before: 0, after: 0, line: 700, lineRule: LineRuleType.EXACT }, children: [] }));
kids.push(new Table({
  columnWidths: [PAGE_W],
  layout: TableLayoutType.FIXED,
  width: { size: PAGE_W, type: WidthType.DXA },
  indent: { size: -M_SIDE, type: WidthType.DXA },
  borders: NO_BORDERS,
  rows: [new TableRow({
    height: { value: 2600, rule: HeightRule.EXACT },
    children: [new TableCell({
      shading: { fill: NAVY },
      borders: NO_BORDERS,
      children: [new Paragraph({ children: [] })],
    })],
  })],
}));
kids.push(new Paragraph({
  spacing: { before: 300, after: 0, line: 260, lineRule: LineRuleType.EXACT },
  indent: { left: BODY_IN },
  children: [t(COLLECTED, { size: 19, color: GREY })],
}));
kids.push(new Paragraph({ children: [], pageBreakBefore: true }));

// ============================== AT A GLANCE ==============================
kids.push(head('Pe scurt'));
kids.push(bullet([
  t(`Muscatel este cel mai scump vin de 2 litri din segment. `, { bold: true }),
  t(`Toate cele ${de(B.rivals)} listări concurente de 2 litri sub ${plain(F.ceiling)} lei/litru `
    + `costă mai puțin — nu majoritatea, ci toate.`),
]));
kids.push(bullet([
  t('Selgros îl subcotează cu propriul raft. ', { bold: true }),
  t(`Babanu stă la ${lei(F.same_shelf[0].ppl)} lei/litru în același magazin și același `
    + `format, cu ${pct(1 - F.same_shelf[0].ppl / B.ppl)} sub Muscatel.`),
]));
kids.push(bullet([
  t('Bidonul mai mare nu ieftinește litrul. ', { bold: true }),
  t('Formatele de 3 și 5 litri costă mai mult pe litru decât cele de 2 litri. '
    + 'Cumpărătorul plătește în plus pentru volum, nu mai puțin.'),
]));
kids.push(bullet([
  t('Segmentul este o insulă, nu o coadă de distribuție. ', { bold: true }),
  // "de" attaches to a numeral that a noun follows. Nothing follows the second
  // one here, so it takes the bare form: "47 de listări din 6.691 coboară".
  t(`${de(F.n_segment)} listări din ${n(F.n_priced)} coboară sub ${plain(F.ceiling)} lei/litru, `
    + `în timp ce mediana pieței este ${lei(F.market_median_ppl)} lei/litru.`),
]));

// ============================== 1. THE TABLE =============================
kids.push(head('Cum arată raftul de 2 litri'));
kids.push(body([
  t('Un singur format, un singur prag. ', { bold: true }),
  t(`Toate listările sub ${plain(F.ceiling)} lei/litru la 2 litri, ordonate după preț pe litru. `
    + `Muscatel apare de ${n(B.listings)} ori — alb demidulce, alb demisec și roșu demidulce — `
    + 'toate la același preț, și toate pe ultimele locuri.'),
]));

kids.push(...exhibit({
  title: `Muscatel închide lista: ${n(B.cheaper_rivals)} din ${de(B.rivals)} listări concurente sunt mai ieftine.`,
  subtitle: `Vin de 2 litri sub ${plain(F.ceiling)} lei/litru, lei pe litru`,
  headers: ['Vin', 'Magazin', 'Culoare', 'Dulceață', 'Preț', 'Lei/litru'],
  rows: F.rows.map((r) => [
    r.name.length > 34 ? `${r.name.slice(0, 33)}…` : r.name,
    r.retailer, r.colour || '—', r.sweetness || '—', lei(r.price), lei(r.ppl),
  ]),
  emphasis: F.rows.map((r) => r.benchmark),
  widths: [3100, 1750, 1050, 1350, 1150, 1300],
  align: ['l', 'l', 'l', 'l', 'r', 'r'],
  note: 'Preț de listă, fără reduceri. Rândurile îngroșate sunt Muscatel. '
    + 'Rândurile de pe platformele de livrare nu sunt direct comparabile cu cele de raft.',
}));

kids.push(body(`Muscatel stă la ${lei(B.ppl)} lei/litru. Mediana celorlalte este `
  + `${lei(B.rival_median)}, iar pragul de jos ${lei(B.floor)} — deci Muscatel este cu `
  + `${pct(B.vs_median)} peste mediana concurenței și cu ${pct(B.vs_floor)} peste cel mai `
  + 'ieftin vin din format.'));

kids.push(pullQuote(`Nu există niciun vin de 2 litri sub ${plain(F.ceiling)} lei/litru `
  + 'mai scump decât Muscatel.'));

// ============================== 2. SAME SHELF ============================
kids.push(head('Concurența începe în propriul magazin'));
kids.push(body(`Înainte de orice comparație între lanțuri, ${B.retailer} vinde `
  + `${de(F.same_shelf.length)} listări de 2 litri în acest segment, iar Muscatel este cea mai `
  + 'scumpă dintre ele. Un cumpărător care caută prețul nu trebuie să schimbe magazinul.'));

kids.push(...exhibit({
  title: `Pe raftul ${B.retailer}, Muscatel este cea mai scumpă opțiune de 2 litri.`,
  subtitle: `Gama de 2 litri sub ${plain(F.ceiling)} lei/litru la ${B.retailer}, lei pe litru`,
  headers: ['Vin', 'Culoare', 'Dulceață', 'Preț', 'Lei/litru', 'Față de Muscatel'],
  rows: F.same_shelf.map((r) => [
    r.name.length > 32 ? `${r.name.slice(0, 31)}…` : r.name,
    r.colour || '—', r.sweetness || '—', lei(r.price), lei(r.ppl),
    r.benchmark ? '—' : pct(r.ppl / B.ppl - 1),
  ]),
  emphasis: F.same_shelf.map((r) => r.benchmark),
  widths: [3300, 1150, 1400, 1200, 1350, 1600],
  align: ['l', 'l', 'l', 'r', 'r', 'r'],
}));

// ============================== 3. SAME WINE =============================
if (F.same_wine.length) {
  kids.push(head('Același vin, magazine diferite'));
  kids.push(body('Formatul are dispersie mare de preț chiar și acolo unde produsul este '
    + 'identic. Babanu este vândut de patru lanțuri, iar diferența dintre cel mai ieftin și '
    + 'cel mai scump depășește un sfert din preț.'));

  const rows = [];
  const emphasis = [];
  F.same_wine.forEach((group) => {
    group.rows.forEach((r, i) => {
      rows.push([i === 0 ? r.name.split(' ').slice(0, 3).join(' ') : '',
                 r.retailer, lei(r.price), lei(r.ppl),
                 i === 0 ? '—' : pct(r.ppl / group.rows[0].ppl - 1)]);
      emphasis.push(false);
    });
  });
  kids.push(...exhibit({
    title: 'Același vin de 2 litri costă cu până la un sfert mai mult, în funcție de magazin.',
    subtitle: 'Listări legate prin identitatea reconstruită a vinului, lei pe litru',
    headers: ['Vin', 'Magazin', 'Preț', 'Lei/litru', 'Față de cel mai ieftin'],
    rows,
    emphasis,
    widths: [2600, 2100, 1300, 1450, 2250],
    align: ['l', 'l', 'r', 'r', 'r'],
    note: 'Vinurile sunt grupate după identitatea reconstruită din titlu, nu după potrivirea '
      + 'exactă a denumirii: fiecare magazin îl scrie altfel.',
  }));
}

// ============================== 4. FORMAT ================================
kids.push(head('Ajută formatul mai mare?'));
kids.push(body('Intuiția spune că bidonul mai mare aduce litrul mai ieftin. În acest segment '
  + 'nu se întâmplă: 2 litri este formatul cu cel mai ieftin litru, iar 3 și 5 litri costă '
  + 'mai mult pe litru decât el.'));

kids.push(...exhibit({
  title: 'Formatele de 3 și 5 litri costă mai mult pe litru decât cel de 2 litri.',
  subtitle: `Toate formatele sub ${plain(F.ceiling)} lei/litru, lei pe litru`,
  headers: ['Format', 'Listări', 'Minim', 'Median', 'Maxim'],
  rows: F.formats.map((f) => [
    `${f.litres} litri`, n(f.n), lei(f.low), lei(f.median), lei(f.high),
  ]),
  emphasis: F.formats.map((f) => f.litres === 2),
  widths: [2200, 1600, 1800, 1800, 1800],
  note: 'Formatele de 2 litri sunt PET; cele de 3 litri și peste sunt bag-in-box. '
    + 'Numărul de listări per format este mic în afara celui de 2 litri.',
}));

kids.push(body('Singurul format care se apropie de 2 litri este cel de 10 litri de la METRO, '
  + 'care este o achiziție cu totul diferită. Între 2 și 5 litri, litrul se scumpește.'));

// ============================== 5. MIX ===================================
kids.push(head('Culoare și dulceață'));
kids.push(body('În restul pieței vinul sec costă aproximativ dublu față de demisec. În acest '
  + 'segment relația se inversează: demidulcele este cel mai ieftin, iar rozeul cel mai scump.'));

kids.push(...exhibit({
  title: 'Demidulcele este cel mai ieftin sortiment din format, invers față de restul pieței.',
  subtitle: 'Vin de 2 litri sub pragul analizat, lei pe litru',
  headers: ['Sortiment', 'Listări', 'Median lei/litru'],
  rows: [
    ...F.sweetness.map((s) => [s.value, n(s.n), lei(s.median)]),
    ...F.colour.map((c) => [c.value, n(c.n), lei(c.median)]),
  ],
  widths: [3200, 2200, 2600],
  note: 'Primele rânduri sunt dulceața, ultimele culoarea; un vin apare în ambele.',
}));

// ============================== 6. SHOPS =================================
kids.push(head('Cine joacă în acest format'));

kids.push(...exhibit({
  title: 'METRO are volumul, dar formatul contează cu adevărat în mixul Penny.',
  subtitle: `Listări de 2 litri sub ${plain(F.ceiling)} lei/litru, per magazin`,
  headers: ['Magazin', 'Listări', 'Minim', 'Maxim', 'Median gamă totală'],
  rows: F.shops.map((s) => [
    s.retailer, n(s.n), lei(s.low), lei(s.high), lei(s.range_median),
  ]),
  widths: [2700, 1500, 1500, 1500, 2800],
  align: ['l', 'r', 'r', 'r', 'r'],
  note: '"Median gamă totală" este mediana întregii game de vin a magazinului, pentru scară. '
    + `Absente complet din format: ${F.absent.join(', ')}.`,
}));

// ============================== 7. STRUCTURE =============================
kids.push(head('Un lucru structural'));
kids.push(body([
  t(`Sub ${plain(F.ceiling)} lei litrul nu se vinde vin la sticlă. `, { bold: true }),
  t(`Cea mai ieftină sticlă obișnuită de 0,75 litri din toată piața este `
    + `${F.cheapest_bottle.name.replace(/ SGR.*$/, '')} la ${F.cheapest_bottle.retailer}, `
    + `${lei(F.cheapest_bottle.price)} lei — adică ${lei(F.cheapest_bottle.ppl)} lei/litru, `
    + `cu ${pct(F.cheapest_bottle.ppl / B.ppl - 1)} peste Muscatel. Segmentul este exclusiv `
    + 'PET și bag-in-box.'),
]));

// ============================== 8. SO WHAT ===============================
kids.push(head('Ce înseamnă'));
kids.push(bullet([
  t('Muscatel nu are un preț de segment de intrare. ', { bold: true }),
  t(`La ${lei(B.ppl)} lei/litru stă deasupra întregului format, inclusiv deasupra a `
    + `${de(F.same_shelf.length - B.listings)} produse din propriul magazin. Dacă poziția `
    + 'urmărită este prețul, prețul nu o susține.'),
]));
kids.push(bullet([
  t('Pragul real al pieței este ', { bold: true }),
  t(`${lei(B.floor)} lei/litru`, { bold: true }),
  t(`. Acolo stau Carrefour, Kaufland și Penny, cu bidon de 2 litri la `
    + `${lei(F.rows[0].price)} lei. Este nivelul față de care se măsoară orice preț de intrare.`),
]));
kids.push(bullet([
  t('Formatul mare nu este un argument de preț. ', { bold: true }),
  t('3 și 5 litri costă mai mult pe litru decât 2 litri, deci volumul se vinde pe '
    + 'comoditate, nu pe economie.'),
]));

// ============================== METHOD ===================================
kids.push(head('Cum a fost calculat'));
kids.push(bullet(`Prețurile sunt prețuri de listă, fără reduceri: pe ${de(F.n_two_litre)} `
  + 'listări din acest format nu rulează nicio promoție, deci prețul de pe pagină este '
  + 'prețul normal.'));
kids.push(bullet('Prețul pe litru face formatele comparabile și este singura bază pe care '
  + 'un bidon de 2 litri poate fi pus lângă o sticlă.'));
kids.push(bullet('Rândurile de pe platformele de livrare — Bolt Food, Glovo — sunt marcate ca '
  + 'atare. Ele stau la sau peste prețul de raft, iar Glovo include garanția SGR de 0,50 lei '
  + 'în prețul afișat, deci nu sunt direct comparabile cu rândurile de raft.'));
kids.push(bullet(`Toate cifrele provin dintr-o singură colectare completă, ${COLLECTED}, `
  + `acoperind ${de(F.n_priced)} listări de vin cu preț. Prețurile se mișcă; aceasta este o `
  + 'fotografie.'));

// ============================== DOCUMENT =================================
const doc = new Document({
  numbering: {
    config: [{
      reference: 'bl',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '—', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: BODY_IN + 300, hanging: 220 } },
                 run: { color: INK, font: SANS, size: 19 } },
      }],
    }],
  },
  styles: { default: { document: { run: { font: SANS, size: 19, color: INK } } } },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: 1100, right: M_SIDE, bottom: 1000, left: M_SIDE },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { before: 0, after: 0, line: 200, lineRule: LineRuleType.EXACT },
          children: [t('', { size: 15, color: GREY }),
                     new TextRun({ children: [PageNumber.CURRENT], font: SANS, size: 15, color: GREY })],
        })],
      }),
    },
    children: kids,
  }],
});

const out = '/home/user/MarketWineScraper/exports/segment-intrare-2l.docx';
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log(`wrote ${out} (${buf.length} bytes, ${exN} exhibits)`);
});
