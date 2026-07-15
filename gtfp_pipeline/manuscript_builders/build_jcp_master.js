// JCP MASTER DOCUMENT — full assembly, submission-ready structure.
// All statistics from fill_data.json. Author-year citations (verify style at submission).

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, Header, Footer, PageNumber, PageBreak,
  BorderStyle, WidthType, ShadingType,
} = require("docx");

const F = JSON.parse(fs.readFileSync(
  "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/fill_data.json", "utf8"));
const B = F.benchmark, RY = F.region_year_fe, Q = F.quantile_solow, H3 = F.h3_paired,
      CD = F.cd_tests, MOD = F.moderation, REG = F.regional_interactions,
      D = F.diag, S = F.sample, ROB = F.robustness, DES = F.descriptives;
const lag = {};
for (const r of F.lag_profile) if (r.sample === "common") lag[`${r.dep}_${r.lag}`] = r;

const r3 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(3);
const r4 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(4);
const st = (p) => (p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.10 ? "*" : "");
const cs = (c) => c ? `${r4(c.b)}${st(c.p)} (${Number(c.se).toFixed(4)})` : "—";
const csp = (c) => `β = ${r3(c.b)}, SE = ${Number(c.se).toFixed(3)}, p = ${Number(c.p).toFixed(2)}`;

const FONT = "Calibri";
function parseRuns(text, size = 21) {
  const runs = [];
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  for (const part of parts) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      runs.push(new TextRun({ text: part.slice(2, -2), font: FONT, size, bold: true }));
    else if (part.startsWith("*") && part.endsWith("*") && part.length > 2)
      runs.push(new TextRun({ text: part.slice(1, -1), font: FONT, size, italics: true }));
    else runs.push(new TextRun({ text: part, font: FONT, size }));
  }
  return runs;
}
const P = (t, o = {}) => new Paragraph({
  spacing: { after: 120, line: 276 }, alignment: AlignmentType.JUSTIFIED,
  indent: o.noIndent ? undefined : { firstLine: 340 }, children: parseRuns(t) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 280, after: 130 },
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { before: 220, after: 100 },
  children: [new TextRun({ text: t, font: FONT, size: 21, bold: true, italics: true })] });
const todo = (t) => new Paragraph({ spacing: { before: 90, after: 90 },
  shading: { fill: "FFF2CC", type: ShadingType.CLEAR },
  children: [new TextRun({ text: `◆ ${t}`, font: FONT, size: 18, bold: true, color: "B45309" })] });
const pb = () => new Paragraph({ children: [new PageBreak()] });

const BD = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const ALL = { top: BD, bottom: BD, left: BD, right: BD };
const cell = (t, o = {}) => new TableCell({
  borders: ALL, width: { size: o.w, type: WidthType.DXA },
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 45, bottom: 45, left: 85, right: 85 },
  children: [new Paragraph({ spacing: { after: 0 },
    alignment: o.left ? AlignmentType.LEFT : AlignmentType.CENTER,
    children: [new TextRun({ text: String(t), font: FONT, size: 16,
      bold: o.bold || false, italics: o.it || false, color: o.color })] })] });
const row = (cells) => new TableRow({ children: cells });
const HC = (t, w) => cell(t, { w, bold: true, fill: "1F4E78", color: "FFFFFF" });
const tTitle = (n, t) => new Paragraph({ spacing: { before: 210, after: 80 },
  children: [new TextRun({ text: `Table ${n}. ${t}`, font: FONT, size: 19, bold: true })] });
const tNote = (t) => new Paragraph({ spacing: { before: 60, after: 170 },
  alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: `Notes: ${t}`, font: FONT, size: 15, italics: true })] });
const W = 9360;
const sig = "* p<0.10, ** p<0.05, *** p<0.01. Driscoll–Kraay standard errors in parentheses. Controls: ln GDP per capita, trade openness, FDI, government consumption, urbanisation.";

const RNAME = { LATAM: "Latin America", ASIA: "Asia", AFRICA: "Africa" };
const kaz = Object.entries(D.ml_infeasible_by_country).map(([c, n]) => `${c} (${n})`).join(", ");

// ═══════════════ REFERENCES (verified only; author–year) ═══════════════
const REFS = [
  "Acemoglu, D., Autor, D., Hazell, J., Restrepo, P., 2022. Artificial intelligence and jobs: evidence from online vacancies. J. Labor Econ. 40 (S1), S293–S340.",
  "Babina, T., Fedyk, A., He, A., Hodson, J., 2024. Artificial intelligence, firm growth, and product innovation. J. Financ. Econ. 151, 103745.",
  "Bresnahan, T.F., Trajtenberg, M., 1995. General purpose technologies: 'engines of growth'? J. Econom. 65 (1), 83–108.",
  "Brynjolfsson, E., Rock, D., Syverson, C., 2021. The productivity J-curve: how intangibles complement general purpose technologies. Am. Econ. J. Macroecon. 13 (1), 333–372.",
  "Canay, I.A., 2011. A simple approach to quantile regression for panel data. Econom. J. 14 (3), 368–386.",
  "Chung, Y.H., Färe, R., Grosskopf, S., 1997. Productivity and undesirable outputs: a directional distance function approach. J. Environ. Manage. 51 (3), 229–240.",
  "Cimoli, M., Hofman, A., Mulder, N., 2010. Innovation and Economic Development: The Impact of Information and Communication Technologies in Latin America. Edward Elgar, Cheltenham.",
  "Cohen, W.M., Levinthal, D.A., 1990. Absorptive capacity: a new perspective on learning and innovation. Adm. Sci. Q. 35 (1), 128–152.",
  "Driscoll, J.C., Kraay, A.C., 1998. Consistent covariance matrix estimation with spatially dependent panel data. Rev. Econ. Stat. 80 (4), 549–560.",
  "Färe, R., Grosskopf, S., Norris, M., Zhang, Z., 1994. Productivity growth, technical progress, and efficiency change in industrialized countries. Am. Econ. Rev. 84 (1), 66–83.",
  "Färe, R., Grosskopf, S., Pasurka, C.A., 2007. Environmental production functions and environmental directional distance functions. Energy 32 (7), 1055–1066.",
  "Feenstra, R.C., Inklaar, R., Timmer, M.P., 2015. The next generation of the Penn World Table. Am. Econ. Rev. 105 (10), 3150–3182.",
  "Goldfarb, A., Taska, B., Teodoridis, F., 2023. Could machine learning be a general purpose technology? A comparison of emerging technologies using data on occupational impacts. Res. Policy 52 (1), 104653.",
  "Gollin, D., 2002. Getting income shares right. J. Polit. Econ. 110 (2), 458–474.",
  "Griliches, Z., 1979. Issues in assessing the contribution of research and development to productivity growth. Bell J. Econ. 10 (1), 92–116.",
  "Griliches, Z., 1990. Patent statistics as economic indicators: a survey. J. Econ. Lit. 28 (4), 1661–1707.",
  "[JCP-REF 1–5: insert 3–5 recent Journal of Cleaner Production green-TFP papers here, alphabetically merged]",
  "Luo, J., Lei, H., Hou, J., 2024. The impact of artificial intelligence technology innovation on total factor productivity: an empirical study based on provincial panel data in China. Natl. Account. Rev. 6 (2), 172–194.",
  "McMillan, M., Rodrik, D., 2011. Globalization, structural change and productivity growth. NBER Working Paper 17143.",
  "Niebel, T., 2018. ICT and economic growth — comparing developing, emerging and developed countries. World Dev. 104, 197–211.",
  "OECD, 2024. OECD.AI Policy Observatory: AI research publications. OECD, Paris. https://oecd.ai.",
  "Pesaran, M.H., 2004. General diagnostic tests for cross section dependence in panels. Cambridge Working Papers in Economics 0435.",
  "Pesaran, M.H., 2006. Estimation and inference in large heterogeneous panels with a multifactor error structure. Econometrica 74 (4), 967–1012.",
  "Roodman, D., 2009. How to do xtabond2: an introduction to difference and system GMM in Stata. Stata J. 9 (1), 86–136.",
  "Vinuesa, R., Azizpour, H., Leite, I., Balaam, M., Dignum, V., Domisch, S., Felländer, A., Langhans, S.D., Tegmark, M., Fuso Nerini, F., 2020. The role of artificial intelligence in achieving the Sustainable Development Goals. Nat. Commun. 11, 233.",
  "World Bank, 2016. World Development Report 2016: Digital Dividends. World Bank, Washington, DC.",
];

// ═══════════════ TABLES ═══════════════

const table1 = [
  tTitle(1, "Panel means by region, 2016–2023."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2160, 1800, 1800, 1800, 1800],
    rows: [
      row([cell("", { w: 2160 }), HC("GTFP-ML", 1800), HC("Malmquist CRS", 1800),
           HC("Solow ln(TFP)", 1800), HC("ln AI pubs p.m.", 1800)]),
      ...["LATAM", "ASIA", "AFRICA"].map(r => row([
        cell(RNAME[r], { w: 2160, left: true }),
        cell(DES[r].GTFP_ML.toFixed(4), { w: 1800 }),
        cell(DES[r].MALM_CRS.toFixed(4), { w: 1800 }),
        cell(DES[r].LN_TFP_SOLOW.toFixed(3), { w: 1800 }),
        cell(DES[r].LN_AI.toFixed(3), { w: 1800 })])),
    ] }),
  tNote("Index measures are year-over-year change indices (value 1 = no change); Solow is a log level. Full descriptive statistics in Supplementary Table S1."),
];

const table2 = [
  tTitle(2, "AI research (t−1) and productivity: benchmark estimates."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([cell("", { w: 2900 }), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      row([cell("FE-DK (country + year FE)", { w: 2900, left: true }),
           cell(cs(B.GTFP_ML), { w: 2150 }), cell(cs(B.MALM_CRS), { w: 2150 }), cell(cs(B.LN_TFP_SOLOW), { w: 2160 })]),
      row([cell("Country + region×year FE", { w: 2900, left: true }),
           cell(cs(RY.GTFP_ML), { w: 2150 }), cell(cs(RY.MALM_CRS), { w: 2150 }), cell(cs(RY.LN_TFP_SOLOW), { w: 2160 })]),
      row([cell("Residual CD (region×year spec)", { w: 2900, left: true }),
           cell(`${RY.GTFP_ML.CD_after} (p=${RY.GTFP_ML.CD_p.toFixed(2)})`, { w: 2150 }),
           cell(`${RY.MALM_CRS.CD_after} (p=${RY.MALM_CRS.CD_p.toFixed(2)})`, { w: 2150 }),
           cell(`${RY.LN_TFP_SOLOW.CD_after} (p=${RY.LN_TFP_SOLOW.CD_p.toFixed(2)})`, { w: 2160 })]),
      row([cell("N", { w: 2900, left: true }),
           cell(B.GTFP_ML.N, { w: 2150 }), cell(B.MALM_CRS.N, { w: 2150 }), cell(B.LN_TFP_SOLOW.N, { w: 2160 })]),
    ] }),
  tNote(sig + ` Baseline FE-DK residual CD: GTFP-ML ${CD.GTFP_ML.CD} (p=${CD.GTFP_ML.p.toFixed(2)}), Malmquist ${CD.MALM_CRS.CD} (p=${CD.MALM_CRS.p.toFixed(2)}), Solow ${CD.LN_TFP_SOLOW.CD} (p<0.001).`),
];

const table3 = [
  tTitle(3, "Lag profile on the lag-invariant common sample."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([HC("AI lag", 2900), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      ...["L0", "L1", "L2"].map(L => row([
        cell(L === "L0" ? "Contemporaneous" : L === "L1" ? "One-year lag" : "Two-year lag", { w: 2900, left: true }),
        ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) =>
          cell(cs(lag[`${d}_${L}`]), { w: i === 2 ? 2160 : 2150 }))])),
    ] }),
  tNote(`Common sample restricts to observations with all three lags observed (N = ${lag["GTFP_ML_L0"].N} GTFP-ML; ${lag["MALM_CRS_L0"].N} others). Full-sample estimates in Supplementary Table S2. ` + sig),
];

const subRegRow = (d) => ["LATAM", "ASIA", "AFRICA"].map(r =>
  REG[d][`sub_${r}`] ? cs(REG[d][`sub_${r}`]) : "—");
const table4 = [
  tTitle(4, "Regional heterogeneity: interactions and subsamples."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([cell("", { w: 2900 }), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      row([cell("Panel A. Interactions (base: Latin America)", { w: W, left: true, bold: true, it: true, fill: "F2F2F2" }),
           ...[2150, 2150, 2160].map(w => cell("", { w, fill: "F2F2F2" }))]),
      ...[["AI (t−1)", "LN_AI_L1"], ["AI × Asia", "AIxASIA"], ["AI × Africa", "AIxAFRICA"]].map(([lab, k]) =>
        row([cell(lab, { w: 2900, left: true }),
          ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) => {
            const b = REG[d][`${k}_b`], se = REG[d][`${k}_se`], p = REG[d][`${k}_p`];
            return cell(b !== undefined ? `${r4(b)}${st(p)} (${Number(se).toFixed(4)})` : "—",
                        { w: i === 2 ? 2160 : 2150 });
          })])),
      row([cell("Panel B. Region subsamples — AI (t−1) coefficient", { w: W, left: true, bold: true, it: true, fill: "F2F2F2" }),
           ...[2150, 2150, 2160].map(w => cell("", { w, fill: "F2F2F2" }))]),
      ...["LATAM", "ASIA", "AFRICA"].map((r, ri) =>
        row([cell(RNAME[r] + " only", { w: 2900, left: true }),
          ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) =>
            cell(REG[d][`sub_${r}`] ? cs(REG[d][`sub_${r}`]) : "—", { w: i === 2 ? 2160 : 2150 }))])),
      row([cell("Excluding Latin America (pooled)", { w: 2900, left: true }),
           cell(cs(D.drop_LATAM.GTFP_ML), { w: 2150 }),
           cell(cs(D.drop_LATAM.MALM_CRS), { w: 2150 }),
           cell(cs(D.drop_LATAM.LN_TFP_SOLOW), { w: 2160 })]),
    ] }),
  tNote(sig),
];

const modRows = [["RULE_OF_LAW", "Rule of Law"], ["BROADBAND", "Broadband"],
                 ["MOBILE", "Mobile"], ["RENEW_L1", "Renewables (t−1)"]];
const table5 = [
  tTitle(5, "Moderation: AI (t−1) × moderator interaction coefficients."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([HC("Moderator", 2900), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      ...modRows.map(([k, lab]) => row([
        cell(lab, { w: 2900, left: true }),
        ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) =>
          cell(MOD[d] && MOD[d][k] ? cs(MOD[d][k]) : "—", { w: i === 2 ? 2160 : 2150 }))])),
    ] }),
  tNote("Moderators demeaned before interacting; moderator main effect included. Median-split subsample estimates in Supplementary Table S3. " + sig),
];

const robKeys = Object.keys(ROB);
const table6 = [
  tTitle(6, "Robustness, environmental margin, and distributional estimates."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([cell("", { w: 2900 }), HC("GTFP-ML", 2150), HC("Malmquist CRS", 2150), HC("Solow ln(TFP)", 2160)]),
      row([cell("Panel A. Alternative AI specifications", { w: W, left: true, bold: true, it: true, fill: "F2F2F2" }),
           ...[2150, 2150, 2160].map(w => cell("", { w, fill: "F2F2F2" }))]),
      ...robKeys.map(k => row([
        cell(k, { w: 2900, left: true }),
        ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) =>
          cell(ROB[k][d] ? cs(ROB[k][d]) : "—", { w: i === 2 ? 2160 : 2150 }))])),
      row([cell("Panel B. Environmental margin: Δβ (GTFP − Malmquist), paired", { w: W, left: true, bold: true, it: true, fill: "F2F2F2" }),
           ...[2150, 2150, 2160].map(w => cell("", { w, fill: "F2F2F2" }))]),
      row([cell("Δβ at L0 / L1 / L2", { w: 2900, left: true }),
           cell(`${r4(H3.L0.b)}${st(H3.L0.p)}`, { w: 2150 }),
           cell(`${r4(H3.L1.b)}${st(H3.L1.p)}`, { w: 2150 }),
           cell(`${r4(H3.L2.b)}${st(H3.L2.p)}`, { w: 2160 })]),
      row([cell("Panel C. Canay quantile — Solow ln(TFP), AI (t−1)", { w: W, left: true, bold: true, it: true, fill: "F2F2F2" }),
           ...[2150, 2150, 2160].map(w => cell("", { w, fill: "F2F2F2" }))]),
      row([cell("τ = 0.10 / 0.25 / 0.50", { w: 2900, left: true }),
           cell(`${r4(Q["0.1"].b)}${st(Q["0.1"].p)}`, { w: 2150 }),
           cell(`${r4(Q["0.25"].b)}${st(Q["0.25"].p)}`, { w: 2150 }),
           cell(`${r4(Q["0.5"].b)}${st(Q["0.5"].p)}`, { w: 2160 })]),
      row([cell("τ = 0.75 / 0.90", { w: 2900, left: true }),
           cell(`${r4(Q["0.75"].b)}${st(Q["0.75"].p)}`, { w: 2150 }),
           cell(`${r4(Q["0.9"].b)}${st(Q["0.9"].p)}`, { w: 2150 }),
           cell("", { w: 2160 })]),
    ] }),
  tNote("Panel B columns display the L0/L1/L2 paired difference (not per-DV). Panel C cells display quantile coefficients in τ order (columns are positional, not per-DV). Bootstrap (country-cluster, 200 reps) SEs for Panel C. System-GMM deferred to revision (Roodman, 2009). " + sig),
];

// ═══════════════ DOCUMENT ═══════════════
const children = [
  // ---- title page ----
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 170 },
    shading: { fill: "DEEBF7", type: ShadingType.CLEAR },
    children: [new TextRun({
      text: "MASTER DRAFT v1 (assembled) — Journal of Cleaner Production · remaining before submission: [JCP-REF] exemplars, [email]/declaration fields, citation-style check, supplementary tables S1–S3, clean pipeline re-run",
      font: FONT, size: 16, bold: true, color: "1F4E78" })] }),
  new Paragraph({ spacing: { before: 600, after: 140 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({
      text: "Does artificial intelligence research improve green total factor productivity? Cross-regional evidence from 40 emerging economies in Latin America, Asia, and Africa",
      font: FONT, size: 30, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 },
    children: [new TextRun({ text: "Carlos Miguel Yalta Vargas ¹  ·  Lv KangJuan ²·*", font: FONT, size: 24, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "¹ School of Economics, Shanghai University — [email]", font: FONT, size: 20, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
    children: [new TextRun({ text: "² SILC Business School, Shanghai University — [email] — * corresponding author", font: FONT, size: 20, italics: true })] }),
  pb(),

  // ---- highlights + abstract ----
  H1("Highlights"),
  ...[
    `First cross-regional evidence on AI research and green TFP in ${S.n_countries} economies.`,
    "Green TFP measured by Malmquist–Luenberger index with CO₂ as undesirable output.",
    "AI–green-TFP link is null on impact and turns negative at a two-year lag.",
    "Negative associations concentrate in Asia and Africa, not Latin America.",
    "AI-for-sustainability strategies need institutional and digital foundations.",
  ].map(t => new Paragraph({ spacing: { after: 70 }, indent: { left: 360, hanging: 240 },
    children: [new TextRun({ text: "• ", font: FONT, size: 21, bold: true, color: "1F4E78" }),
               new TextRun({ text: t, font: FONT, size: 21 })] })),

  H1("Abstract"),
  P(`Artificial intelligence (AI) is promoted as an enabler of cleaner production and sustainable development, yet whether AI innovation is associated with greener productivity in developing economies remains untested at cross-regional scale. This study estimates the relationship between AI research output and green total factor productivity (GTFP) in ${S.n_countries} emerging economies across Latin America (${S.regions.LATAM}), Asia (${S.regions.ASIA}), and Africa (${S.regions.AFRICA}) over ${S.window[0]}–${S.window[1]}. GTFP is measured with a Malmquist–Luenberger index treating CO₂ emissions as an undesirable output, contrasted with a conventional Malmquist index and a Solow-residual measure; AI innovation is proxied by AI-related scientific publications from the OECD AI Observatory. The design addresses cross-sectional dependence through Driscoll–Kraay inference, Common Correlated Effects estimators, and region-by-year fixed effects. The contemporaneous association between AI research and GTFP is statistically insignificant (β = ${r3(B.GTFP_ML.b)}, p = ${B.GTFP_ML.p.toFixed(2)}); it is negative and marginally significant under region-by-year fixed effects (β = ${r3(RY.GTFP_ML.b)}, p = ${RY.GTFP_ML.p.toFixed(2)}) and strengthens to β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) at a two-year lag. The association is significantly more negative in Asia and Africa than in Latin America, and green and conventional productivity respond similarly, indicating no separate environmental margin. Mobile connectivity significantly softens the GTFP association, and Rule of Law moderates the conventional index. The findings caution against expecting short-run green-productivity dividends from AI research capacity alone and support sequencing AI strategies behind institutional and digital-infrastructure investments, in line with SDG 8.2 and SDG 9.`, { noIndent: true }),
  P("**Keywords:** artificial intelligence; green total factor productivity; Malmquist–Luenberger index; cleaner production; emerging economies; cross-sectional dependence", { noIndent: true }),
  pb(),

  // ---- 1. Introduction ----
  H1("1. Introduction"),
  P("Emerging economies face a dual challenge: reigniting productivity growth while decarbonising it. Growth across Latin America, developing Asia, and Africa remains substantially more emissions-intensive than in advanced economies, and the productivity gains that do materialise often come with rising CO₂. Against this backdrop, artificial intelligence is widely promoted — by national AI strategies and international organisations alike — as a technology that can deliver *cleaner* production: more output from fewer inputs with lower emissions. Whether AI innovation is in fact associated with greener productivity in the Global South is an open empirical question; the existing evidence concentrates on advanced economies and China, and almost exclusively on conventional productivity measures that ignore the emissions margin."),
  P(`This paper provides, to our knowledge, the first cross-regional analysis of the relationship between AI research output and green total factor productivity (GTFP), covering ${S.n_countries} emerging economies — ${S.regions.LATAM} in Latin America, ${S.regions.ASIA} in Asia, and ${S.regions.AFRICA} in Africa — over ${S.window[0]}–${S.window[1]}. GTFP is measured with a Malmquist–Luenberger index that credits economies for expanding output while contracting CO₂ emissions (Chung et al., 1997), and is benchmarked against a conventional Malmquist index (Färe et al., 1994) and a Solow-residual measure so that the environmental margin of the AI–productivity relationship is itself testable. AI innovation is proxied by AI-related scientific publications (OECD, 2024), observed on a consistent bibliometric basis across all sample countries. The econometric design treats cross-sectional dependence explicitly — Driscoll–Kraay inference, Common Correlated Effects estimators (Pesaran, 2006), and region-by-year fixed effects.`),
  P(`Three findings emerge. First, the contemporaneous AI–GTFP association is statistically indistinguishable from zero (${csp(B.GTFP_ML)}); under region-by-year fixed effects it is negative and marginally significant (${csp(RY.GTFP_ML)}), and it deepens monotonically with the lag of the AI measure, reaching β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) at two years on a lag-invariant sample — a delayed-adjustment pattern consistent with the productivity J-curve (Brynjolfsson et al., 2021). Second, the association is regionally concentrated: interactions with the conventional Malmquist index are significantly negative for Asia (β = ${r3(REG.MALM_CRS["AIxASIA_b"])}, p < 0.01) and Africa (β = ${r3(REG.MALM_CRS["AIxAFRICA_b"])}, p < 0.01) relative to Latin America, and excluding Latin America turns the pooled GTFP association significantly negative (β = ${r3(D.drop_LATAM.GTFP_ML.b)}, p < 0.05). Third, green and conventional productivity respond similarly: a paired coefficient-difference test finds no significant environmental margin at one- or two-year lags (Δβ = ${r3(H3.L1.b)} and ${r3(H3.L2.b)}, both insignificant), while moderation analysis shows mobile connectivity significantly softening the GTFP association and Rule of Law moderating the conventional index.`),
  P("The contributions are threefold: the first cross-regional AI–GTFP evidence for the Global South; an explicit test of the environmental margin via the GTFP–conventional-TFP contrast; and a treatment of cross-sectional dependence — diagnosed, and resolved with region-by-year fixed effects — that is absent from prior green-TFP studies. Section 2 reviews related literature and states the hypotheses, Section 3 describes materials and methods, Section 4 reports results, Section 5 discusses implications, and Section 6 concludes."),

  // ---- 2. Literature ----
  H1("2. Literature review and hypotheses"),
  H2("2.1 AI and productivity"),
  P("The economic case for expecting AI to raise productivity rests on its characterisation as a general purpose technology: pervasive across sectors, improving over time, and spawning complementary innovation (Bresnahan and Trajtenberg, 1995). Yet the same literature explains why measured productivity may respond slowly or even negatively in the medium run. Brynjolfsson, Rock and Syverson (2021) formalise the productivity J-curve: because AI requires complementary intangible investments — organisational redesign, skills, data infrastructure — measured productivity understates true output early in the diffusion process, and contemporaneous correlations between AI activity and productivity can be zero or negative even when the long-run effect is positive. Empirically, positive associations have been documented mainly in advanced economies: Acemoglu, Autor, Hazell and Restrepo (2022) find modest gains concentrated in large U.S. firms, and Babina, Fedyk, He and Hodson (2024) link firm AI investment to growth through product innovation. At the technology-assessment level, Goldfarb, Taska and Teodoridis (2023) conclude that machine learning behaves like a general purpose technology but that its measurable aggregate effects remain smaller than those of earlier GPTs at comparable stages.", { noIndent: true }),
  P("Evidence for developing economies is thin and concentrated on China. Luo, Lei and Hou (2024) document positive effects of AI patent activity on the total factor productivity of Chinese provinces. Whether such findings travel to regions with smaller AI research bases, weaker complementary infrastructure, and more emissions-intensive growth is unknown — and the productivity concept in this literature is almost always conventional TFP, which is silent on whether AI-associated growth is cleaner or merely faster. In the knowledge-production tradition that underpins these studies (Griliches, 1979, 1990), research output measures — patents or publications — proxy the knowledge input into production; scientific publications have the practical advantage of consistent bibliometric observation across countries with very different patenting propensities."),
  H2("2.2 Green total factor productivity"),
  P("Conventional productivity indices credit output expansion regardless of its emissions content. The directional distance function of Chung, Färe and Grosskopf (1997) extends the production frontier to joint production of desirable and undesirable outputs under weak disposability, and the associated Malmquist–Luenberger (ML) index measures productivity change that simultaneously credits output expansion and emissions contraction (see also Färe, Grosskopf and Pasurka, 2007). The resulting green TFP concept has become the workhorse of the cleaner-production literature on emerging economies, with a large body of applications to Chinese provinces and cities examining drivers ranging from environmental regulation to the digital economy [JCP-REF: insert 3–5 recent green-TFP papers from this journal]. Two gaps stand out. First, applications are overwhelmingly single-country; cross-regional evidence spanning Latin America, Asia, and Africa is, to our knowledge, absent. Second, AI-specific innovation has not been examined as a driver of green TFP, despite the prominence of AI in national sustainable-development strategies.", { noIndent: true }),
  H2("2.3 Absorptive capacity and conditional effects"),
  P("Whether knowledge inputs translate into productivity depends on complementary capabilities. Cohen and Levinthal (1990) formalise absorptive capacity at the organisational level; its macro analogue holds that the productivity return to new technology is increasing in institutional quality, infrastructure, and skills. For digital technologies in developing economies this conditionality is well documented (World Bank, 2016; Niebel, 2018), and for Latin America specifically, Cimoli, Hofman and Mulder (2010) show that ICT-driven productivity gains required complementary investment in education and institutions. Structural composition matters as well: where growth is concentrated in emissions-intensive industrialisation, the same knowledge input may coincide with deteriorating environmental efficiency (McMillan and Rodrik, 2011). Global assessments of AI and the Sustainable Development Goals reach a parallel conclusion: AI can enable most environmental targets, but realising the benefits depends on governance and infrastructure preconditions (Vinuesa et al., 2020).", { noIndent: true }),
  P("From these literatures we derive three hypotheses. **H1:** AI research output is positively associated with green total factor productivity. **H2:** the association is stronger in economies with stronger institutions and digital infrastructure. **H3:** the AI–GTFP association differs from the AI–conventional-TFP association — that is, an environmental margin exists. H1 reflects the optimistic GPT prior embedded in national AI strategies; the J-curve and absorptive-capacity literatures supply the reasons it may fail in the short run, which our lag-profile and moderation analyses are designed to detect."),

  // ---- 3. Methods ----
  H1("3. Materials and methods"),
  H2("3.1 Sample and data"),
  P(`The sample covers ${S.n_countries} emerging economies (${S.regions.LATAM} in Latin America, ${S.regions.ASIA} in Asia, ${S.regions.AFRICA} in Africa) over ${S.window[0]}–${S.window[1]} (T = 8; ${S.n_obs_panel} country-year observations), bounded by the OECD AI Observatory publication series (2016–) and the CO₂ data lag (through 2023). Nigeria is excluded because constant-price national accounts are unavailable following its GDP rebase. Data sources: World Bank WDI (GDP, gross fixed capital formation, CO₂ emissions, renewable-energy share, controls), ILOSTAT employment, Penn World Table 10.01 human capital (Feenstra et al., 2015; trend-extended after 2019), Worldwide Governance Indicators Rule of Law, and OECD AI Observatory publications (OECD, 2024). China's capital input uses gross capital formation because constant-price GFCF is unavailable. The country list and series codes appear in Appendix A.`),
  H2("3.2 Productivity measurement"),
  P(`The Malmquist–Luenberger (ML) index is computed from directional distance functions with inputs physical capital (perpetual inventory method, δ = 0.05, initialised 2008) and effective labour (employment × human capital), desirable output real GDP, undesirable output CO₂, and direction g = (y, −b) (Chung et al., 1997). The conventional CRS Malmquist index (Färe et al., 1994) and the Solow residual (capital share α = 0.35; Gollin, 2002) provide the environmental-margin contrast. Of ${S.gtfp_possible} feasible index observations, ${S.gtfp_valid} ML values are valid; infeasibility concentrates in the sample's most CO₂-intensive economies — ${kaz} — which are therefore effectively excluded from the GTFP regressions, a restriction reported transparently and common to directional-distance applications.`),
  H2("3.3 Econometric strategy"),
  P("The baseline regresses each productivity measure on the one-year-lagged log of AI publications per million population and controls (log GDP per capita, trade openness, FDI, government consumption, urbanisation), with country and year fixed effects and Driscoll–Kraay (1998) standard errors. Cross-sectional dependence is diagnosed with the Pesaran (2004) CD test; where residual dependence reflects a between-region common factor, region-by-year fixed effects are added. Regional heterogeneity uses region × AI interactions and subsamples; moderation uses demeaned-moderator interactions with median-split corroboration; distributional heterogeneity uses the Canay (2011) two-step quantile estimator with country-cluster bootstrap. Identification is associational throughout; the lag profile is evaluated on a lag-invariant common sample to separate dynamics from sample composition. System-GMM estimates with collapsed instruments (Roodman, 2009) are deferred to the revision stage."),

  // ---- 4. Results ----
  H1("4. Results"),
  H2("4.1 Descriptive statistics and dependence diagnostics"),
  P(`Table 1 summarises the panel by region. Mean GTFP-ML is below unity in all three regions, indicating on-average green-productivity regression over the window; AI research intensity is highest in Asia (mean ln AI publications per million ${DES.ASIA.LN_AI.toFixed(2)}, against ${DES.LATAM.LN_AI.toFixed(2)} in Latin America and ${DES.AFRICA.LN_AI.toFixed(2)} in Africa).`, { noIndent: true }),
  ...table1,
  P(`Pesaran CD tests on baseline FE residuals show no significant dependence for the index measures but strong dependence for the Solow level measure (CD = ${CD.LN_TFP_SOLOW.CD}, p < 0.001). The dependence is a between-region phenomenon — within-region CD statistics are all insignificant — and region-by-year fixed effects reduce the pooled statistic to ${RY.LN_TFP_SOLOW.CD_after} (p = ${RY.LN_TFP_SOLOW.CD_p.toFixed(2)}). The region-by-year specification is therefore reported alongside the baseline throughout.`),
  H2("4.2 Benchmark estimates"),
  ...table2,
  P(`The contemporaneous-lag benchmark is small and insignificant for all three measures. Under region-by-year fixed effects — the specification favoured by the dependence diagnostics — the GTFP-ML coefficient is negative and marginally significant (${csp(RY.GTFP_ML)}).`),
  H2("4.3 Lag profile"),
  ...table3,
  P(`For GTFP-ML the association deepens monotonically with the lag — from ${r4(lag["GTFP_ML_L0"].b)} contemporaneously to ${r4(lag["GTFP_ML_L2"].b)}${st(lag["GTFP_ML_L2"].p)} at two years on identical observations — so the two-year result reflects dynamics rather than sample composition. A delayed negative association that strengthens over the horizon is the signature of adjustment costs during technology absorption predicted by the productivity J-curve literature.`),
  H2("4.4 Regional heterogeneity"),
  ...table4,
  P(`The conventional-Malmquist association is significantly more negative in Asia and Africa than in Latin America (Table 4, Panel A), and excluding Latin America turns the pooled association significantly negative for both GTFP-ML (${csp(D.drop_LATAM.GTFP_ML)}) and the conventional index (${csp(D.drop_LATAM.MALM_CRS)}). The pooled null therefore averages a near-zero Latin American association with negative associations in Asia and Africa.`),
  H2("4.5 Moderation"),
  ...table5,
  P(`Mobile connectivity significantly softens the GTFP association (interaction β = ${r4(MOD.GTFP_ML.MOBILE.b)}, p = ${Number(MOD.GTFP_ML.MOBILE.p).toFixed(3)}), consistent with digital infrastructure enabling productive absorption of AI research. Rule of Law significantly moderates the conventional index (β = ${r4(MOD.MALM_CRS.RULE_OF_LAW.b)}, p = ${Number(MOD.MALM_CRS.RULE_OF_LAW.p).toFixed(3)}); broadband and lagged renewable-energy share moderate the Solow measure. These conditional patterns give H2 qualified support: complementary capabilities shape the association, though not uniformly across productivity concepts.`),
  H2("4.6 Environmental margin, distributional estimates, and robustness"),
  ...table6,
  P(`Because the green and conventional indices are observed on the same country-years, regressing their difference on AI delivers a paired test of the environmental margin (Table 6, Panel B): the difference is insignificant at one- and two-year lags, and the two indices correlate at ${D.wedge_overall.corr_indices}. H3 is not supported — AI research relates to green and conventional productivity similarly. Canay quantile estimates for the Solow level measure (Panel C) are positive across the conditional distribution while the conditional-mean estimate is insignificant; level and change measures answer different questions, and the positive level association does not contradict the negative lagged change association. The benchmark null is robust to alternative AI specifications (Panel A), to dropping China, and to trimming the index tails.`),

  // ---- 5. Discussion ----
  H1("5. Discussion"),
  H2("5.1 No short-run green dividend, and no environmental margin"),
  P(`Taken together, the results give a disciplined answer to the question in the title: AI research capacity is not associated with green-productivity improvement in the short run. The contemporaneous benchmark is null, the region-by-year specification favoured by the dependence diagnostics is negative and marginally significant, and the association deepens to β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) two years after the AI measure on a lag-invariant sample. Equally important is what the paired test shows: green and conventional productivity respond to AI almost identically. H3 is not supported. AI research is thus not yet associated with *cleaner* growth specifically — whatever relationship exists operates through the input–output core of productivity, not the emissions margin. For the cleaner-production agenda this is a cautionary result: research capacity alone does not shift the emissions efficiency of growth within the horizon we observe.`, { noIndent: true }),
  H2("5.2 Delayed adjustment, not instant payoff"),
  P(`The monotone deepening of the negative association across the lag profile (${r4(lag["GTFP_ML_L0"].b)} → ${r4(lag["GTFP_ML_L1"].b)} → ${r4(lag["GTFP_ML_L2"].b)}${st(lag["GTFP_ML_L2"].p)}) is the pattern the productivity J-curve predicts during the absorption phase of a general purpose technology: complementary investments are being made, resources are reallocated, and measured productivity temporarily falls before the payoff arrives (Brynjolfsson et al., 2021). With eight years of data we observe the descending arm of such a curve but not its recovery; the interpretation therefore remains conditional, and the alternative — a persistent misalignment between research output and productive application in the Global South — cannot be excluded. Distinguishing the two is the single most valuable extension as longer panels accumulate.`),
  H2("5.3 Regional concentration and its reading"),
  P(`The pooled estimates conceal sharp regional structure. A naïve absorptive-capacity reading — weaker capabilities, worse outcomes — fits the Africa result but sits awkwardly with Asia, where AI research intensity is highest in the sample. A more plausible reading is compositional: the fastest expansions of AI research output in Asia coincide with phases of emissions-intensive industrial growth, so within-country increases in research output co-move with deteriorating frontier efficiency. The moderation results support the capability view at the margin — mobile connectivity significantly softens the GTFP association and Rule of Law moderates the conventional index. We caution that the AI measure is research output, not deployment; region-specific gaps between the two are themselves a candidate explanation and an agenda for measurement work.`),
  H2("5.4 Policy implications"),
  P("Three implications follow for AI-for-sustainability strategies. First, sequencing: the moderation evidence indicates that digital connectivity and institutional quality condition whatever productivity return AI research delivers, so strategies that fund research capacity ahead of connectivity and governance foundations are unlikely to show measurable green-productivity results within a policy cycle. Second, differentiation: the regional heterogeneity argues against uniform regional templates — the binding margin in one region (connectivity in much of Africa) differs from another (managing the emissions intensity of industrial expansion in parts of Asia). Third, expectation management aligned with SDG 8.2 and SDG 9: the absence of an environmental margin means AI research investment should be justified on innovation-system grounds, with green-productivity claims reserved until deployment-stage evidence exists."),
  H2("5.5 Limitations"),
  P(`Five limitations bound the conclusions. The design is associational; fixed effects with lagged regressors do not identify causal effects. Publications measure research capacity, not deployment, and the wedge between the two plausibly varies by region. The panel is short (T = 8), constrained by the OECD publication series and the CO₂ data lag. The ML index is infeasible for the sample's most emissions-intensive economies (${Object.keys(D.ml_infeasible_by_country).join(", ")}), which are effectively absent from the GTFP regressions. Finally, system-GMM estimates are deferred to the revision stage; the lag-profile and region-by-year results should be read with that pending check in mind.`, { noIndent: true }),

  // ---- 6. Conclusions ----
  H1("6. Conclusions"),
  P(`This paper provides the first cross-regional evidence on AI research and green total factor productivity in ${S.n_countries} emerging economies. AI research capacity shows no contemporaneous association with green productivity, a negative association that emerges under region-by-year fixed effects and deepens at a two-year lag, significant regional concentration in Asia and Africa, and no separate environmental margin relative to conventional productivity. For policy, the results caution against expecting short-run green-productivity dividends from AI research capacity alone: the moderation evidence points to digital connectivity and institutional quality as the binding complements, and the regional heterogeneity argues for differentiated rather than uniform AI-for-sustainability strategies across the Global South. Longer panels — as the OECD AI Observatory series accumulates — will allow a direct test of whether the delayed negative association resolves into the positive long-run effect that the general-purpose-technology view predicts.`, { noIndent: true }),

  // ---- Declarations ----
  H1("Declarations"),
  P("**CRediT authorship contribution statement:** Carlos Miguel Yalta Vargas: Conceptualisation, Methodology, Software, Data curation, Formal analysis, Writing – original draft. Lv KangJuan: Supervision, Methodology, Writing – review & editing. **Declaration of competing interest:** The authors declare no competing interests. **Data availability:** The replication package (gtfp_pipeline) will be deposited in a public repository upon acceptance. **Funding:** [state funding or absence]. **Declaration of generative AI in scientific writing:** [disclose per Elsevier policy].", { noIndent: true }),
  pb(),

  // ---- References ----
  H1("References"),
  todo("Verify against the current JCP reference style at submission (author–year shown). Fill [JCP-REF 1–5] with recent green-TFP papers from this journal and merge alphabetically."),
  ...REFS.map(r => new Paragraph({
    spacing: { after: 100, line: 264 }, indent: { left: 340, hanging: 340 },
    alignment: AlignmentType.JUSTIFIED, children: parseRuns(r, 19) })),
  pb(),

  // ---- Appendix A ----
  H1("Appendix A. Sample and data sources"),
  P("**Countries (N = 40).** *Latin America (17):* Argentina, Bolivia, Brazil, Chile, Colombia, Costa Rica, Dominican Republic, Ecuador, El Salvador, Guatemala, Honduras, Mexico, Nicaragua, Panama, Paraguay, Peru, Uruguay. *Asia (11):* Bangladesh, China, India, Indonesia, Kazakhstan, Malaysia, Pakistan, Philippines, Sri Lanka, Thailand, Vietnam. *Africa (12):* Algeria, Côte d'Ivoire, Egypt, Ethiopia, Ghana, Kenya, Morocco, Senegal, South Africa, Tanzania, Tunisia, Uganda. Nigeria excluded (constant-price national accounts unavailable post-rebase).", { noIndent: true }),
  P("**Series.** Real GDP NY.GDP.MKTP.KD; GFCF NE.GDI.FTOT.KD (China: NE.GDI.TOTL.KD); CO₂ EN.GHG.CO2.MT.CE.AR5; renewables EG.FEC.RNEW.ZS; employment ILOSTAT EMP_TEMP (15+); human capital PWT 10.01 hc; Rule of Law WGI RL.EST; mobile IT.CEL.SETS.P2; broadband IT.NET.BBND.P2; AI publications OECD.AI all-fields count. Full variable definitions in the replication package.", { noIndent: true }),
];

const doc = new Document({
  creator: "Claude",
  title: "JCP master draft v1 — assembled",
  styles: { default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "000000" },
        paragraph: { spacing: { before: 280, after: 130 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 21, bold: true, italics: true, color: "000000" },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "AI research and green TFP in 40 emerging economies · JCP master draft",
        font: FONT, size: 16, italics: true, color: "808080" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Page ", font: FONT, size: 16, color: "808080" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "808080" }),
                 new TextRun({ text: " of ", font: FONT, size: 16, color: "808080" }),
                 new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: "808080" })] })] }) },
    children }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/paper2_JCP_MASTER_v1.docx";
  fs.writeFileSync(out, buf);
  console.log(`Saved ${out} (${buf.length} bytes)`);
});
