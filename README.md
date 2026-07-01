# The Impact of AI Adoption on Total Factor Productivity in Latin America

**Replication Package**

> Carlos Yalta Vargas
> Shanghai University / PhD in Industrial Economics program
> cyaltav@outlook.com
> Version: March 2026

---

## Overview

This repository contains the full replication package for the paper *"The Impact of AI Adoption on Total Factor Productivity (TFP) in Latin America."* The study examines whether AI-related patent activity — used as a revealed indicator of AI adoption — is associated with Total Factor Productivity growth across seven Latin American countries over the period 1992–2024.

Two TFP measures are constructed and compared:

1. **Solow Residual** — parametric, growth-accounting approach with labor-augmenting human capital (α = 0.35; PWT 10.01 human capital index)
2. **DEA-Malmquist Index** — non-parametric, output-oriented Variable Returns to Scale (VRS) frontier approach

Five hypotheses are tested using panel data methods, including Common Correlated Effects estimators (CCEP, CCEFE) to address cross-sectional dependence.

All econometric estimators are implemented from scratch in NumPy. No external econometrics library is required.

---

## Repository Structure

```
tfp-ai-patent-latam/
├── README.md                                   ← This file
├── requirements.txt                            ← Python dependencies (3 packages)
├── .gitignore
│
├── run_dissertation_v4_noimput_pipeline.py     ← MAIN PIPELINE (canonical)
│
├── data/                                       ← All input data sources
│   ├── wb_data_export.csv                      ← World Development Indicators (WDI)
│   ├── pwt-data-human-capital-026-03-22T15-56_export.csv  ← Penn World Table 10.01
│   ├── EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv.gz         ← ILOSTAT employment
│   ├── ai-search-wipo-results-spanish-v2.xlsx              ← WIPO AI patents (Spanish)
│   └── ai-search-wipo-results-br-portuguese-v2.xlsx        ← WIPO AI patents (Portuguese)
│
├── output/
│   └── results/
│       └── benchmark_dissertation_v4_noimput/  ← Pre-computed results (canonical)
│           ├── regression_results.json          ← Full structured results (all hypotheses)
│           ├── regression_comparison.csv        ← Publication-ready coefficient table
│           ├── descriptive_statistics.csv
│           ├── correlation_matrix.csv
│           ├── tab_solow_full.tex               ← LaTeX table: Solow TFP, full controls
│           ├── tab_solow_pars.tex               ← LaTeX table: Solow TFP, parsimonious
│           ├── tab_malmquist_full.tex           ← LaTeX table: Malmquist, full controls
│           └── tab_malmquist_pars.tex           ← LaTeX table: Malmquist, parsimonious
│
└── deprecated/                                 ← Prior model specifications (v3)
    ├── README.md                               ← Explanation of methodological evolution
    ├── run_dissertation_v3_noimput_pipeline.py
    └── run_dissertation_v3_pipeline.py
```

---

## Data Sources

| File | Source | Variables | Coverage |
|---|---|---|---|
| `wb_data_export.csv` | World Bank WDI | GDP, GFCF, trade, FDI, govt consumption, urban pop., internet users, mobile cellular, fixed broadband, private credit, Rule of Law, tertiary enrollment | 7 countries, 1992–2024 |
| `pwt-data-human-capital-*.csv` | Penn World Table 10.01 | Human capital index (hc) | 7 countries, 1950–2019 (extrapolated to 2024) |
| `EMP_TEMP_SEX_AGE_NB_A-*.csv.gz` | ILOSTAT | Total employment (EMP_TEMP), all sexes, all ages | 7 countries, 1992–2024 |
| `ai-search-wipo-results-spanish-v2.xlsx` | WIPO IP Portal | AI-related patents — ARG, CHL, COL, MEX, PER | Up to 2024 |
| `ai-search-wipo-results-br-portuguese-v2.xlsx` | WIPO IP Portal | AI-related patents — BRA (Portuguese) | Up to 2024 |

**Countries**: Argentina (ARG), Brazil (BRA), Chile (CHL), Colombia (COL), Costa Rica (CRI), Mexico (MEX), Peru (PER)

**Sample period**: 1992–2024 (up to 231 country-year observations; unbalanced due to data availability)

### AI Patent Classification

AI-related patents were identified from WIPO using a keyword search strategy aligned with OECD/WIPO guidelines for AI patent identification, covering machine learning, neural networks, computer vision, natural language processing, robotics, and expert systems. Patent counts are aggregated to the country-year level. Separate searches were conducted in Spanish and Portuguese to maximize coverage for the LAC region.

### Data Licensing & Attribution

The input data files are redistributed here to make the results reproducible. Each remains subject to the terms of its original provider, and users should cite the primary sources rather than this repository:

- **World Bank — World Development Indicators (WDI):** Licensed under [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses). Attribution: The World Bank, World Development Indicators.
- **Penn World Table 10.01:** Feenstra, Inklaar & Timmer (2015), "The Next Generation of the Penn World Table," *American Economic Review*, 105(10), 3150–3182. Available at [www.ggdc.net/pwt](https://www.rug.nl/ggdc/productivity/pwt/); licensed under CC BY 4.0.
- **ILOSTAT (International Labour Organization):** Employment statistics, redistributed under the ILO [terms of use](https://ilostat.ilo.org/about/copyright/) (CC BY 4.0). Attribution: ILOSTAT.
- **WIPO IP Portal (PATENTSCOPE):** AI-patent search exports are derived from the [WIPO IP Portal](https://patentscope.wipo.int/), subject to WIPO's [terms of use](https://www.wipo.int/tools/en/disclaim.html). The files here are aggregated, keyword-filtered search results prepared by the author.

---

## Methodology

### TFP Computation

**Solow Residual:**

```
TFP_it = GDP_it / (K_it^α × (L_it × HC_it)^(1−α))
```

where α = 0.35 (capital share), K is the capital stock estimated via the Perpetual Inventory Method (PIM) using gross fixed capital formation (GFCF) from WDI, L is total employment from ILOSTAT, and HC is the Penn World Table 10.01 human capital index.

**DEA-Malmquist Index:**

The Malmquist total factor productivity change index is computed using output-oriented Variable Returns to Scale (VRS) DEA:

```
M_it = sqrt[ (D^t+1(x_t+1, y_t+1) / D^t+1(x_t, y_t)) × (D^t(x_t+1, y_t+1) / D^t(x_t, y_t)) ]
```

M > 1 indicates productivity improvement; M < 1 indicates decline. The index is decomposed into efficiency change (catching-up) and technical change (frontier shift).

### Panel Estimators

| Estimator | Abbreviation | Notes |
|---|---|---|
| Pooled OLS | OLS | Cluster-robust SE by country |
| Fixed Effects (Within) | FE | Cluster-robust SE; time-demeaned |
| Random Effects (GLS) | RE | Mundlak variance components |
| Common Correlated Effects Pooled | CCEP | Pesaran (2006); cross-mean augmented |
| Common Correlated Effects FE | CCEFE | Pesaran (2006); FE variant |

CCEP/CCEFE are preferred specifications due to evidence of cross-sectional dependence (Pesaran CD test reported for all models).

### Hypotheses

| Hypothesis | Description |
|---|---|
| H1 | AI patent activity is positively associated with TFP growth (benchmark) |
| H2 | The effect of AI patents on TFP is mediated by human capital (Baron & Kenny 1986) |
| H3 | The AI–TFP relationship is moderated by institutional quality (Rule of Law, RL.EST) |
| H4 | The AI–TFP relationship is moderated by mobile cellular penetration (primary channel) |
| H4r | Robustness check for H4 using fixed broadband penetration |
| H5 | The AI–TFP relationship is heterogeneous across the TFP distribution (panel quantile regression, τ = 0.10, 0.25, 0.50, 0.75, 0.90) |

### Imputation Strategy

The canonical pipeline (`run_dissertation_v4_noimput_pipeline.py`) applies **no imputation** to any variable:

- ILOSTAT labor: raw observed values only; missing observations remain NaN
- WDI control variables: raw values only
- AI patent counts: unobserved country-years remain NaN (no zero-fill)
- PWT HC extrapolation to 2024 and PIM capital stock gap-skipping are retained

This is a conservative approach that preserves the information structure of the raw data and avoids imputation-induced attenuation bias.

---

## Replication Instructions

### 1. Requirements

- Python 3.10 or later
- Three external packages: `numpy`, `pandas`, `openpyxl`

```bash
pip install -r requirements.txt
```

### 2. Clone the Repository

```bash
git clone https://github.com/carlosyv/tfp-ai-patent-latam.git
cd tfp-ai-patent-latam
```

### 3. Decompress the ILOSTAT File

The ILOSTAT employment data is stored in compressed format to comply with GitHub file size limits. Decompress it before running the pipeline:

```bash
cd data/
gunzip -k EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv.gz
```

The `-k` flag keeps the original `.gz` file. The pipeline expects both the `.gz` and uncompressed `.csv` to be present in `data/`.

### 4. Run the Main Pipeline

From the repository root:

```bash
python run_dissertation_v4_noimput_pipeline.py
```

**Expected runtime**: approximately 5–15 minutes depending on hardware (DEA-Malmquist computation is the bottleneck).

**Output**: Results are written to `output/results/benchmark_dissertation_v4_noimput/`. Pre-computed results for the canonical specification are already included in this directory for immediate inspection without re-running.

### 5. Verify Against Pre-Computed Results

The `output/results/benchmark_dissertation_v4_noimput/` directory contains the pre-computed results included in the paper. Running the pipeline will overwrite these files with freshly computed results. Numerical equivalence (within floating-point tolerance) confirms successful replication.

---

## Output Files

| File | Description |
|---|---|
| `regression_results.json` | Complete structured results for all hypotheses (H1–H5), all estimators, all specifications. Machine-readable format for downstream analysis. |
| `regression_comparison.csv` | Publication-ready coefficient comparison table with standard errors, t-statistics, p-values, and significance stars. |
| `descriptive_statistics.csv` | Summary statistics (N, mean, SD, min, max) for all variables in the final estimation sample. |
| `correlation_matrix.csv` | Pairwise Pearson correlation matrix for all regression variables. |
| `tab_solow_full.tex` | LaTeX regression table — Solow TFP, full control specification. Ready for insertion into a LaTeX manuscript. |
| `tab_solow_pars.tex` | LaTeX regression table — Solow TFP, parsimonious specification. |
| `tab_malmquist_full.tex` | LaTeX regression table — Malmquist TFP, full control specification. |
| `tab_malmquist_pars.tex` | LaTeX regression table — Malmquist TFP, parsimonious specification. |

---

## Additional Scripts

The following auxiliary scripts are present in the repository root but are not part of the core replication pipeline:

- **`run_dissertation_v4_pipeline.py`** — Imputation variant of v4 (uses linear interpolation for missing values). Used to assess sensitivity of results to the no-imputation assumption.
- **`build_comparison_v4_table.py`** — Generates a side-by-side Excel workbook comparing imputed vs. no-imputation results across all hypotheses.
- **`build_comparison_table.py`** — Generates a comparison table across v3 and v4 specifications.
- **`h3_institutional_comparison.py`** — Robustness script for H3: compares Rule of Law (RL.EST), Regulatory Quality (RQ.EST), and Government Effectiveness (GE.EST) as institutional moderators.

Prior pipeline specifications (v3) are archived in the `deprecated/` directory with a methodological explanation of the model evolution.

---

## Notes on Reproducibility

**Cross-sectional dependence**: Pesaran CD test statistics are reported for all models. CCEP and CCEFE are the preferred estimators under cross-sectional dependence. OLS and FE results are included for comparability with prior literature.

**Endogeneity**: Patent-TFP reverse causality is addressed via lagged patent specifications (Lag-1 and Lag-2 robustness checks included in H1). Cumulative patent stock specifications are also tested.

**Data vintage**: All data were downloaded in March 2026. WDI series may be revised by the World Bank; results may differ marginally if the pipeline is run against updated WDI data.

**Random seed**: The DEA-Malmquist computation is deterministic (no stochastic components). Results should be numerically identical across runs given identical input data.

---

## Citation

If you use this code or data in your research, please cite:

> Yalta, C. (2026). *The Impact of AI Adoption on Total Factor Productivity in Latin America*. [Journal name, volume, pages]. DOI: [to be assigned]

---

## License

The **code** in this repository is released under the [MIT License](LICENSE).

The **input data** files in `data/` are redistributed under the licenses of their
original providers (World Bank WDI, Penn World Table, ILOSTAT, and WIPO IP Portal) —
see [Data Licensing & Attribution](#data-licensing--attribution) above. Please cite
the primary data sources, not this repository, when reusing the underlying data.

---

## Contact

For questions about the replication package, please open an issue on this repository or contact the author at cyaltav@outlook.com.
