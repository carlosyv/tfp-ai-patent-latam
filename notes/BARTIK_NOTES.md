# Macro Bartik IV — implementation notes (2026-07-14)

`analysis/bartik_iv.py` implements §4.7 with the in-repo OECD.AI field-level publications
(5 fields, 2016–2024): shares = 2016–17 country field composition; shifts = ln global
ex-LatAm field publications; Z = share-weighted shifts.

## Verdict: transparently WEAK with available field granularity
- First-stage F ≈ 2.3 (Panel B, LN_AI_pub) and ≈ 2.4 (Panel A 2016–24 subwindow, LN_AI)
  — far below conventional thresholds. Do NOT lean on these IV estimates.
- Cause (diagnosed): NOT pure share homogeneity (cross-country SD of CV/Robotics
  shares is 0.22/0.27). Two compounding problems instead: (i) base-period shares are
  NOISY for small countries (tiny 2016-17 publication counts -> attenuation), and
  (ii) the two dominant fields (CV 0.39, Robotics 0.51 mean shares) have highly
  correlated global trends, so after year FE the shifts collapse toward a single
  common factor with little differential bite. Coarse 5-field granularity underlies
  both.
- Rotemberg-approx weights: Computer Vision 0.65, Robotics 0.20, NLP 0.09 —
  identification would hinge almost entirely on CV trends.
- IV point estimates (for the record, wide CIs): H1 null under IV on both panels;
  H3/H4 interaction IVs null.

## Dissertation treatment (recommended)
Report the Bartik attempt WITH diagnostics in the identification section: committee
asked for shift-share; we implement it, show the first stage, and explain why the
5-field publications version is under-identified. Operative evidence remains FE-DK +
lagged-IV/2SLS + system GMM with conditional-association language. Fix path (queued):
WIPO patents by 35-technology-field × origin × year (free WIPO statistics pull) for
finer, patent-based shares over a genuinely predetermined 2000–2004 base period.

Outputs: output/results/bartik_iv_results.csv, rotemberg_weights.csv.

# Bartik v2 — WIPO 35-field version (2026-07-19): IDENTIFICATION ACHIEVED

`analysis/bartik_iv_v2.py` + `data/wipo_field/` (WIPO bulk "patent indicators" file:
publications by technology field x origin x year, 2000-2022, free download).
shares = country field composition 2000-2004 (genuinely predetermined);
shifts = ln global ex-LatAm publications by field-year; Panel A 2000-2022.

- **FIRST-STAGE F = 23.5** (vs 2.3 in the 5-field publications v1) — strong.
- **IV H1: b = -0.029 (t = -1.06) vs FE-OLS -0.020 (t = -1.43) — the unconditional
  null SURVIVES under strong identification.** This is the headline IV result for the
  dissertation: not "no instrument," but "instrumented estimate confirms the null."
- IV x RuleOfLaw: AIxRL = -0.024 (t=-1.25) — consistent with the Solow-level
  heterogeneity (see PERIOD_HETEROGENEITY_NOTES.md). IV x Broadband: NOT identified
  (ZxM first stage too weak; SEs explode) — report as such, rely on OLS-FE for H4.
- Rotemberg-approx weights DIVERSIFIED: top field Medical technology 0.145, then
  consumer goods 0.127, engines 0.069... — no single-field dominance (v1 had CV=0.65).
- Documented deviation from §4.7: all 35 WIPO fields, not only G06N-adjacent —
  relevance runs through computer/digital-field specialization; state in text.
- Sample truncates at 2022 (WIPO file vintage); note in table footnote.
