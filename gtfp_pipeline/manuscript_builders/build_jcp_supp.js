// JCP Supplementary Material — separate file (S1–S4), from supp_data.json.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, Header, Footer, PageNumber,
  BorderStyle, WidthType, ShadingType,
} = require("docx");

const SD = JSON.parse(fs.readFileSync(
  "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/supp_data.json", "utf8"));

const FONT = "Calibri";
const r4 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(4);
const st = (p) => (p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.10 ? "*" : "");
const cs = (c) => c ? `${r4(c.b)}${st(c.p)} (${Number(c.se).toFixed(4)})` : "—";

const P = (t, o = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: t, font: FONT, size: 21, italics: o.it || false })] });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 280, after: 120 },
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true })] });
const BD = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const ALL = { top: BD, bottom: BD, left: BD, right: BD };
const cell = (t, o = {}) => new TableCell({
  borders: ALL, width: { size: o.w, type: WidthType.DXA },
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 40, bottom: 40, left: 80, right: 80 },
  children: [new Paragraph({ spacing: { after: 0 },
    alignment: o.left ? AlignmentType.LEFT : AlignmentType.CENTER,
    children: [new TextRun({ text: String(t), font: FONT, size: 16,
      bold: o.bold || false, color: o.color })] })] });
const row = (c) => new TableRow({ children: c });
const HC = (t, w) => cell(t, { w, bold: true, fill: "1F4E78", color: "FFFFFF" });
const tTitle = (t) => new Paragraph({ spacing: { before: 210, after: 80 },
  children: [new TextRun({ text: t, font: FONT, size: 19, bold: true })] });
const tNote = (t) => new Paragraph({ spacing: { before: 60, after: 170 },
  children: [new TextRun({ text: `Notes: ${t}`, font: FONT, size: 15, italics: true })] });
const W = 9360;
const RN = { LATAM: "Latin America", ASIA: "Asia", AFRICA: "Africa" };
const VN = { GTFP_ML: "GTFP-ML", MALM_CRS: "Malmquist CRS", LN_TFP_SOLOW: "Solow ln(TFP)",
             LN_AI: "ln AI pubs p.m.", CO2: "CO₂ (Mt)", RULE_OF_LAW: "Rule of Law",
             BROADBAND: "Broadband /100", MOBILE: "Mobile /100", RENEWABLES: "Renewables %",
             RENEW_L1: "Renewables (t−1)" };

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 140 },
    children: [new TextRun({
      text: "Supplementary Material",
      font: FONT, size: 30, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({
      text: "Does artificial intelligence research improve green total factor productivity? Cross-regional evidence from 40 emerging economies in Latin America, Asia, and Africa",
      font: FONT, size: 21, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 260 },
    children: [new TextRun({
      text: "Carlos Miguel Yalta Vargas · Lv KangJuan — Shanghai University",
      font: FONT, size: 19, italics: true })] }),

  // ---- S1 ----
  H1("Supplementary Table S1. Full descriptive statistics by region"),
  ...Object.entries(SD.s1).flatMap(([reg, vars]) => [
    tTitle(`S1.${reg === "LATAM" ? "a" : reg === "ASIA" ? "b" : "c"} — ${RN[reg]}`),
    new Table({ width: { size: W, type: WidthType.DXA },
      columnWidths: [2400, 1392, 1392, 1392, 1392, 1392],
      rows: [
        row([HC("Variable", 2400), HC("Mean", 1392), HC("SD", 1392),
             HC("Min", 1392), HC("Max", 1392), HC("N", 1392)]),
        ...Object.entries(vars).map(([v, s]) => row([
          cell(VN[v] || v, { w: 2400, left: true }),
          cell(s.mean, { w: 1392 }), cell(s.sd, { w: 1392 }),
          cell(s.min, { w: 1392 }), cell(s.max, { w: 1392 }), cell(s.N, { w: 1392 })])),
      ] }),
  ]),
  tNote("Sample 2016–2023. Index variables (GTFP-ML, Malmquist CRS) are year-over-year change indices available from 2017."),

  // ---- S2 ----
  H1("Supplementary Table S2. Lag profile — full-sample estimates"),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([HC("AI lag", 2900), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      ...["L0", "L1", "L2"].map(L => {
        const get = (d) => SD.s2.find(r => r.dep === d && r.lag === L);
        return row([
          cell(L === "L0" ? "Contemporaneous" : L === "L1" ? "One-year lag" : "Two-year lag", { w: 2900, left: true }),
          ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) => {
            const g = get(d);
            return cell(g ? `${r4(g.b)}${st(g.p)} (${Number(g.se).toFixed(4)}) [N=${g.N}]` : "—",
                        { w: i === 2 ? 2160 : 2150 });
          })]);
      }),
    ] }),
  tNote("Full (lag-specific) samples; the main-text Table 3 reports the lag-invariant common sample. Driscoll–Kraay SEs. * p<0.10, ** p<0.05, *** p<0.01."),

  // ---- S3 ----
  H1("Supplementary Table S3. Moderation — median-split subsample estimates"),
  ...Object.entries(SD.s3).map(([dep, mods]) => [
    tTitle(`S3 — ${VN[dep]}: AI (t−1) coefficient by moderator half`),
    new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 3230, 3230],
      rows: [
        row([HC("Moderator", 2900), HC("Below median", 3230), HC("Above median", 3230)]),
        ...Object.entries(mods).map(([m, v]) => row([
          cell(VN[m] || m, { w: 2900, left: true }),
          cell(v.below ? cs(v.below) + ` [N=${v.below.N}]` : "—", { w: 3230 }),
          cell(v.above ? cs(v.above) + ` [N=${v.above.N}]` : "—", { w: 3230 })])),
      ] }),
  ]).flat(),
  tNote("Two-way FE with Driscoll–Kraay SEs on each half-sample. * p<0.10, ** p<0.05, *** p<0.01."),

  // ---- S4 ----
  H1("Supplementary Table S4. System GMM (Blundell–Bond, collapsed instruments)"),
  new Table({ width: { size: W, type: WidthType.DXA },
    columnWidths: [2400, 2320, 2320, 2320],
    rows: [
      row([cell("", { w: 2400 }), HC("GTFP-ML", 2320), HC("Malmquist CRS", 2320), HC("Solow ln(TFP)", 2320)]),
      ...[
        ["AI (t−1)", (g) => cs(g)],
        ["Lagged dep. var. (ρ)", (g) => `${r4(g.rho)} (p=${Number(g.rho_p).toFixed(3)})`],
        ["Hansen J p-value", (g) => Number(g.hansen_p).toFixed(3)],
        ["AR(1) p-value", (g) => Number(g.ar1_p).toFixed(3)],
        ["AR(2) p-value", (g) => Number(g.ar2_p).toFixed(3)],
        ["Instruments / countries", (g) => `${g.n_instruments} / ${g.n_countries}`],
        ["N", (g) => g.N],
      ].map(([lab, f]) => row([
        cell(lab, { w: 2400, left: true }),
        ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map(d =>
          cell(f(SD.s4[d]), { w: 2320 }))])),
    ] }),
  tNote("Two-step system GMM (pydynpd), GMM-style instruments: lags 2–4 of the dependent variable, collapsed; AI treated as predetermined; controls IV-style. Diagnostics reject or marginally reject instrument validity (Hansen p = 0.001–0.076) and AR(2) is rejected for GTFP-ML; consistent with the well-known fragility of system GMM in short panels (T = 8) and with the absence of autoregressive structure in change indices (ρ ≈ 0 for GTFP-ML and Malmquist). These estimates are reported for completeness and are not relied upon; the region-by-year FE-DK specification remains preferred. * p<0.10, ** p<0.05, *** p<0.01."),
];

const doc = new Document({
  creator: "Claude",
  title: "JCP Supplementary Material",
  styles: { default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true, color: "000000" },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 0 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Supplementary Material · AI research and green TFP",
        font: FONT, size: 16, italics: true, color: "808080" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "S-", font: FONT, size: 16, color: "808080" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "808080" })] })] }) },
    children }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/paper2_JCP_Supplementary_Material.docx";
  fs.writeFileSync(out, buf);
  console.log(`Saved ${out} (${buf.length} bytes)`);
});
