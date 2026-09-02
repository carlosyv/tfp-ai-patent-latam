# Period robustness + official v5 heterogeneity — verification notes (2026-07-19)

## Period-robustness table (§5.8) — `analysis/period_robustness.py` → output/results/period_robustness_table.csv
Windows: 2000–24 (patents), 2016–24 (patents), 2017–24 (patents AND composite).
H1 null in every window and under both treatments. One table, windows as blocks — not cluttered.

## Official v5 heterogeneity (run_heterogeneity, captured to
## output/results/heterogeneity_v5_official.txt — pipeline printed but never saved this)

**The conditional (H3/H4) story is TFP-MEASURE-DEPENDENT:**

Malmquist-CRS (TFP change): POSITIVE conditioning, consistent with the pilot narrative —
  High-vs-low subsample diff tests significant for ALL THREE moderators:
  RuleOfLaw Δβ=+0.035 (p=.044), Mobile Δβ=+0.049 (p=.015), Broadband Δβ=+0.032 (p=.037);
  interactions positive for mobile (**) and broadband (**).

Solow (ln TFP level): MIXED-TO-OPPOSITE for institutions —
  RuleOfLaw interaction = −0.047*** and high-RL subsample β(AI) = −0.058*** (diff −0.086***):
  the AI–TFP *level* association is MORE NEGATIVE in high-institution countries.
  Broadband: interaction −0.003** but high-broadband subsample +0.034* (approaches disagree).

**Dissertation framing (pre-defense critical):**
- The positive-conditioning claim (pilot Q3/Q4) is supported on the Malmquist margin —
  productivity CHANGE — across all moderators; state it as such, not as a blanket result.
- The negative Solow×RL result is interpretable through the report's own typology (§1.1.3
  Chile paradox: top governance, falling level-TFP) and the J-curve: adoption is deepest
  precisely where institutions are strong, and reorganization costs depress measured
  level-TFP first. Efficiency-change vs level distinction (DEA decomposition) is the
  natural mechanism discussion.
- Do NOT let §7.1's "more positive or at minimum less negative" stand unqualified for
  Solow×RL — it is contradicted at the 1% level. Precision here converts a committee
  attack into a contribution.
- My earlier composite/period runs used Solow lnTFP only — explains their negative
  interaction signs; not an error, a measure choice. Composite robustness conclusions
  (H1 null robust) unaffected.

# ILO labor-channel exercise (2026-07-20) — `analysis/ilo_labor_channel.py`
Data: ILOSTAT EMP_TEMP_SEX_OCU via rplumber API (saved data/ilostat/EMP_TEMP_SEX_OCU_NB_A_latam.csv;
old bulk endpoint is dead). Occupational shares (ISCO-08 majors; SKILL buckets) on lagged
LN_AI, two-way FE, country-clustered.
RESULT: NULL across all occupation groups. Clerical (routine-exposed) share does NOT
decline with AI patenting (b=+0.27, t=1.37); managers weakly negative (t=-1.93, 10%);
skill buckets null. Reading for the dissertation (§1.2/§2.7): no detectable occupational
recomposition at the aggregate level yet — consistent with shallow AI diffusion and the
overall null unconditional effects; displacement concerns are prospective, not present,
in LatAm macro data. Caveats: small N, slow-moving shares, informality may absorb
adjustment invisibly (workers shift formal→informal within the same ISCO group).
Output: output/results/ilo_labor_channel.csv.
