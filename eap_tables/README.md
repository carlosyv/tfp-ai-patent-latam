# `eap_tables/` — generating the EAP manuscript tables

Two stages, one rule: **no number reaches a table cell except by lookup from a
committed results file.**

```
 raw data ──▶ pipeline_v5/run_pipeline_v5.py ──▶ output/results/*.csv
                                                      │
                                    robustness_verification.py
                                                      │
                                                      ▼
                              compute_eap_results.py ──▶ eap_results_v5.json
                                                              │
                                       build_eap_tables.py ◀──┘
                                                              │
                                         EAP_tables_v5.docx  +  coverage report
```

## Why this exists

`run_pipeline_v5.py` estimates every specification the manuscript reports, but
only the benchmark regressions are written to disk. `run_mediation()`,
`run_heterogeneity()` and `run_quantile_canay()` all return `None` — they print
to stdout and nothing else. Tables 4, 5, 6 and 7 therefore had no
machine-readable source and were keyed in by hand from console output.

Table 6 panel B did not even have console output behind it. §5.7 of the
dissertation describes the robustness battery in prose and reports no
coefficients; the panel's fourteen cells were filled with plausible values that
had never been estimated. Five of seven specifications were wrong, two with the
sign flipped. The builder that produced them carried a header comment reading
*"All numbers verified against dissertation-v5 Tables …"* — a file-scope
assurance written over content that had a hole in it.

The design here makes that specific failure impossible: a cell whose statistic
is absent renders as **[NO SOURCE]** in red, is listed in
`eap_tables_coverage.md`, and makes the build exit non-zero.

## Running it

```bash
python3 pipeline_v5/run_pipeline_v5.py            # if results/ is stale
python3 pipeline_v5/robustness_verification.py    # Table 6 panel B
python3 eap_tables/compute_eap_results.py         # -> eap_results_v5.json
python3 eap_tables/build_eap_tables.py            # -> EAP_tables_v5.docx
```

`build_eap_tables.py` exits 1 if any cell is unsourced. Use `--allow-missing`
for a draft build; the cells stay marked either way.

## Stage 1 — `compute_eap_results.py`

Imports its estimators from `run_pipeline_v5` **unchanged** —
`pooled_ols`, `fixed_effects_twoway`, `cce_pooled`, `cce_fe`,
`pesaran_cd_test`, `compute_descriptives`. It assembles and serialises; it does
not define new estimators. That is why the output reproduces the dissertation
rather than approximating it.

Inputs, all under `output/results/`:

| File | Produced by | Used for |
|---|---|---|
| `merged_dissertation_v5.csv` | `run_pipeline_v5.py:1602` | Tables 1–6 (Panel A, 225 obs) |
| `merged_panelB_v5.csv` | `run_pipeline_v5_panelB.py:498` | Table 7 (OECD publications, 136 obs) |
| `robustness_verification_v5.json` | `pipeline_v5/robustness_verification.py` | Table 6 panel B |

`ln_TFP` is reconstructed as `np.log(df['TFP'].clip(lower=1e-15))`, matching
`run_pipeline_v5.py:1609`. The interaction terms `AI_x_RL`, `AI_x_MOBILE`,
`AI_x_BROADBAND` are already in the merged CSV (built at lines 629–631).

### Block-by-block provenance

| JSON key | Manuscript | How it is computed |
|---|---|---|
| `table1_descriptives` | Table 1 | Direct from the merged panel over the explicit `TABLE1_VARS` list. The pipeline's `compute_descriptives()` covers a different, shorter variable set and reports Solow TFP in levels, so it cannot produce this table; it is stored alongside under `_pipeline_compute_descriptives` for cross-reference. |
| `table2_cd_tests` | Table 2 | `pesaran_cd_test()` on residuals of the parsimonious two-way FE model, for `ln_TFP`, `TFP_Change` (VRS), `TFP_Change_CRS`. |
| `table3_benchmark` | Table 3 | `pooled_ols`, `fixed_effects_twoway(se_type='driscoll_kraay')`, `cce_pooled`, `cce_fe` on `[LN_AI] + CONTROLS_PARS`. OLS is stored because the table note quotes it. |
| `table4_heterogeneity` | Table 4, App. D | Mirrors `run_heterogeneity()`: interaction model per moderator, then median splits estimated separately above and below. Stores the interaction model's **own** main effect on `LN_AI` — see the warning below. |
| `table5_quantile` | Table 5 | Mirrors `run_quantile_canay()`: one-way entity FE for `mu_hat_i`, `y* = y − mu_hat`, time-demean `y*` and `X`, Koenker–Bassett LP per τ, paired bootstrap `B=200` under `RandomState(42)`, `se = boot.std(ddof=0)`, p from t with `df = n − k`. |
| `table6a_mediation` | Table 6 panel A | Mirrors `run_mediation()`. See the three gotchas below. |
| `table6b_robustness` | Table 6 panel B | **Read, not recomputed.** Loaded from `robustness_verification_v5.json` with its SHA-256 recorded. This is the panel that was fabricated; it stays pinned to the verification script's own output. |
| `table7_panel_b` | Table 7 | `pooled_ols` / `fixed_effects_twoway` / `cce_pooled` on `[LN_AI_pub] + CONTROLS_PARS`, plus the Pesaran CD statistics. |

### Three things that are easy to get wrong

**Mediation uses five controls, not six.** `controls_med` drops `LN_HC_index`,
because human capital is itself a mediator. So Step 1 is *not* the Table 3
baseline: it gives β₁ = −0.0123, not −0.0157. The dissertation reports this as
the "Step 1 β₁ (ref.)" row. The estimation sample is also fixed per mediator by
dropping missing values across y, AI, M and the controls, and reused for all
three steps.

**% mediated is `(a₁·δ₂)/β₁`, not `(β₁ − δ₁)/β₁`.** The dissertation's table
note describes the second formula; the code computes the first, and the code is
what produced the published 3.7% and −28.4%. Left as-is here to reproduce; the
note is what should change.

**The quantile bootstrap is paired, not clustered.** A block bootstrap by
country would be more defensible for panel data, but changing it moves every
standard error in Table 5. Change the pipeline first, rerun both, document the
move — don't quietly fix it in this layer.

### Driscoll–Kraay standard errors: two conventions

`run_pipeline_v5.py:801` passes **raw residuals** to `_driscoll_kraay_se`.
`gtfp_pipeline`'s `fe_dk` scales them by `sqrt(n/dof)` first, where
`dof = n − k − N_entity − N_time + 1`. For Panel A that is `sqrt(225/185) =
1.1028`, so v5's DK errors are ~10% smaller:

| | β | SE, v5 (uncorrected) | SE, dof-corrected |
|---|---|---|---|
| Solow ln(TFP), FE-DK | −0.0157 | 0.0118 (t = −1.34) | 0.0130 (t = −1.21) |
| Malmquist CRS, FE-DK | −0.0094 | 0.0076 (t = −1.24) | 0.0084 (t = −1.12) |

The corrected version is the defensible one — Hoechle's `xtscc` applies a
small-sample adjustment, and without it DK errors are downward-biased in short
panels. **The default here is the uncorrected convention**, because the first
job of this script is to reproduce the dissertation and the submitted
manuscript. Pass `--dk-dof-correction` to switch; `meta.dk_dof_correction` in
the JSON and the header line of the .docx both record which was used.

No baseline inference changes either way. The interaction models are where it
could matter (Table 7.2 broadband, t = 2.43, falls to roughly t = 2.20), and
those have different N and k, so do not rescale by 1.1028 — rerun.

## Stage 2 — `build_eap_tables.py`

Reads `eap_results_v5.json` and nothing else. No pandas, no estimation, no
access to the raw data. It cannot compute a number even by accident.

Every value goes through `Results.get(path)`, which walks a dotted path and
raises `MissingResult` if any segment is absent. **There is deliberately no
`default=` parameter.** On a miss the path is appended to `R.missing`, the cell
renders `[NO SOURCE]` in bold red, and `main()` returns 1.

Because paths are dotted, **result keys must not contain a literal `.`** Two
places needed re-slugging: quantiles are keyed `tau_010 … tau_090` rather than
`tau_0.10`, and the robustness specifications are re-mapped from the
verification script's labels (`delta_p=0.22` → `delta_p_022`, `2SLS lagged AI`
→ `iv_2sls_lag1`) via `_key_map`, which is stored in the JSON.

### Known departures from the submitted manuscript

Both are corrections, and both are deliberate.

1. **Table 4's main-effect row.** The submitted table printed the *baseline*
   coefficient (−0.016 / −0.009) in the `ln(AI patent stock)` row of the
   interaction models. That is wrong: in a model with `AI × MOD`, the main
   effect is conditional on `MOD = 0` and differs from the baseline. The true
   values are −0.0068 / +0.0016 / +0.0155 (Solow) and −0.0123 / −0.0329 /
   −0.0232 (Malmquist). This builder prints the model's own main effect and the
   note explains the distinction. The dissertation has the same problem.

2. **Table 4's Malmquist × Rule-of-Law interaction.** Printed as `0.014`; the
   correct value is `0.0014`, an order of magnitude out. Insignificant either
   way, but wrong.

Table 6 panel B's sample sizes are also now reported (225 / 216 / 207), since
the lagged and 2SLS specifications lose initial years.

## Verification

Every block was checked against dissertation v5 after the rewrite:

- Table 1 vs 5.1, Table 2 vs 5.2, Table 3 vs 5.3/5.4 — exact
- Table 4 vs 7.1/7.2/D.1/D.2 — exact, except the two corrections above
- Table 5 vs 8.1 — exact to four decimals on all five quantiles, β and SE
- Table 6A vs 6.1 — exact, including Sobel z and % mediated
- Table 6B vs `robustness_verification_v5.json` — exact
- Table 7 vs 9.2 — exact

## If you add a table

Add the statistic to `compute_eap_results.py` first, rerun it, then reference
the new path in `build_eap_tables.py`. Never type a number into the builder.
If a value cannot be computed yet, leave it out — the `[NO SOURCE]` marker and
the non-zero exit exist so that an unfinished table is visibly unfinished
rather than quietly plausible.
