# Government AI Readiness Index (GAIRI) — merged global rankings, 2019–2025

Produced by `build_gairi_panel.py` (repository root). Re-run that script to
regenerate everything in this folder; do not edit the CSVs by hand.

## Files

| File | Contents |
|---|---|
| `gairi_global_rankings_2019_2025.csv` | Tidy long panel, one row per country-year |
| `gairi_country_crosswalk.csv` | Every source country label → ISO3, with the editions in which it appears |

Raw inputs are kept unmodified in `../raw/` (seven publisher workbooks).

## Panel dimensions

- **1,283** country-year observations
- **195** distinct countries/economies (ISO3)
- **2019–2025**, unbalanced

| Edition | Countries ranked | LatAm study countries |
|---:|---:|---:|
| 2019 | 194 | 17 |
| 2020 | 172 | 17 |
| 2021 | 160 | 17 |
| 2022 | 181 | 17 |
| 2023 | 193 | 17 |
| 2024 | 188 | 17 |
| 2025 | 195 | 17 |

All 17 Panel A + Panel B countries are present in every edition, so the LatAm
sub-panel is fully balanced (119 observations).

## Variables

| Column | Description |
|---|---|
| `iso3` | ISO 3166-1 alpha-3 code |
| `country` | Canonical short English name (constant within `iso3`) |
| `year` | Index edition year |
| `rank` | Global rank as published |
| `n_ranked` | Number of countries ranked in that edition |
| `rank_pct` | `(rank − 1) / (n_ranked − 1)`; 0 = top, 1 = bottom |
| `score_raw` | Score exactly as published (2019 on 0–10; 2020–2025 on 0–100) |
| `score_100` | Common 0–100 basis (2019 multiplied by 10) |
| `score_scale` | `"0-10"` or `"0-100"`, flagging the raw scale |
| `panel_a` | 1 if in the 9-country main panel |
| `panel_b` | 1 if in the 17-country robustness panel |
| `latam_panel` | Alias of `panel_b` |
| `country_source` | Original label in the source workbook (audit trail) |
| `source_file`, `source_sheet` | Provenance of each observation |

## Source heterogeneity that was normalised

| Edition | Sheet | Header offset | Layout |
|---|---|---|---|
| 2019 | `Rankings` | 2 rows | Wide: global block in cols 0–2, regional sub-tables to the right (ignored) |
| 2020 | `Global ranking` | 1 row | Long |
| 2021 | `Global ranking` | 1 row | Long |
| 2022 | `Global rankings` | 1 row | Long |
| 2023 | `Global rankings` | 1 row | Long |
| 2024 | `Ranking` | 1 row | Long |
| 2025 | `Global Rankings` | 2 rows | Long, with a leading blank column |

Country nomenclature also drifts across editions (`Turkey` → `Türkiye`,
`Czech Republic` → `Czechia`, `Bolivia` → `Bolivia (Plurinational State of)`,
`United Kingdom` → `United Kingdom of Great Britain and Northern Ireland`, and
so on). The crosswalk in `build_gairi_panel.py` is an **explicit** dictionary
covering all 215 observed labels; fuzzy matching is deliberately not used, and
the script raises rather than silently dropping an unrecognised label.

Non-country rows (the `AVERAGE` row at the foot of the 2019 sheet, blank
spacer rows) are removed.

## Caveats for empirical use

1. **Levels are not a consistent time series.** The indicator set, pillar
   structure, weights and data vintages change between editions. `score_100`
   puts all editions in the same *units*, not on the same *scale*. Treat
   year-on-year score changes with caution; a country's score can move because
   the methodology moved.

2. **Country coverage changes substantially** (160 in 2021 to 195 in 2025).
   Raw `rank` is therefore not comparable across editions — use `rank_pct`,
   and note that even a percentile is affected by *which* countries enter.
   Entry is not random: newly added countries are disproportionately small and
   low-readiness, which mechanically shifts percentiles for incumbents.

3. **Ties in the 2019 edition.** Three rank values are shared by two countries
   each (rank 6: Canada/Sweden; rank 93: Senegal/Tanzania; rank 135:
   Barbados/Monaco), with ranks 7, 94 and 136 correspondingly skipped. This is
   competition ranking in the published source and is reproduced verbatim.

4. **Not an annual series.** GAIRI is a point-in-time assessment published
   annually, but underlying indicators have varying reference years and lags.
   Aligning `year` to the productivity panel's calendar year is an
   approximation; consider lagging when used as a right-hand-side variable.

5. **Construct validity.** GAIRI measures *government* AI readiness
   (government pillar, technology sector pillar, data & infrastructure
   pillar). It is a plausible proxy for complementary capabilities, but it is
   not a measure of economy-wide AI adoption and should not be interpreted as
   one.

6. **2025 scores are published rounded to 2 decimals**, unlike 2021–2024
   (full precision). Minor, but relevant if scores are used to break ties or
   compute tight differences.

## Provenance

Oxford Insights / International Development Research Centre (IDRC),
*Government AI Readiness Index*, editions 2019–2025. Public datasets as
distributed by the publisher. Data retain the publisher's licence terms; the
merge code is MIT-licensed with the rest of this repository.
