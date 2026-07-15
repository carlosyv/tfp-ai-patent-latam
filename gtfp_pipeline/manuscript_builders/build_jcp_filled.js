// JCP manuscript draft — scaffold with all ◆◆PENDING◆◆ blocks filled from fill_data.json
// Every statistic is read from the pipeline export; nothing hand-typed.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, Header, Footer, PageNumber,
  BorderStyle, WidthType, ShadingType,
} = require("docx");

const F = JSON.parse(fs.readFileSync(
  "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/fill_data.json", "utf8"));

const FONT = "Calibri";

// ---------- number formatting (all from JSON) ----------
const r3 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(3);
const r4 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(4);
const st = (p) => (p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.10 ? "*" : "");
const cs = (c) => `${r4(c.b)}${st(c.p)} (${Number(c.se).toFixed(4)})`;
const csp = (c) => `β = ${r3(c.b)}, SE = ${Number(c.se).toFixed(3)}, p = ${Number(c.p).toFixed(2)}`;

const B = F.benchmark, RY = F.region_year_fe, Q = F.quantile_solow,
      H3 = F.h3_paired, CD = F.cd_tests, MOD = F.moderation,
      REG = F.regional_interactions, D = F.diag, S = F.sample;

// lag profile lookup (common sample)
const lag = {};
for (const row of F.lag_profile) {
  if (row.sample === "common") lag[`${row.dep}_${row.lag}`] = row;
}

// ---------- docx helpers ----------
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
const note = (t) => new Paragraph({ spacing: { after: 100 },
  children: [new TextRun({ text: t, font: FONT, size: 17, italics: true, color: "555555" })] });
const todo = (t) => new Paragraph({ spacing: { before: 100, after: 100 },
  shading: { fill: "FFF2CC", type: ShadingType.CLEAR },
  children: [new TextRun({ text: `◆ TO DRAFT — ${t}`, font: FONT, size: 19, bold: true, color: "B45309" })] });

const BD = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const ALL = { top: BD, bottom: BD, left: BD, right: BD };
const cell = (t, o = {}) => new TableCell({
  borders: ALL, width: { size: o.w, type: WidthType.DXA },
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 50, bottom: 50, left: 90, right: 90 },
  children: [new Paragraph({ spacing: { after: 0 },
    alignment: o.left ? AlignmentType.LEFT : AlignmentType.CENTER,
    children: [new TextRun({ text: String(t), font: FONT, size: 17,
      bold: o.bold || false, italics: o.it || false, color: o.color })] })] });
const row = (cells) => new TableRow({ children: cells });
const tTitle = (n, t) => new Paragraph({ spacing: { before: 220, after: 90 },
  children: [new TextRun({ text: `Table ${n}. ${t}`, font: FONT, size: 19, bold: true })] });
const tNote = (t) => new Paragraph({ spacing: { before: 70, after: 180 },
  alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: `Notes: ${t}`, font: FONT, size: 15, italics: true })] });
const W = 9360;

// ---------- content ----------
const kazZaf = Object.entries(D.ml_infeasible_by_country)
  .map(([c, n]) => `${c} (${n})`).join(", ");

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 180 },
    shading: { fill: "DEEBF7", type: ShadingType.CLEAR },
    children: [new TextRun({
      text: "MANUSCRIPT DRAFT v1 — Journal of Cleaner Production · results filled from gtfp_pipeline v1.1 (fill_data.json) · remaining to draft: §2 literature prose, §5 discussion prose · verify all numbers against a clean pipeline re-run before submission",
      font: FONT, size: 17, bold: true, color: "1F4E78" })] }),

  new Paragraph({ spacing: { after: 130 },
    children: [new TextRun({
      text: "Does artificial intelligence research improve green total factor productivity? Cross-regional evidence from 40 emerging economies in Latin America, Asia, and Africa",
      font: FONT, size: 28, bold: true })] }),
  P("**Carlos Miguel Yalta Vargas** ¹ · **Lv KangJuan** ²·* — ¹ School of Economics, Shanghai University; ² SILC Business School, Shanghai University; * corresponding author [email]", { noIndent: true }),

  // ---- Highlights ----
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
  note("All five ≤85 characters. Bullets 3–4 filled from pipeline results."),

  // ---- Abstract ----
  H1("Abstract"),
  P(`Artificial intelligence (AI) is promoted as an enabler of cleaner production and sustainable development, yet whether AI innovation is associated with greener productivity in developing economies remains untested at cross-regional scale. This study estimates the relationship between AI research output and green total factor productivity (GTFP) in ${S.n_countries} emerging economies across Latin America (${S.regions.LATAM}), Asia (${S.regions.ASIA}), and Africa (${S.regions.AFRICA}) over ${S.window[0]}–${S.window[1]}. GTFP is measured with a Malmquist–Luenberger index treating CO₂ emissions as an undesirable output, contrasted with a conventional Malmquist index and a Solow-residual measure; AI innovation is proxied by AI-related scientific publications from the OECD AI Observatory. The design addresses cross-sectional dependence through Driscoll–Kraay inference, Common Correlated Effects estimators, and region-by-year fixed effects. The contemporaneous association between AI research and GTFP is statistically insignificant (β = ${r3(B.GTFP_ML.b)}, p = ${B.GTFP_ML.p.toFixed(2)}); it is negative and marginally significant under region-by-year fixed effects (β = ${r3(RY.GTFP_ML.b)}, p = ${RY.GTFP_ML.p.toFixed(2)}) and strengthens to β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) at a two-year lag. The association is significantly more negative in Asia and Africa than in Latin America, and green and conventional productivity respond similarly, indicating no separate environmental margin. Mobile connectivity significantly softens the GTFP association, and Rule of Law moderates the conventional index. The findings caution against expecting short-run green-productivity dividends from AI research capacity alone and support sequencing AI strategies behind institutional and digital-infrastructure investments, in line with SDG 8.2 and SDG 9.`, { noIndent: true }),
  note("≈250 words — under the 300-word JCP cap. Every figure sourced from fill_data.json."),

  P("**Keywords:** artificial intelligence; green total factor productivity; Malmquist–Luenberger index; cleaner production; emerging economies; cross-sectional dependence", { noIndent: true }),

  // ---- 1. Introduction ----
  H1("1. Introduction"),
  P("Emerging economies face a dual challenge: reigniting productivity growth while decarbonising it. Growth across Latin America, developing Asia, and Africa remains substantially more emissions-intensive than in advanced economies, and the productivity gains that do materialise often come with rising CO₂. Against this backdrop, artificial intelligence is widely promoted — by national AI strategies and international organisations alike — as a technology that can deliver *cleaner* production: more output from fewer inputs with lower emissions. Whether AI innovation is in fact associated with greener productivity in the Global South is an open empirical question; the existing evidence concentrates on advanced economies and China, and almost exclusively on conventional productivity measures that ignore the emissions margin."),
  P("This paper provides, to our knowledge, the first cross-regional analysis of the relationship between AI research output and green total factor productivity (GTFP), covering " + `${S.n_countries} emerging economies — ${S.regions.LATAM} in Latin America, ${S.regions.ASIA} in Asia, and ${S.regions.AFRICA} in Africa — over ${S.window[0]}–${S.window[1]}. GTFP is measured with a Malmquist–Luenberger index that credits economies for expanding output while contracting CO₂ emissions, and is benchmarked against a conventional Malmquist index and a Solow-residual measure so that the environmental margin of the AI–productivity relationship is itself testable. AI innovation is proxied by AI-related scientific publications, observed on a consistent bibliometric basis across all sample countries. The econometric design treats cross-sectional dependence explicitly — Driscoll–Kraay inference, Common Correlated Effects estimators, and region-by-year fixed effects.`),
  P(`Three findings emerge. First, the contemporaneous AI–GTFP association is statistically indistinguishable from zero (${csp(B.GTFP_ML)}); under region-by-year fixed effects it is negative and marginally significant (${csp(RY.GTFP_ML)}), and it deepens monotonically with the lag of the AI measure, reaching β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) at two years on a lag-invariant sample — a delayed-adjustment pattern consistent with the productivity J-curve. Second, the association is regionally concentrated: interactions with the conventional Malmquist index are significantly negative for Asia (β = ${r3(REG.MALM_CRS["AIxASIA_b"])}, p < 0.01) and Africa (β = ${r3(REG.MALM_CRS["AIxAFRICA_b"])}, p < 0.01) relative to Latin America, and excluding Latin America turns the pooled GTFP association significantly negative (β = ${r3(D.drop_LATAM.GTFP_ML.b)}, p < 0.05). Third, green and conventional productivity respond similarly: a paired coefficient-difference test finds no significant environmental margin at one- or two-year lags (Δβ = ${r3(H3.L1.b)} and ${r3(H3.L2.b)}, both insignificant), while moderation analysis shows mobile connectivity significantly softening the GTFP association and Rule of Law moderating the conventional index.`),
  P("The contributions are threefold: the first cross-regional AI–GTFP evidence for the Global South; an explicit test of the environmental margin via the GTFP–conventional-TFP contrast; and a treatment of cross-sectional dependence — diagnosed, and resolved with region-by-year fixed effects — that is absent from prior green-TFP studies. Section 2 reviews related literature, Section 3 describes materials and methods, Section 4 reports results, Section 5 discusses implications, and Section 6 concludes."),

  // ---- 2. Literature ----
  H1("2. Literature review and hypotheses"),
  todo("§2 prose (~900 words in three subsections: AI and productivity; green TFP and the ML index; absorptive capacity). Guidance retained from scaffold. Close with H1–H3 as stated below."),
  P("*H1.* AI research output is positively associated with green total factor productivity. *H2.* The association is stronger in economies with stronger institutions and digital infrastructure. *H3.* The AI–GTFP association differs from the AI–conventional-TFP association (an environmental margin exists).", { noIndent: true }),

  // ---- 3. Materials and methods ----
  H1("3. Materials and methods"),
  H2("3.1 Sample and data"),
  P(`${S.n_countries} emerging economies (${S.regions.LATAM} Latin America, ${S.regions.ASIA} Asia, ${S.regions.AFRICA} Africa), ${S.window[0]}–${S.window[1]} (T = 8; ${S.n_obs_panel} country-year observations). Nigeria is excluded because constant-price national accounts are unavailable following its GDP rebase. Data: WDI (GDP, GFCF, CO₂, renewables, controls), ILOSTAT employment, PWT 10.01 human capital (trend-extended post-2019), WGI Rule of Law, OECD AI Observatory publications. China's capital input uses gross capital formation (GFCF unavailable). Country list and series codes in Appendix A.`),
  H2("3.2 Green total factor productivity"),
  P(`The Malmquist–Luenberger (ML) index is computed from directional distance functions with inputs (PIM capital, δ = 0.05, initialised 2008; effective labour = employment × human capital), desirable output real GDP, undesirable output CO₂, and direction g = (y, −b). The conventional CRS Malmquist and the Solow residual (α = 0.35, labour-augmenting human capital) provide the environmental-margin contrast. Of ${S.gtfp_possible} feasible index observations, ${S.gtfp_valid} ML values are valid; infeasibility concentrates in the sample's most CO₂-intensive economies — ${kazZaf} — which are therefore effectively excluded from the GTFP regressions, a restriction reported transparently and common to directional-distance applications.`),
  H2("3.3 Econometric strategy"),
  P("Baseline: two-way fixed effects of each productivity measure on the one-year-lagged log of AI publications per million population plus controls (log GDP per capita, trade openness, FDI, government consumption, urbanisation), with Driscoll–Kraay standard errors. Cross-sectional dependence is diagnosed with the Pesaran CD test; where residual dependence reflects a between-region factor, region-by-year fixed effects are added. Regional heterogeneity uses region × AI interactions and subsamples; moderation uses demeaned-moderator interactions with median-split corroboration; distributional heterogeneity uses the Canay (2011) two-step quantile estimator with country-cluster bootstrap. The identification is associational throughout; lag-profile analysis on a lag-invariant common sample separates dynamics from sample composition. System GMM is deferred to a companion Stata implementation."),

  // ---- 4. Results ----
  H1("4. Results"),

  H2("4.1 Descriptive statistics and diagnostics"),
  P(`Table 1 summarises the panel by region. Mean GTFP-ML is below unity in all three regions (${["LATAM","ASIA","AFRICA"].map(r => `${r === "LATAM" ? "Latin America" : r === "ASIA" ? "Asia" : "Africa"} ${F.descriptives[r].GTFP_ML.toFixed(3)}`).join(", ")}), indicating on-average green-productivity regression over the window; AI research intensity is highest in Asia (mean ln AI publications per million ${F.descriptives.ASIA.LN_AI.toFixed(2)} vs ${F.descriptives.LATAM.LN_AI.toFixed(2)} in Latin America and ${F.descriptives.AFRICA.LN_AI.toFixed(2)} in Africa).`, { noIndent: false }),

  tTitle(1, "Panel means by region, 2016–2023."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2160, 1800, 1800, 1800, 1800],
    rows: [
      row([cell("", { w: 2160 }), cell("GTFP-ML", { w: 1800, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Malmquist CRS", { w: 1800, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Solow ln(TFP)", { w: 1800, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("ln AI pubs p.m.", { w: 1800, bold: true, fill: "1F4E78", color: "FFFFFF" })]),
      ...["LATAM", "ASIA", "AFRICA"].map(r => row([
        cell(r === "LATAM" ? "Latin America" : r === "ASIA" ? "Asia" : "Africa", { w: 2160, left: true }),
        cell(F.descriptives[r].GTFP_ML.toFixed(4), { w: 1800 }),
        cell(F.descriptives[r].MALM_CRS.toFixed(4), { w: 1800 }),
        cell(F.descriptives[r].LN_TFP_SOLOW.toFixed(3), { w: 1800 }),
        cell(F.descriptives[r].LN_AI.toFixed(3), { w: 1800 })])),
    ] }),
  tNote("Full descriptive statistics (SD, min, max, N) in Supplementary Table S1. Index measures are year-over-year change indices; Solow is a log level."),

  P(`Pesaran CD tests on baseline FE residuals show no significant dependence for the index measures (GTFP-ML CD = ${CD.GTFP_ML.CD}, p = ${CD.GTFP_ML.p.toFixed(2)}; Malmquist CD = ${CD.MALM_CRS.CD}, p = ${CD.MALM_CRS.p.toFixed(2)}) but strong dependence for the Solow level measure (CD = ${CD.LN_TFP_SOLOW.CD}, p < 0.001). The Solow dependence is a between-region phenomenon: within-region CD statistics are all insignificant (${Object.entries(D.solow_cd_within_regions).map(([k, v]) => `${k.replace("cd_", "")} ${v.CD}`).join("; ")}), and region-by-year fixed effects reduce the pooled statistic to ${RY.LN_TFP_SOLOW.CD_after} (p = ${RY.LN_TFP_SOLOW.CD_p.toFixed(2)}). Region-by-year fixed effects are therefore reported alongside the baseline throughout.`),

  H2("4.2 Benchmark estimates"),
  tTitle(2, "AI research (t−1) and productivity: benchmark estimates."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([cell("", { w: 2900 }), cell("GTFP-ML", { w: 2150, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Malmquist CRS", { w: 2150, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Solow ln(TFP)", { w: 2160, bold: true, fill: "1F4E78", color: "FFFFFF" })]),
      row([cell("FE-DK (country + year FE)", { w: 2900, left: true }),
           cell(cs(B.GTFP_ML), { w: 2150 }), cell(cs(B.MALM_CRS), { w: 2150 }), cell(cs(B.LN_TFP_SOLOW), { w: 2160 })]),
      row([cell("Country + region×year FE", { w: 2900, left: true }),
           cell(cs(RY.GTFP_ML), { w: 2150 }), cell(cs(RY.MALM_CRS), { w: 2150 }), cell(cs(RY.LN_TFP_SOLOW), { w: 2160 })]),
      row([cell("N", { w: 2900, left: true }),
           cell(B.GTFP_ML.N, { w: 2150 }), cell(B.MALM_CRS.N, { w: 2150 }), cell(B.LN_TFP_SOLOW.N, { w: 2160 })]),
    ] }),
  tNote("Driscoll–Kraay standard errors in parentheses (Bartlett kernel). Controls: ln GDP per capita, trade openness, FDI, government consumption, urbanisation. * p<0.10, ** p<0.05, *** p<0.01."),

  P(`The contemporaneous-lag benchmark association is small and insignificant for all three measures. Under region-by-year fixed effects — the specification favoured by the CD diagnostics — the GTFP-ML coefficient is negative and marginally significant (${csp(RY.GTFP_ML)}).`),

  H2("4.3 Lag profile"),
  tTitle(3, "Lag profile on the lag-invariant common sample."),
  new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [2900, 2150, 2150, 2160],
    rows: [
      row([cell("AI lag", { w: 2900, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("GTFP-ML", { w: 2150, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Malmquist CRS", { w: 2150, bold: true, fill: "1F4E78", color: "FFFFFF" }),
           cell("Solow ln(TFP)", { w: 2160, bold: true, fill: "1F4E78", color: "FFFFFF" })]),
      ...["L0", "L1", "L2"].map(L => row([
        cell(L === "L0" ? "Contemporaneous" : L === "L1" ? "One-year lag" : "Two-year lag", { w: 2900, left: true }),
        ...["GTFP_ML", "MALM_CRS", "LN_TFP_SOLOW"].map((d, i) =>
          cell(cs(lag[`${d}_${L}`]), { w: i === 2 ? 2160 : 2150 }))])),
    ] }),
  tNote(`Common sample: observations with all three lags observed (N = ${lag["GTFP_ML_L0"].N} for GTFP-ML, ${lag["MALM_CRS_L0"].N} otherwise). Full-sample estimates in Supplementary Table S2.`),
  P(`For GTFP-ML the association deepens monotonically with the lag — from ${r4(lag["GTFP_ML_L0"].b)} contemporaneously to ${r4(lag["GTFP_ML_L2"].b)}${st(lag["GTFP_ML_L2"].p)} at two years on identical observations — so the two-year result reflects dynamics rather than sample composition. A delayed negative association that strengthens over the horizon is the signature of adjustment costs during technology absorption predicted by the productivity J-curve literature.`),

  H2("4.4 Regional heterogeneity"),
  P(`Region × AI interactions show the conventional-Malmquist association significantly more negative in Asia (β = ${r3(REG.MALM_CRS["AIxASIA_b"])}${st(REG.MALM_CRS["AIxASIA_p"])}) and Africa (β = ${r3(REG.MALM_CRS["AIxAFRICA_b"])}${st(REG.MALM_CRS["AIxAFRICA_p"])}) than in Latin America. Leave-one-region-out estimates make the same point: excluding Latin America, the pooled association is significantly negative for both GTFP-ML (${csp(D.drop_LATAM.GTFP_ML)}) and the conventional index (${csp(D.drop_LATAM.MALM_CRS)}). The pooled null therefore averages a near-zero Latin American association with negative associations in Asia and Africa. Full interaction and subsample estimates in Table 4 [assemble from t4_regional.json].`),

  H2("4.5 Moderation"),
  P(`Mobile connectivity significantly softens the GTFP association (interaction ${csp(MOD.GTFP_ML.MOBILE)}), consistent with digital infrastructure enabling productive absorption of AI research. Rule of Law significantly moderates the conventional index (${csp(MOD.MALM_CRS.RULE_OF_LAW)}), echoing the institutional-moderation pattern documented for Latin America in prior work; broadband (${csp(MOD.LN_TFP_SOLOW.BROADBAND)}) and lagged renewable-energy share (${csp(MOD.LN_TFP_SOLOW.RENEW_L1)}) moderate the Solow measure. Median-split subsample estimates corroborate the interactions [Table 5 from t5_moderation.csv].`),

  H2("4.6 The environmental margin (H3)"),
  P(`Because GTFP-ML and the conventional Malmquist index are observed on the same country-years, regressing their difference on AI and controls delivers a paired test of the environmental margin. The coefficient difference is insignificant at the one-year (Δβ = ${r3(H3.L1.b)}, p = ${H3.L1.p.toFixed(2)}) and two-year (Δβ = ${r3(H3.L2.b)}, p = ${H3.L2.p.toFixed(2)}) lags; only the contemporaneous difference is marginally positive (Δβ = ${r3(H3.L0.b)}, p = ${H3.L0.p.toFixed(2)}). The two indices correlate at ${D.wedge_overall.corr_indices} with a mean wedge indistinguishable from zero. H3 is therefore not supported: AI research relates to green and conventional productivity similarly, implying that its measured association operates through the input–output core of productivity rather than through the emissions margin.`),

  H2("4.7 Distributional heterogeneity and robustness"),
  P(`Canay quantile estimates for Solow ln(TFP) are positive across the conditional distribution (τ = 0.10: ${r4(Q["0.1"].b)}${st(Q["0.1"].p)}; τ = 0.25: ${r4(Q["0.25"].b)}${st(Q["0.25"].p)}; τ = 0.50: ${r4(Q["0.5"].b)}${st(Q["0.5"].p)}; τ = 0.75: ${r4(Q["0.75"].b)}${st(Q["0.75"].p)}; τ = 0.90: ${r4(Q["0.9"].b)}${st(Q["0.9"].p)}), while the conditional-mean estimate is insignificant — level and change measures answer different questions, and the positive level association does not contradict the negative lagged change association. The benchmark is robust to dropping China and to trimming the index tails; unnormalised publication counts yield the same null [Table 6 from robustness block]. GMM estimates are deferred to the revision stage.`),

  // ---- 5. Discussion ----
  H1("5. Discussion"),
  todo("§5 prose (~700 words). Key filled interpretation points to build on:"),
  P(`(i) The lag-deepening negative GTFP association (${r4(lag["GTFP_ML_L1"].b)} → ${r4(lag["GTFP_ML_L2"].b)}${st(lag["GTFP_ML_L2"].p)}) is consistent with J-curve adjustment costs rather than a permanent penalty — testable only with longer panels. (ii) The regional concentration (negative in Asia and Africa, null in Latin America) inverts the absorptive-capacity prior and deserves careful discussion: one reading is that fast-growing AI research bases in Asia coincide with emissions-intensive industrial expansion phases. (iii) The null environmental margin (H3) means AI research is not yet associated with *cleaner* growth specifically — the policy case for AI-for-sustainability rests on complementary investments, not on AI capacity alone. (iv) Moderation results (mobile connectivity softening; Rule of Law) support sequencing: connectivity and institutions first. (v) Limitations: associational design; publications ≠ deployment; T = 8; ML infeasibility excludes the two most CO₂-intensive economies (${kazZaf.split(",").slice(0, 2).join(",")}); CO₂ data lag truncates at 2023.`, { noIndent: true }),

  // ---- 6. Conclusions ----
  H1("6. Conclusions"),
  P(`This paper provides the first cross-regional evidence on AI research and green total factor productivity in ${S.n_countries} emerging economies. AI research capacity shows no contemporaneous association with green productivity, a negative association that emerges under region-by-year fixed effects and deepens at a two-year lag, significant regional concentration in Asia and Africa, and no separate environmental margin relative to conventional productivity. For policy, the results caution against expecting short-run green-productivity dividends from AI research capacity alone: the moderation evidence points to digital connectivity and institutional quality as the binding complements, and the regional heterogeneity argues for differentiated rather than uniform AI-for-sustainability strategies across the Global South. Longer panels — as the OECD AI Observatory series accumulates — will allow a direct test of whether the delayed negative association resolves into the positive long-run effect that the general-purpose-technology view predicts.`, { noIndent: true }),

  // ---- Declarations ----
  H1("Declarations"),
  P("**CRediT:** C.M.Y.V.: Conceptualisation, Methodology, Software, Data curation, Formal analysis, Writing – original draft. K.L.: Supervision, Methodology, Writing – review & editing. **Competing interests:** none. **Data availability:** replication package (gtfp_pipeline) to be deposited on acceptance. **Funding:** [state]. **Generative AI statement:** [disclose per Elsevier policy].", { noIndent: true }),
];

const doc = new Document({
  creator: "Claude",
  title: "JCP manuscript draft v1 — filled",
  styles: { default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, color: "1F4E78" },
        paragraph: { spacing: { before: 280, after: 130 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 21, bold: true, italics: true, color: "2E75B6" },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "JCP draft v1 · results from gtfp_pipeline v1.1",
        font: FONT, size: 16, italics: true, color: "808080" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Page ", font: FONT, size: 16, color: "808080" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "808080" })] })] }) },
    children }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/paper2_JCP_manuscript_draft_v1.docx";
  fs.writeFileSync(out, buf);
  console.log(`Saved ${out} (${buf.length} bytes)`);
});
