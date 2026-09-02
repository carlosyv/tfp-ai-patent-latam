# AI-capability composite index (§5.6) — build + robustness notes (2026-07-14)

`analysis/composite_index.py`. Components (z-scores, equal weights, 2017–24 sample): ln AI patent
stock pc (LN_AI) + ln OECD.AI publications + AI-strategy adoption indicator (dates per
opening report §1.1.2; Mexico=0 through 2024, strategy remained draft) + digital
infrastructure (mean z of WDI broadband+internet — documented substitute for ITU IDI,
discontinued 2018–22). Oxford Government AI Readiness = optional 5th component,
auto-included when `data/oxford_ai_readiness.csv` exists (form-gated download;
grab "Index Data" for 2019–2025 editions at oxfordinsights.com → save as
CountryName,Year,score).

Coherence (5-component build, Oxford/GAIRI included — re-run 2026-07-29): PCA-1 explains
46.1% with balanced positive loadings (c_pat 0.428, c_pub 0.453, c_str 0.395, c_inf 0.392,
c_ox 0.550) — components measure one underlying construct. [Superseded: the 4-component
build without Oxford gave PCA-1 = 48%.]

## Robustness verdict (Panel A, 2017–2024, n=72)
- H1 with composite treatment: b=+0.010 (t=0.87) vs patents-only b=0.004 (t=0.53) —
  [5-component build, re-run 2026-07-29; the 4-component build gave b=-0.002 (t=-0.20).
  Sign flips, magnitude trivial, conclusion unchanged.]
  **null unconditional baseline is ROBUST to the multi-dimensional AI measure.**
  Directly answers the "patents understate AI capability" critique (P2): measuring AI
  capability more broadly does not resurrect an unconditional effect.
- H3/H4 interactions ≈ 0 in this short subwindow for BOTH treatments — consistent with
  the conditional effects being a full-window (2000–2024) result; the 8-year window
  lacks power (as anticipated in §6.6-style reasoning). State this explicitly in the
  dissertation: composite robustness targets H1; conditional results are identified on
  the long panel.
Outputs: output/results/composite_index.csv, composite_robustness_results.csv.
