# AEL measurement letter — replication package

**Paper:** "Do patents and publications measure the same AI innovation? Evidence from Latin American panels"
(target: *Applied Economics Letters*; draft in `tfp-ai/publications/AEL/AEL_letter_draft.docx`)

**Authors:** Carlos Miguel Yalta Vargas (School of Economics, Shanghai University);
Lv KangJuan (SILC Business School, Shanghai University, corresponding).

## Finding in one line

The two standard national AI-innovation proxies — WIPO keyword-based AI patents and OECD.AI
scientific publications — agree almost perfectly **between** countries (r = 0.91) but share
essentially no **within**-country variation once year effects are removed (r = 0.07, p = 0.55).
Fixed-effects panel estimates of AI's economic effects are therefore measure-specific;
cross-sectional rankings are not.

## Contents

| File | Purpose |
|---|---|
| `ael_analysis.py` | Computes every statistic in the letter (Table 1, Figure 1) |
| `output/ael_results.json` | Machine-readable results (generated) |
| `output/ael_figure1.png` | Two-panel figure, 300 dpi (generated) |

## Data inputs

All inputs live in `../../data/` and are shared with `pipeline_v5` (no duplication):

| File | Source | Role |
|---|---|---|
| `ai-search-wipo-results-spanish-v2.xlsx` | WIPO PATENTSCOPE keyword search (Spanish, WIPO 2019 keyword list) | Patent counts |
| `ai-search-wipo-results-br-portuguese-v2.xlsx` | WIPO PATENTSCOPE keyword search (Portuguese, Brazil) | Patent counts |
| `cat-ai-patents-country-data/publications_yearly_articles.csv` | OECD.AI Policy Observatory, AI research publications, field = "All" | Publication counts |

## Method summary

- Patent stock: perpetual inventory, `S_t = P_t + (1 − 0.36)·S_{t−1}` (Yan, Chen & Zhang 2020),
  identical to `pipeline_v5`.
- Sample: 9 countries (ARG BRA CHL COL CRI DOM MEX PER URY) × 2016–2024 = 81 obs.
  2025+ excluded (flagged incomplete in the OECD source).
- Both measures transformed ln(x + 1).
- Statistics: between-country Pearson/Spearman on country means; pooled country-demeaned r;
  two-way (country + year) demeaned r — the fixed-effects-relevant statistic; Δln growth-rate r;
  per-country correlations; between/within variance decomposition; year-by-year rank correlations.

## Reproduce

```bash
cd letters/ael_measurement
python3 ael_analysis.py        # writes output/ael_results.json + output/ael_figure1.png
```

Dependencies: `pandas numpy scipy matplotlib openpyxl` (see repo `requirements.txt`).

## Key numbers (for verification against the letter)

| Statistic | Value |
|---|---|
| Between-country r (means, logs) | 0.907 (p = 0.001) |
| Between-country Spearman ρ | 0.867 (p = 0.003) |
| Pooled within-country r | 0.487 |
| **Two-way demeaned r** | **0.068 (p = 0.548)** |
| Growth-rate r (Δln) | 0.108 (p = 0.365) |
| Between-country variance share | patents 0.915 · publications 0.963 |
| Year-by-year rank ρ range | 0.78–0.92 |

## Publication workflow

This folder stays in the private working repo. At acceptance:
1. Freeze with `git tag ael-letter-accepted-<date>`.
2. Copy this folder + a data-access note into a fresh public repository / Zenodo deposit
   (raw WIPO exports may need to be replaced by extraction instructions, per WIPO terms).
3. Cite the Zenodo DOI in the published data-availability statement.
