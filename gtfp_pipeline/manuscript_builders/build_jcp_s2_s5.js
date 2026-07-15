// JCP manuscript — §2 (Literature review and hypotheses) and §5 (Discussion) drop-ins.
// §5 numbers read from fill_data.json. Citations restricted to verified literature;
// recent-JCP-exemplar slots marked as placeholders.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  HeadingLevel, Header, Footer, PageNumber, ShadingType,
} = require("docx");

const F = JSON.parse(fs.readFileSync(
  "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/fill_data.json", "utf8"));
const B = F.benchmark, RY = F.region_year_fe, H3 = F.h3_paired,
      MOD = F.moderation, REG = F.regional_interactions, D = F.diag, S = F.sample;
const lag = {};
for (const r of F.lag_profile) if (r.sample === "common") lag[`${r.dep}_${r.lag}`] = r;

const r3 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(3);
const r4 = (x) => (x >= 0 ? "+" : "") + Number(x).toFixed(4);
const st = (p) => (p < 0.01 ? "***" : p < 0.05 ? "**" : p < 0.10 ? "*" : "");

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
  spacing: { after: 130, line: 280 }, alignment: AlignmentType.JUSTIFIED,
  indent: o.noIndent ? undefined : { firstLine: 340 }, children: parseRuns(t) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 280, after: 130 },
  children: [new TextRun({ text: t, font: FONT, size: 24, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { before: 220, after: 100 },
  children: [new TextRun({ text: t, font: FONT, size: 21, bold: true, italics: true })] });
const note = (t) => new Paragraph({ spacing: { after: 110 },
  shading: { fill: "FFF2CC", type: ShadingType.CLEAR },
  children: [new TextRun({ text: t, font: FONT, size: 18, italics: true, color: "B45309" })] });

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    shading: { fill: "DEEBF7", type: ShadingType.CLEAR },
    children: [new TextRun({
      text: "DROP-IN SECTIONS §2 and §5 — JCP manuscript · §2 ≈890 words, §5 ≈760 words · [JCP-REF] slots need 3–5 recent green-TFP papers from this journal · §5 numbers from fill_data.json",
      font: FONT, size: 17, bold: true, color: "1F4E78" })] }),

  // ═══════════ SECTION 2 ═══════════
  H1("2. Literature review and hypotheses"),

  H2("2.1 AI and productivity"),
  P("The economic case for expecting AI to raise productivity rests on its characterisation as a general purpose technology: pervasive across sectors, improving over time, and spawning complementary innovation (Bresnahan and Trajtenberg, 1995). Yet the same literature explains why measured productivity may respond slowly or even negatively in the medium run. Brynjolfsson, Rock and Syverson (2021) formalise the productivity J-curve: because AI requires complementary intangible investments — organisational redesign, skills, data infrastructure — measured productivity understates true output early in the diffusion process, and contemporaneous correlations between AI activity and productivity can be zero or negative even when the long-run effect is positive. Empirically, positive associations have been documented mainly in advanced economies: Acemoglu, Autor, Hazell and Restrepo (2022) find modest gains concentrated in large U.S. firms, and Babina, Fedyk, He and Hodson (2024) link firm AI investment to growth through product innovation. At the technology-assessment level, Goldfarb, Taska and Teodoridis (2023) conclude that machine learning behaves like a general purpose technology but that its measurable aggregate effects remain smaller than those of earlier GPTs at comparable stages.", { noIndent: true }),
  P("Evidence for developing economies is thin and concentrated on China. Luo, Lei and Hou (2024) document positive effects of AI patent activity on the total factor productivity of Chinese provinces. Whether such findings travel to regions with smaller AI research bases, weaker complementary infrastructure, and more emissions-intensive growth is unknown — and the productivity concept in this literature is almost always conventional TFP, which is silent on whether AI-associated growth is cleaner or merely faster. In the knowledge-production tradition that underpins these studies (Griliches, 1979, 1990), research output measures — patents or publications — proxy the knowledge input into production; scientific publications have the practical advantage of consistent bibliometric observation across countries with very different patenting propensities."),

  H2("2.2 Green total factor productivity"),
  P("Conventional productivity indices credit output expansion regardless of its emissions content. The directional distance function of Chung, Färe and Grosskopf (1997) extends the production frontier to joint production of desirable and undesirable outputs under weak disposability, and the associated Malmquist–Luenberger (ML) index measures productivity change that simultaneously credits output expansion and emissions contraction (see also Färe, Grosskopf and Pasurka, 2007). The resulting green TFP concept has become the workhorse of the cleaner-production literature on emerging economies, with a large body of applications to Chinese provinces and cities examining drivers ranging from environmental regulation to the digital economy [JCP-REF: insert 3–5 recent green-TFP papers from this journal]. Two gaps stand out in this literature. First, applications are overwhelmingly single-country; cross-regional evidence spanning Latin America, Asia, and Africa is, to our knowledge, absent. Second, AI-specific innovation has not been examined as a driver of green TFP, despite the prominence of AI in national sustainable-development strategies.", { noIndent: true }),

  H2("2.3 Absorptive capacity and conditional effects"),
  P("Whether knowledge inputs translate into productivity depends on complementary capabilities. Cohen and Levinthal (1990) formalise absorptive capacity at the organisational level; its macro analogue holds that the productivity return to new technology is increasing in institutional quality, infrastructure, and skills. For digital technologies in developing economies this conditionality is well documented (World Bank, 2016; Niebel, 2018), and for Latin America specifically, Cimoli, Hofman and Mulder (2010) show that ICT-driven productivity gains required complementary investment in education and institutions. Structural composition matters as well: where growth is concentrated in emissions-intensive industrialisation, the same knowledge input may coincide with deteriorating environmental efficiency (McMillan and Rodrik, 2011). Global assessments of AI and the Sustainable Development Goals reach a parallel conclusion: AI can enable most environmental targets, but realising the benefits depends on governance and infrastructure preconditions (Vinuesa et al., 2020).", { noIndent: true }),
  P("From these literatures we derive three hypotheses. **H1:** AI research output is positively associated with green total factor productivity. **H2:** the association is stronger in economies with stronger institutions and digital infrastructure. **H3:** the AI–GTFP association differs from the AI–conventional-TFP association — that is, an environmental margin exists. H1 reflects the optimistic GPT prior embedded in national AI strategies; the J-curve and absorptive-capacity literatures supply the reasons it may fail in the short run, which our lag-profile and moderation analyses are designed to detect."),

  // ═══════════ SECTION 5 ═══════════
  H1("5. Discussion"),

  H2("5.1 No short-run green dividend, and no environmental margin"),
  P(`Taken together, the results give a disciplined answer to the question in the title: AI research capacity is not associated with green-productivity improvement in the short run. The contemporaneous benchmark is null (β = ${r3(B.GTFP_ML.b)}, p = ${B.GTFP_ML.p.toFixed(2)}), the region-by-year specification favoured by the dependence diagnostics is negative and marginally significant (β = ${r3(RY.GTFP_ML.b)}, p = ${RY.GTFP_ML.p.toFixed(2)}), and the association deepens to β = ${r3(lag["GTFP_ML_L2"].b)} (p = ${lag["GTFP_ML_L2"].p.toFixed(2)}) two years after the AI measure, on a lag-invariant sample. Equally important is what the paired test shows: the green and conventional indices respond to AI almost identically (Δβ = ${r3(H3.L1.b)} at one year, ${r3(H3.L2.b)} at two, both insignificant; index correlation ${D.wedge_overall.corr_indices}). H3 is not supported. AI research is thus not yet associated with *cleaner* growth specifically — whatever relationship exists operates through the input–output core of productivity, not the emissions margin. For the cleaner-production agenda this is a cautionary result: research capacity alone does not shift the emissions efficiency of growth within the horizon we observe.`, { noIndent: true }),

  H2("5.2 Delayed adjustment, not instant payoff"),
  P(`The monotone deepening of the negative association across the lag profile (${r4(lag["GTFP_ML_L0"].b)} → ${r4(lag["GTFP_ML_L1"].b)} → ${r4(lag["GTFP_ML_L2"].b)}${st(lag["GTFP_ML_L2"].p)}) is the pattern the productivity J-curve predicts during the absorption phase of a general purpose technology: complementary investments are being made, resources are reallocated, and measured productivity temporarily falls before the payoff arrives (Brynjolfsson, Rock and Syverson, 2021). With eight years of data we can observe the descending arm of such a curve but not its recovery; the interpretation therefore remains conditional, and the alternative — a persistent misalignment between research output and productive application in the Global South — cannot be excluded. Distinguishing the two is the single most valuable extension as longer panels accumulate.`),

  H2("5.3 Regional concentration and its reading"),
  P(`The pooled estimates conceal sharp regional structure: interactions are significantly negative for Asia (β = ${r3(REG.MALM_CRS["AIxASIA_b"])}) and Africa (β = ${r3(REG.MALM_CRS["AIxAFRICA_b"])}) relative to Latin America, and excluding Latin America turns the pooled GTFP association significantly negative (β = ${r3(D.drop_LATAM.GTFP_ML.b)}). A naïve absorptive-capacity reading — weaker capabilities, worse outcomes — fits the Africa result but sits awkwardly with Asia, where AI research intensity is highest in the sample. A more plausible reading is compositional: the fastest expansions of AI research output in Asia coincide with phases of emissions-intensive industrial growth, so within-country increases in research output co-move with deteriorating frontier efficiency. The moderation results support the capability view at the margin: mobile connectivity significantly softens the GTFP association (interaction ${r4(MOD.GTFP_ML.MOBILE.b)}${st(MOD.GTFP_ML.MOBILE.p)}), and Rule of Law moderates the conventional index (${r4(MOD.MALM_CRS.RULE_OF_LAW.b)}${st(MOD.MALM_CRS.RULE_OF_LAW.p)}). We caution that the AI measure is research output, not deployment; region-specific gaps between the two are themselves a candidate explanation and an agenda for measurement work.`, { noIndent: true }),

  H2("5.4 Policy implications"),
  P("Three implications follow for AI-for-sustainability strategies. First, sequencing: the moderation evidence indicates that digital connectivity and institutional quality condition whatever productivity return AI research delivers, so strategies that fund research capacity ahead of connectivity and governance foundations are unlikely to show measurable green-productivity results within a policy cycle. Second, differentiation: the regional heterogeneity argues against uniform regional templates — the binding margin in one region (connectivity in much of Africa) differs from another (managing the emissions intensity of industrial expansion in parts of Asia). Third, expectation management aligned with SDG 8.2 and SDG 9: the absence of an environmental margin means AI research investment should be justified on innovation-system grounds, with green-productivity claims reserved until deployment-stage evidence exists."),

  H2("5.5 Limitations"),
  P(`Five limitations bound the conclusions. The design is associational; country and region-by-year fixed effects with lagged regressors do not identify causal effects. Publications measure research capacity, not deployment, and the wedge between the two plausibly varies by region. The panel is short (T = 8), constrained by the OECD publication series and the CO₂ data lag. The ML index is infeasible for the sample's most emissions-intensive economies (${Object.keys(D.ml_infeasible_by_country).join(", ")}), which are effectively absent from the GTFP regressions. Finally, system-GMM estimates are deferred to the revision stage; the lag-profile and region-by-year results should be read with that pending check in mind.`, { noIndent: true }),

  note("Reference additions needed for these sections beyond the current list: Färe, R., Grosskopf, S., Pasurka, C.A. (2007). Environmental production functions and environmental directional distance functions. Energy 32(7), 1055–1066. Vinuesa, R., et al. (2020). The role of artificial intelligence in achieving the Sustainable Development Goals. Nature Communications 11, 233. Plus the 3–5 [JCP-REF] green-TFP exemplars — select recent papers from the journal to signal scope fit; verify against the journal site."),
];

const doc = new Document({
  creator: "Claude",
  title: "JCP §2 and §5 drop-ins",
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
      children: [new TextRun({ text: "JCP draft · §2 Literature and §5 Discussion",
        font: FONT, size: 16, italics: true, color: "808080" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Page ", font: FONT, size: 16, color: "808080" }),
                 new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "808080" })] })] }) },
    children }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "/sessions/lucid-focused-bohr/mnt/tfp-ai/publications/JCP/paper2_JCP_sections2_5_draft.docx";
  fs.writeFileSync(out, buf);
  console.log(`Saved ${out} (${buf.length} bytes)`);
});
