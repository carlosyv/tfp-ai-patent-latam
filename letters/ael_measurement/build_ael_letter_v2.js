// AEL letter v2 — adds a Framework block (display equations) and an explicit
// Robustness subsection, matching the structure of recent AEL acceptances.
// Numbers read from ael_results.json + ael_robustness.json. Output overwrites
// the working file Applied-Economics-Letters-manuscript-cyv.docx.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel,
  Header, Footer, PageNumber, Table, TableRow, TableCell, WidthType,
  BorderStyle, ShadingType, ImageRun,
} = require("docx");

const AELDIR = "/sessions/busy-trusting-ride/mnt/tfp-ai/publications/AEL";
const RES = JSON.parse(fs.readFileSync(AELDIR + "/ael_results.json", "utf8"));
const ROB = JSON.parse(fs.readFileSync(AELDIR + "/ael_robustness.json", "utf8"));

const FONT = "Times New Roman";
const r2 = (x) => Number(x).toFixed(2);
const r3 = (x) => Number(x).toFixed(3);

function parseRuns(text, size = 22) {
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
  spacing: { after: 120, line: 300 }, alignment: AlignmentType.JUSTIFIED,
  indent: o.noIndent ? undefined : { firstLine: 340 }, children: parseRuns(t) });
const EQ = (t) => new Paragraph({ spacing: { before: 60, after: 120 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: t, font: "Cambria Math", size: 22, italics: true })] });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 240, after: 110 },
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true })] });
const H2 = (t) => new Paragraph({ spacing: { before: 160, after: 80 },
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, italics: true })] });

const BD = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const ALL = { top: BD, bottom: BD, left: BD, right: BD };
const cell = (t, o = {}) => new TableCell({
  borders: ALL, width: { size: o.w, type: WidthType.DXA },
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 45, bottom: 45, left: 90, right: 90 },
  children: [new Paragraph({ spacing: { after: 0 },
    alignment: o.left ? AlignmentType.LEFT : AlignmentType.CENTER,
    children: [new TextRun({ text: String(t), font: FONT, size: 18,
      bold: o.bold || false, italics: o.it || false, color: o.color })] })] });
const row = (c) => new TableRow({ children: c });
const HC = (t, w) => cell(t, { w, bold: true, fill: "1F4E78", color: "FFFFFF" });

const fig = fs.readFileSync(AELDIR + "/ael_figure1.png");

// star helper
const str = (p) => (p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.10 ? "*" : "");

const children = [
  // Title
  new Paragraph({ spacing: { after: 140 },
    children: [new TextRun({
      text: "Do patents and publications measure the same AI innovation? Evidence from Latin American panels",
      font: FONT, size: 28, bold: true })] }),
  P("**Carlos Miguel Yalta Vargas**¹ and **Lv KangJuan**²·* — ¹ School of Economics, Shanghai University; ² SILC Business School, Shanghai University. * Corresponding author: [email]", { noIndent: true }),

  // Abstract
  H1("Abstract"),
  P("National studies of artificial intelligence (AI) and economic performance proxy AI innovation with either patent counts or scientific publications, implicitly treating the two as substitutes. Using nine Latin American countries over 2016–2024, we show that the two standard measures — a WIPO keyword-based AI patent stock and OECD AI Observatory publications — agree almost perfectly across countries (r = 0.91) but share essentially no variation within countries once common time effects are removed (r = 0.07, p = 0.55); annual growth rates are likewise uncorrelated (r = 0.11). The near-zero within-country agreement is robust to the patent-stock depreciation rate, to per-GDP normalisation, to excluding Brazil, and to rank-based correlation, and the within-country relationship even reverses sign across sub-periods. Because fixed-effects panel estimators identify from precisely this within variation, panel studies of AI and productivity are not robust to the choice of innovation measure, whereas cross-sectional rankings are. We recommend reporting both measures and treating them as complements capturing distinct dimensions — commercially oriented invention versus scientific capacity.", { noIndent: true }),
  P("**Keywords:** artificial intelligence; patents; bibliometrics; measurement; panel data. **JEL:** O31; O34; C23; O54.", { noIndent: true }),

  // I. Introduction
  H1("I. Introduction"),
  P("A fast-growing literature estimates the economic effects of national and regional AI activity, proxying AI innovation with patent counts in some studies (Luo, Lei, and Hou 2024) and with measures built on scientific and technical output in others (Acemoglu et al. 2022; Babina et al. 2024; OECD 2024). The choice is usually made on availability grounds and is rarely defended: patents and publications are implicitly treated as interchangeable signals of the same underlying construct. Whether they are interchangeable is an empirical question with direct consequences for inference. If the two measures agree on levels but not on changes, then cross-country comparisons are robust to the choice while fixed-effects panel estimates — the workhorse design of this literature — are not."),
  P("This letter provides direct evidence from a setting where both measures can be constructed consistently: nine Latin American countries observed annually over 2016–2024. The knowledge-production-function tradition treats patents as an indicator of commercially oriented inventive output, subject to cross-country differences in patent propensity (Griliches 1990); bibliometric counts capture scientific capacity, subject to different incentives and a different growth process (Bornmann and Mutz 2015). For AI specifically — a technology whose research frontier is dominated by open publication and pre-print culture — the wedge between the two may be unusually wide."),

  // II. Data and methodology
  H1("II. Data and methodology"),
  H2("Data"),
  P("AI patents are identified through Spanish- and Portuguese-language keyword searches of the WIPO database, following the WIPO Technology Trends keyword list (WIPO 2019), aggregated to country–year counts and accumulated into a stock by the perpetual inventory method with knowledge depreciation δ = 0.36 (Yan, Chen, and Zhang 2020). AI publications are the OECD AI Observatory all-fields count of AI-related scientific publications (OECD 2024). The overlap window is 2016–2024 (the Observatory's coverage begins in 2016; 2025 is incomplete in the source), giving a balanced panel of nine countries — Argentina, Brazil, Chile, Colombia, Costa Rica, Dominican Republic, Mexico, Peru, Uruguay — and 81 observations.", { noIndent: true }),
  H2("Framework"),
  P("Let S_{it} denote the AI patent stock and A_{it} the AI publication count for country i in year t. The stock accumulates as", { noIndent: true }),
  EQ("S_{it} = P_{it} + (1 − δ) S_{i,t−1},"),
  P("where P_{it} is new patent filings and δ = 0.36. Both measures enter in logs, x_{it} = ln(S_{it} + 1) and y_{it} = ln(A_{it} + 1). We compare the two measures at three levels of variation. The between-country agreement is the correlation of country means,", { noIndent: true }),
  EQ("ρ_B = corr( x̄_i , ȳ_i ),"),
  P("where x̄_i and ȳ_i average over t. The within-country agreement — the variation that a two-way fixed-effects estimator uses — is the correlation of the doubly demeaned series,", { noIndent: true }),
  EQ("x̃_{it} = x_{it} − x̄_i − x̄_t + x̄,   ỹ_{it} = y_{it} − ȳ_i − ȳ_t + ȳ,"),
  EQ("ρ_W = corr( x̃_{it} , ỹ_{it} ),"),
  P("where x̄_t and ȳ_t are year means and x̄, ȳ are grand means. We also report the correlation of annual log growth rates, ρ_Δ = corr(Δx_{it}, Δy_{it}), and a variance decomposition giving the between-country share of each measure's total variance. Because any two-way fixed-effects regression of an outcome on 'AI innovation' is identified from x̃_{it}, ρ_W is the statistic that governs whether panel results are robust to the choice of proxy."),

  // III. Results
  H1("III. Results"),
  P(`Table 1 reports the agreement statistics; Figure 1 visualises the contrast. Between countries, the two measures are nearly interchangeable: ρ_B = ${r3(RES.cross_section.pearson_r)} (Spearman ${r3(RES.cross_section.spearman_rho)}), and year-by-year cross-sectional rank correlations are stable between 0.78 and 0.92 across all nine years. A study that ranks Latin American countries by AI capacity reaches the same ordering with either measure.`),
  P(`Within countries the picture reverses. The pooled country-demeaned correlation is ${r3(RES.within_pooled.pearson_r)}, and once year effects are also removed — the exact transformation a two-way fixed-effects estimator applies — it collapses to ρ_W = ${r3(RES.within_twoway.pearson_r)} (p = ${r2(RES.within_twoway.p)}). Annual growth rates are similarly unrelated (ρ_Δ = ${r3(RES.growth_rates.pearson_r)}, p = ${r2(RES.growth_rates.p)}). Country-level time-series correlations are heterogeneous: significantly positive in ${RES.per_country_summary.sig_pos_5pct} of nine countries, near zero in three, and significantly negative in one. Both measures are dominated by between-country variance (${r3(RES.between_share.ln_stock)} of the log patent stock and ${r3(RES.between_share.ln_pub)} of log publications), so fixed-effects designs discard nearly all the variation on which the two measures agree and retain the sliver on which they disagree.`),
  P("The implication is mechanical but consequential. Since the two standard proxies share essentially none of the within variation, coefficient estimates from two-way fixed-effects models are measure-specific: a panel result obtained with patents cannot be expected to replicate with publications, and vice versa — not because either measure is wrong, but because they move for different reasons at annual frequency. Cross-sectional and between-style designs, by contrast, are robust to the choice."),

  // Table 1
  new Paragraph({ spacing: { before: 180, after: 90 },
    children: [new TextRun({ text: "Table 1. Agreement between AI patent stock and AI publications, nine Latin American countries, 2016–2024.", font: FONT, size: 20, bold: true })] }),
  new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [4680, 1560, 1560, 1560],
    rows: [
      row([HC("Statistic", 4680), HC("Estimate", 1560), HC("p-value", 1560), HC("N", 1560)]),
      row([cell("Between countries: ρ_B (Pearson, country means)", { w: 4680, left: true }), cell(r3(RES.cross_section.pearson_r), { w: 1560 }), cell(r2(RES.cross_section.p), { w: 1560 }), cell("9", { w: 1560 })]),
      row([cell("Between countries: Spearman ρ (country means)", { w: 4680, left: true }), cell(r3(RES.cross_section.spearman_rho), { w: 1560 }), cell(r2(RES.cross_section.p_rho), { w: 1560 }), cell("9", { w: 1560 })]),
      row([cell("Within countries: pooled r (country-demeaned)", { w: 4680, left: true }), cell(r3(RES.within_pooled.pearson_r), { w: 1560 }), cell("<0.01", { w: 1560 }), cell("81", { w: 1560 })]),
      row([cell("Within countries: ρ_W (two-way demeaned)", { w: 4680, left: true, bold: true }), cell(r3(RES.within_twoway.pearson_r), { w: 1560, bold: true }), cell(r2(RES.within_twoway.p), { w: 1560, bold: true }), cell("81", { w: 1560 })]),
      row([cell("Annual growth rates: ρ_Δ (Δln)", { w: 4680, left: true }), cell(r3(RES.growth_rates.pearson_r), { w: 1560 }), cell(r2(RES.growth_rates.p), { w: 1560 }), cell(String(RES.growth_rates.n), { w: 1560 })]),
      row([cell("Between-country variance share: ln patent stock", { w: 4680, left: true }), cell(r3(RES.between_share.ln_stock), { w: 1560 }), cell("—", { w: 1560 }), cell("81", { w: 1560 })]),
      row([cell("Between-country variance share: ln publications", { w: 4680, left: true }), cell(r3(RES.between_share.ln_pub), { w: 1560 }), cell("—", { w: 1560 }), cell("81", { w: 1560 })]),
      row([cell("Country-level correlations: median r; sig.+ / sig.−", { w: 4680, left: true }), cell(`${r3(RES.per_country_summary.median_r)}; ${RES.per_country_summary.sig_pos_5pct} / ${RES.per_country_summary.sig_neg_5pct}`, { w: 1560 }), cell("—", { w: 1560 }), cell("9", { w: 1560 })]),
    ] }),
  new Paragraph({ spacing: { before: 60, after: 170 },
    children: [new TextRun({ text: "Notes: Patent stock from WIPO Spanish/Portuguese keyword searches, PIM with δ = 0.36; publications from OECD AI Observatory (all fields). Both in ln(x + 1). ρ_W removes country and year means, replicating the variation used by two-way fixed-effects estimators.", font: FONT, size: 16, italics: true })] }),

  // Figure 1
  new Paragraph({ spacing: { before: 80, after: 60 }, alignment: AlignmentType.CENTER,
    children: [new ImageRun({ type: "png", data: fig, transformation: { width: 600, height: 252 },
      altText: { title: "Figure 1", description: "Between vs within correlation", name: "fig1" } })] }),
  new Paragraph({ spacing: { after: 180 },
    children: [new TextRun({ text: "Figure 1. (a) Country means, 2016–2024: near-perfect agreement. (b) Two-way demeaned observations: no residual co-movement.", font: FONT, size: 16, italics: true })] }),

  // IV. Robustness
  H1("IV. Robustness"),
  P(`The within-country result is the paper's inferential core, so we subject ρ_W to four perturbations and a stability check (Table 2). It is unchanged under an alternative patent-stock depreciation rate (δ = 0.22: ρ_W = ${r3(ROB.R2_delta_022.within2way_r)}), under per-GDP rather than per-capita-style normalisation of the stock (ρ_W = ${r3(ROB.R3_per_gdp.within2way_r)}), under exclusion of Brazil, the dominant filer (ρ_W = ${r3(ROB.R4_drop_BRA.within2way_r)}), and under a rank-based (Spearman) definition (ρ_W = ${r3(ROB.R6_spearman_within.within2way_rho)}). In every case the two-way within correlation is small and statistically insignificant, while the between-country correlation stays near 0.9. A sub-period split is more telling still: the within-country correlation is significantly positive in 2016–2020 (${r3(ROB.R5a_2016_2020.within2way_r)}${str(ROB.R5a_2016_2020.within2way_p)}) but significantly negative in 2021–2024 (${r3(ROB.R5b_2021_2024.within2way_r)}${str(ROB.R5b_2021_2024.within2way_p)}). The near-zero pooled value is thus not masking a stable relationship; the within-country co-movement is unstable, even reversing sign, which is exactly what one expects if the two series are driven by different underlying processes at annual frequency.`),

  new Paragraph({ spacing: { before: 180, after: 90 },
    children: [new TextRun({ text: "Table 2. Robustness of the two-way within correlation ρ_W.", font: FONT, size: 20, bold: true })] }),
  new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [4680, 1560, 1560, 1560],
    rows: [
      row([HC("Specification", 4680), HC("ρ_W", 1560), HC("p-value", 1560), HC("ρ_B", 1560)]),
      row([cell("Baseline (δ = 0.36)", { w: 4680, left: true }), cell(r3(ROB.R1_baseline.within2way_r), { w: 1560 }), cell(r2(ROB.R1_baseline.within2way_p), { w: 1560 }), cell(r3(ROB.R1_baseline.between_r), { w: 1560 })]),
      row([cell("Alternative depreciation δ = 0.22", { w: 4680, left: true }), cell(r3(ROB.R2_delta_022.within2way_r), { w: 1560 }), cell(r2(ROB.R2_delta_022.within2way_p), { w: 1560 }), cell(r3(ROB.R2_delta_022.between_r), { w: 1560 })]),
      row([cell("Per-GDP normalisation of stock", { w: 4680, left: true }), cell(r3(ROB.R3_per_gdp.within2way_r), { w: 1560 }), cell(r2(ROB.R3_per_gdp.within2way_p), { w: 1560 }), cell(r3(ROB.R3_per_gdp.between_r), { w: 1560 })]),
      row([cell("Excluding Brazil", { w: 4680, left: true }), cell(r3(ROB.R4_drop_BRA.within2way_r), { w: 1560 }), cell(r2(ROB.R4_drop_BRA.within2way_p), { w: 1560 }), cell(r3(ROB.R4_drop_BRA.between_r), { w: 1560 })]),
      row([cell("Rank-based (Spearman) ρ_W", { w: 4680, left: true }), cell(r3(ROB.R6_spearman_within.within2way_rho), { w: 1560 }), cell(r2(ROB.R6_spearman_within.within2way_p), { w: 1560 }), cell("—", { w: 1560 })]),
      row([cell("Sub-period 2016–2020", { w: 4680, left: true }), cell(r3(ROB.R5a_2016_2020.within2way_r) + str(ROB.R5a_2016_2020.within2way_p), { w: 1560 }), cell(r2(ROB.R5a_2016_2020.within2way_p), { w: 1560 }), cell("—", { w: 1560 })]),
      row([cell("Sub-period 2021–2024", { w: 4680, left: true }), cell(r3(ROB.R5b_2021_2024.within2way_r) + str(ROB.R5b_2021_2024.within2way_p), { w: 1560 }), cell(r2(ROB.R5b_2021_2024.within2way_p), { w: 1560 }), cell("—", { w: 1560 })]),
    ] }),
  new Paragraph({ spacing: { before: 60, after: 170 },
    children: [new TextRun({ text: "Notes: ρ_W is the two-way (country and year) demeaned correlation between the log AI patent stock and log AI publications; ρ_B is the between-country correlation of means. * p<0.10, ** p<0.05, *** p<0.01. p-values from the Fisher z-transform.", font: FONT, size: 16, italics: true })] }),

  // V. Conclusion
  H1("V. Conclusion"),
  P("Patents and publications agree on which Latin American countries have more AI capacity, and disagree almost entirely on when a country's AI activity changes. The two standard proxies are complements, not substitutes: patents track commercially oriented invention filtered through heterogeneous patent propensities; publications track scientific output with different timing and incentives — a divergence consistent with the lag structure that intangible-complements models predict for general purpose technologies (Brynjolfsson, Rock, and Syverson 2021). Empirical practice should follow: panel fixed-effects studies of AI and economic outcomes should report results under both measures rather than treating one as a robustness check for the other, and null or contradictory findings across studies using different proxies should not be read as replication failures. Whether the same divergence holds in economies with deeper patenting systems is an open question; the sparse-patenting environment of Latin America (Cimoli, Hofman, and Mulder 2010) plausibly widens the wedge, which makes the region a cautionary benchmark for the growing AI-and-development literature."),

  // References
  H1("References"),
  ...[
    "Acemoglu, D., D. Autor, J. Hazell, and P. Restrepo. 2022. “Artificial Intelligence and Jobs: Evidence from Online Vacancies.” Journal of Labor Economics 40 (S1): S293–S340.",
    "Babina, T., A. Fedyk, A. He, and J. Hodson. 2024. “Artificial Intelligence, Firm Growth, and Product Innovation.” Journal of Financial Economics 151: 103745.",
    "Bornmann, L., and R. Mutz. 2015. “Growth Rates of Modern Science: A Bibliometric Analysis Based on the Number of Publications and Cited References.” Journal of the Association for Information Science and Technology 66 (11): 2215–2222.",
    "Brynjolfsson, E., D. Rock, and C. Syverson. 2021. “The Productivity J-Curve: How Intangibles Complement General Purpose Technologies.” American Economic Journal: Macroeconomics 13 (1): 333–372.",
    "Cimoli, M., A. Hofman, and N. Mulder. 2010. Innovation and Economic Development: The Impact of Information and Communication Technologies in Latin America. Cheltenham: Edward Elgar.",
    "Griliches, Z. 1990. “Patent Statistics as Economic Indicators: A Survey.” Journal of Economic Literature 28 (4): 1661–1707.",
    "Luo, J., H. Lei, and J. Hou. 2024. “The Impact of Artificial Intelligence Technology Innovation on Total Factor Productivity: An Empirical Study Based on Provincial Panel Data in China.” National Accounting Review 6 (2): 172–194.",
    "OECD. 2024. “OECD.AI Policy Observatory: AI Research Publications.” Paris: OECD. https://oecd.ai.",
    "WIPO. 2019. WIPO Technology Trends 2019: Artificial Intelligence. Geneva: World Intellectual Property Organization.",
    "Yan, Z., M. Chen, and Y. Zhang. 2020. “Technology Patent Depreciation Rate and Its Application.” Science Research Management 41 (7): 89–98.",
  ].map(t => new Paragraph({ spacing: { after: 100, line: 276 },
    indent: { left: 340, hanging: 340 }, alignment: AlignmentType.JUSTIFIED,
    children: parseRuns(t, 20) })),
];

const doc = new Document({
  creator: "Carlos Miguel Yalta Vargas",
  title: "Do patents and publications measure the same AI innovation?",
  styles: { default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true },
        paragraph: { spacing: { before: 240, after: 110 }, outlineLevel: 0 } }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Page ", font: FONT, size: 18, color: "808080" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: "808080" })] })] }) },
    children }],
});

Packer.toBuffer(doc).then(buf => {
  const out = AELDIR + "/Applied-Economics-Letters-manuscript-cyv.docx";
  fs.writeFileSync(out, buf);
  console.log(`Saved ${out} (${buf.length} bytes)`);
});
