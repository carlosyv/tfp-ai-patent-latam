# The Impact of AI Adoption on Total Factor Productivity in Latin America

**Replication Package**

> Carlos Yalta Vargas
> Shanghai University / PhD in Industrial Economics program
> cyaltav@outlook.com
> Version: v5 (2026)

---

## Overview

This repository contains the replication package for the paper *"The Impact of AI Adoption on Total Factor Productivity (TFP) in Latin America."* The study examines whether AI-related innovation — measured through revealed indicators of AI adoption — is associated with Total Factor Productivity growth across Latin American countries.

Two TFP measures are constructed and compared:

1. **Solow Residual** — parametric, growth-accounting approach with labor-augmenting human capital (α = 0.35; PWT 10.01 human capital index).
2. **DEA-Malmquist Index** — non-parametric, output-oriented DEA frontier (Färe et al. 1994), 2-input (capital and effective labor), Variable Returns to Scale (VRS) main specification with a Constant Returns to Scale (CRS) robustness variant.

The relationship is estimated with panel-data methods, including Common Correlated Effects estimators (CCEP, CCEFE) to address cross-sectional dependence. All panel estimators are implemented from scratch in NumPy; no specialized econometrics package (e.g., `statsmodels`, `linearmodels`) is used. `scipy` is used only for general numerical routines (normal/t distributions for p-values, and `linprog` for the DEA linear programs).

### Two analysis panels

| Panel | Script | AI measure | Countries | Period |
|---|---|---|---|---|
| **A** (main) | `pipeline_v5/run_pipeline_v5.py` | WIPO AI patents (per-capita patent stock) | 9 | 2000–2024 |
| **B** (robustness) | `pipeline_v5/run_pipeline_v5_panelB.py` | OECD.AI publications | 17 | 2016–2024 |

**Panel A countries (9):** Argentina (ARG), Brazil (BRA), Chile (CHL), Colombia (COL), Costa Rica (CRI), Dominican Republic (DOM), Mexico (MEX), Peru (PER), Uruguay (URY).

**Panel B countries (17):** Panel A plus Bolivia (BOL), Ecuador (ECU), El Salvador (SLV), Guatemala (GTM), Honduras (HND), Nicaragua (NIC), Panama (PAN), Paraguay (PRY).

---

## Repository Structure

```
tfp-ai-patent-latam/
├── README.md                                     ← This file
├── LICENSE                                       ← MIT (code); data keeps providers' licenses
├── requirements.txt                              ← Python dependencies
├── .gitignore
│
├── pipeline_v5/
│   ├── run_pipeline_v5.py                         ← MAIN PIPELINE (Panel A)
│   └── run_pipeline_v5_panelB.py                  ← Panel B robustness (OECD.AI publications)
│
├── data/                                          ← All input data sources
│   ├── wb_data_export.csv                         ← World Development Indicators (WDI)
│   ├── pwt-data-human-capital-026-03-22T15-56_export.csv  ← Penn World Table 10.01
│   ├── EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv.gz         ← ILOSTAT employment (read gzipped)
│   ├── ai-search-wipo-results-spanish-v2.xlsx             ← WIPO AI patents (Spanish-language offices)
│   ├── ai-search-wipo-results-br-portuguese-v2.xlsx       ← WIPO AI patents (Brazil, Portuguese)
│   └── cat-ai-patents-country-data/               ← OECD.AI Policy Observatory export
│       └── publications_yearly_articles.csv       ← AI publications (used by Panel B)
│
└── output/
    └── results/                                   ← Pipeline outputs (see "Output Files")
        ├── solow_tfp_dissertation_v5.csv
        ├── malmquist_dissertation_v5.csv          ← VRS (main)
        ├── malmquist_crs_dissertation_v5.csv      ← CRS (robustness)
        ├── merged_dissertation_v5.csv             ← Panel A estimation dataset
        ├── merged_panelB_v5.csv                   ← Panel B estimation dataset
        └── benchmark_dissertation_v5/            ← Publication-ready tables
            ├── regression_results.json            ← All benchmark results (structured)
            ├── regression_comparison.csv          ← AI coefficient across specs/estimators
            ├── regression_summary.txt             ← Human-readable summary
            ├── descriptive_statistics.csv
            ├── correlation_matrix.csv
            ├── tab_solow_full.tex / tab_solow_pars.tex        ← LaTeX (Solow)
            └── tab_malmquist_full.tex / tab_malmquist_pars.tex ← LaTeX (Malmquist)
```

---

## Data Sources

| File | Source | Variables | Coverage |
|---|---|---|---|
| `wb_data_export.csv` | World Bank WDI | GDP, GDP per capita, GFCF, trade, FDI, govt consumption, urban pop., internet/mobile/broadband, private credit, Rule of Law, population, services & industry value added | up to 17 countries, 1992–2024 |
| `pwt-data-human-capital-*.csv` | Penn World Table 10.01 | Human capital index (`hc`) | 1950–2019 (extrapolated) |
| `EMP_TEMP_SEX_AGE_NB_A-*.csv.gz` | ILOSTAT | Total employment (EMP_TEMP), all sexes, all ages | 1992–2024 |
| `ai-search-wipo-results-spanish-v2.xlsx` | WIPO IP Portal | AI-related patents — Spanish-language offices (ARG, CHL, COL, CRI, DOM, MEX, PER, URY, …) | up to 2024 |
| `ai-search-wipo-results-br-portuguese-v2.xlsx` | WIPO IP Portal | AI-related patents — Brazil (Portuguese) | up to 2024 |
| `cat-ai-patents-country-data/publications_yearly_articles.csv` | OECD.AI Policy Observatory | AI publication counts (Panel B AI measure) | 2016–2024 |

Every file in `data/` is read by the pipeline; no unused data is shipped.

**Sample periods:** Panel A 2000–2024; Panel B 2016–2024 (both unbalanced due to data availability).

### AI Patent Classification

AI-related patents were identified from the WIPO IP Portal using a keyword search strategy aligned with OECD/WIPO guidance for AI patent identification (machine learning, neural networks, computer vision, natural language processing, robotics, expert systems). Counts are aggregated to the country-year level; separate Spanish and Portuguese searches maximize coverage for the region. The main AI regressor is a **per-capita AI patent stock** accumulated with depreciation (δ = 0.36, following Yan et al. 2020), entered in logs (`LN_AI`).

### Data Licensing & Attribution

The input data files are redistributed here to make the results reproducible. Each remains subject to the terms of its original provider; users should cite the primary sources rather than this repository:

- **World Bank — World Development Indicators (WDI):** [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses). Attribution: The World Bank, World Development Indicators.
- **Penn World Table 10.01:** Feenstra, Inklaar & Timmer (2015), "The Next Generation of the Penn World Table," *American Economic Review*, 105(10), 3150–3182. [www.rug.nl/ggdc/productivity/pwt](https://www.rug.nl/ggdc/productivity/pwt/); CC BY 4.0.
- **ILOSTAT (International Labour Organization):** Redistributed under the ILO [terms of use](https://ilostat.ilo.org/about/copyright/) (CC BY 4.0). Attribution: ILOSTAT.
- **WIPO IP Portal (PATENTSCOPE):** AI-patent search exports derived from the [WIPO IP Portal](https://patentscope.wipo.int/), subject to WIPO's [terms of use](https://www.wipo.int/tools/en/disclaim.html). Files here are aggregated, keyword-filtered search results prepared by the author.
- **OECD.AI Policy Observatory:** AI publication counts from [oecd.ai](https://oecd.ai/), subject to OECD [terms and conditions](https://www.oecd.org/termsandconditions/). Attribution: OECD.AI Policy Observatory.

---

## Methodology

### TFP Computation

**Solow Residual:**

```
TFP_it = GDP_it / (K_it^α × (L_it × HC_it)^(1−α))
```

where α = 0.35, K is the capital stock from the Perpetual Inventory Method (PIM, δ = 0.05) using gross fixed capital formation (GFCF) from WDI, L is total employment from ILOSTAT, and HC is the PWT 10.01 human capital index.

**DEA-Malmquist Index (Färe et al. 1994):**

```
M_it = sqrt[ (D^t(x_{t+1}, y_{t+1}) / D^t(x_t, y_t)) × (D^{t+1}(x_{t+1}, y_{t+1}) / D^{t+1}(x_t, y_t)) ]
```

Output-oriented, 2 inputs (capital and effective labor L×HC) for consistency with the Solow specification. VRS is the main specification; CRS is reported as robustness (it resolves VRS infeasibility for small DMUs). M > 1 indicates productivity improvement.

### Panel Estimators

| Estimator | Abbrev. | Notes |
|---|---|---|
| Pooled OLS | OLS | Cluster-robust SE by country |
| Two-way Fixed Effects | FE-2w | Country + year effects; cluster and Driscoll-Kraay SE |
| Random Effects (GLS) | RE | Variance components |
| Common Correlated Effects Pooled | CCEP | Pesaran (2006); cross-mean augmented |
| Common Correlated Effects FE | CCEFE | Pesaran (2006); FE variant |

The Pesaran CD test for cross-sectional dependence is reported for all dependent variables; CCEP/CCEFE are the preferred estimators under dependence. The pipeline additionally runs mediation analysis (Baron-Kenny), heterogeneity analysis (interactions and subsamples), and Canay (2011) panel quantile regression.

### Changes from v4

v5 supersedes the earlier v4 package with corrections and an expanded sample:

- **Malmquist formula corrected** to the standard Färe et al. (1994) form.
- **Two-way fixed effects** (year dummies added to FE/CCE estimators).
- **DEA uses 2 inputs** (capital, effective labor) for consistency with Solow; the 3-input version is retained as robustness.
- **AI measure** is now a per-capita patent stock with depreciation (Luo et al. 2024).
- **Interpolation** limited to `limit_direction='forward', limit=3`.
- **Panel expanded** from 7 to 9 countries (added DOM, URY); sample window 2000–2024.
- DEA solver returns NaN for infeasible cases.

---

## Replication Instructions

### 1. Requirements

- Python 3.10 or later
- `numpy`, `pandas`, `scipy`, `openpyxl`

```bash
pip install -r requirements.txt
```

### 2. Clone the Repository

```bash
git clone https://github.com/carlosyv/tfp-ai-patent-latam.git
cd tfp-ai-patent-latam
```

The ILOSTAT employment file is stored gzipped and is read directly by the pipeline (`pandas.read_csv` decompresses `.gz` transparently) — no manual decompression is required.

### 3. Run the Main Pipeline (Panel A)

From the repository root:

```bash
python pipeline_v5/run_pipeline_v5.py
```

The full econometric report (all estimators, CD tests, mediation, heterogeneity, and quantile regressions) is printed to the console, and the estimation datasets are written to `output/results/`.

### 4. Run the Robustness Panel (Panel B, optional)

```bash
python pipeline_v5/run_pipeline_v5_panelB.py
```

Panel B reuses the shared estimators from Panel A and uses OECD.AI publication counts as the AI measure across 17 countries (2016–2024). It reads `output/results/merged_dissertation_v5.csv`, so run Panel A first.

---

## Output Files

All outputs are written to `output/results/`:

| File | Description |
|---|---|
| `solow_tfp_dissertation_v5.csv` | Country-year Solow TFP levels and PIM capital stock. |
| `malmquist_dissertation_v5.csv` | DEA-Malmquist TFP change (VRS, main) with efficiency/technical decomposition. |
| `malmquist_crs_dissertation_v5.csv` | DEA-Malmquist TFP change (CRS, robustness). |
| `merged_dissertation_v5.csv` | Panel A estimation dataset (TFP measures, AI patent stock, WDI controls). |
| `merged_panelB_v5.csv` | Panel B estimation dataset (OECD.AI publications, N=17). |

Publication-ready benchmark tables are written to `output/results/benchmark_dissertation_v5/`:

| File | Description |
|---|---|
| `regression_results.json` | Full structured benchmark results (all specifications and estimators). |
| `regression_comparison.csv` | AI coefficient (β, SE, p, stars, R², N) across specs × estimators. |
| `regression_summary.txt` | Human-readable summary of the benchmark AI coefficients. |
| `descriptive_statistics.csv` | Summary statistics (N, mean, SD, min, max) for the estimation sample. |
| `correlation_matrix.csv` | Pairwise correlations for key regression variables. |
| `tab_solow_full.tex`, `tab_solow_pars.tex` | LaTeX regression tables — Solow TFP (full / parsimonious). |
| `tab_malmquist_full.tex`, `tab_malmquist_pars.tex` | LaTeX regression tables — Malmquist TFP (full / parsimonious). |

The complete econometric report (all estimators, CD tests, mediation, heterogeneity, and quantile regressions) is also printed to the console when the pipeline runs.

---

## Notes on Reproducibility

- **Cross-sectional dependence:** Pesaran CD statistics are reported for all dependent variables; CCEP/CCEFE are preferred under dependence.
- **Determinism:** No stochastic components — results are numerically identical across runs given identical input data and package versions.
- **Data vintage:** Data were downloaded in 2026. WDI and OECD.AI series may be revised by their providers; results may differ marginally against updated data.

---

## Citation

If you use this code or data in your research, please cite:

> Yalta, C. (2026). *The Impact of AI Adoption on Total Factor Productivity in Latin America*. [Journal name, volume, pages]. DOI: [to be assigned]

Please also cite the primary data providers listed under [Data Licensing & Attribution](#data-licensing--attribution).

---

## License

The **code** in this repository is released under the [MIT License](LICENSE).

The **input data** files in `data/` are redistributed under the licenses of their original providers (World Bank WDI, Penn World Table, ILOSTAT, WIPO IP Portal, and OECD.AI) — see [Data Licensing & Attribution](#data-licensing--attribution). Please cite the primary data sources, not this repository, when reusing the underlying data.

---

## Contact

For questions about the replication package, please open an issue on this repository or contact the author at cyaltav@outlook.com.
