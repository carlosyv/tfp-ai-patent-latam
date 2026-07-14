# GTFP cross-region pipeline (Paper 2 — Journal of Cleaner Production)

**Paper:** "Does artificial intelligence research improve green total factor productivity?
Cross-regional evidence from 40 emerging economies in Latin America, Asia, and Africa"
(scaffold: `tfp-ai/publications/JCP/paper2_JCP_scaffold.docx`)

## Why this is NOT `pipeline_v6`

The `pipeline_vN` sequence (v3 → v4 → v5, see `archive/` and `pipeline_v5/`) tracks
successive versions of the **dissertation / Paper 1** analysis — same research design,
same LatAm sample, refined implementation. This folder is a **different paper** with a
different sample (40 countries, 3 regions), a different dependent variable (green TFP),
and a different AI measure (publications only). Naming it v6 would wrongly imply it
supersedes v5.

**Repo convention going forward:**

| Folder | Paper | Versioning |
|---|---|---|
| `pipeline_v5/` | Dissertation + EAP Paper 1 (LatAm, TFP) | frozen; dissertation series keeps vN |
| `letters/ael_measurement/` | AEL measurement letter | single script |
| `gtfp_pipeline/` | JCP Paper 2 (cross-region, green TFP) | `run_gtfp_v1.py`, v2… internal to this folder |

One folder per paper; versions live inside the folder. The dissertation keeps its
historical vN naming untouched.

## Design summary (locked decisions)

- **Sample: N = 40**, 2016–2023 (T = 8). 17 LatAm + 11 Asia + 12 Africa.
  **Nigeria dropped** (constant-2015-USD national accounts unavailable in WDI after the
  GDP rebase; documented in the paper's data section).
- **GTFP:** Malmquist–Luenberger index, directional distance function, inputs (K, L·h),
  good output GDP (NY.GDP.MKTP.KD), bad output CO₂ (EN.GHG.CO2.MT.CE.AR5).
  Conventional CRS Malmquist + Solow residual (α = 0.35) computed for the
  environmental-margin contrast.
- **AI measure:** ln(1 + OECD.AI publications per million population), field = "All".
- **Estimators:** FE-DK workhorse → CCEP/CCEMG → Canay quantile → moderation
  (Rule of Law, broadband, mobile, renewables) → robustness (lags, 2SLS predetermined,
  collapsed-instrument system GMM — feasible at N = 40).

## Data notes (see `config.py` for the full indicator map)

- **Rule of Law coalesce:** `RL.EST` covers the 17 LatAm countries (original pull);
  `GOV_WGI_RL.EST` covers the 23 Asia/Africa countries (2026-07-14 pull). Same WGI
  estimate series, same scale (−2.5 to +2.5) — coalesce into one `RULE_OF_LAW` variable.
- **China capital:** `NE.GDI.FTOT.KD` (GFCF) unavailable for CHN; use
  `NE.GDI.TOTL.KD` (gross capital formation) as the PIM input for CHN with a data note.
- **Renewables:** `EG.FEC.RNEW.ZS` ends 2022 → enter lagged, or truncate that
  moderator specification to 2016–2022.
- **ILOSTAT:** use the 2026-07-14 file (`data/ilostat/EMP_TEMP_..._20260714T0915.csv.gz`);
  the March file stays reserved for `pipeline_v5` reproducibility.
- **PWT HC:** trend-extend post-2019 (same rule as v5); flag in limitations.
- **PIM initialisation:** 2008 (8 pre-sample years), δ_K = 0.05, K₀ = I₀/(g+δ).

## Status

- [x] Data audited complete for N = 40 design (2026-07-14)
- [x] `config.py` — sample, regions, parameters, indicator map
- [ ] `run_gtfp_v1.py` — data build + ML-GTFP module + estimation battery
- [ ] Results → fill `paper2_JCP_scaffold.docx` pending blocks
