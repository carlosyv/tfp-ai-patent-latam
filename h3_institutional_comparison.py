#!/usr/bin/env python3
"""
h3_institutional_comparison.py
================================
Compare three H3 moderation regressions for institutional quality:

  Model 1 — RL.EST  : Rule of Law              (current pipeline)
  Model 2 — RQ.EST  : Regulatory Quality
  Model 3 — GE.EST  : Government Effectiveness

For each indicator, runs FE and RE moderation (Y = β1·AI + β2·MOD + β3·AI×MOD + controls)
across both TFP measures (Solow, Malmquist). Outputs a comparison table + CSV.

Usage:
    python h3_institutional_comparison.py
"""

import sys, warnings, json
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

# ── Path setup ─────────────────────────────────────────────────────────────
PIPELINE_DIR = Path('/sessions/sleepy-hopeful-edison/mnt/code')
WB_CSV       = PIPELINE_DIR / 'data' / 'wb_data_export.csv'
OUT_DIR      = PIPELINE_DIR / 'output' / 'h3_institutional_comparison'
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PIPELINE_DIR))

print("Importing pipeline module (this may take a moment)...")
import run_dissertation_v4_noimput_pipeline as pipe

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1-5: Build the panel using the pipeline's own functions
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "═"*70)
print("STEPS 1–5: Loading data via pipeline")
print("═"*70)

# Steps 1: Extract WB + PWT + ILOSTAT data
solow_df, wdi_df = pipe.extract_data_from_csv()

# Step 2: Solow TFP
print(f"\n{'─'*50}")
print(f"Computing Solow TFP (α={pipe.ALPHA})...")
solow_df = pipe.compute_solow_tfp(solow_df)

# Step 3: Malmquist DEA
print(f"\n{'─'*50}")
print("Computing Malmquist DEA TFP...")
dea_df = solow_df.dropna(subset=['GDP', 'CAPITAL', 'LABOR', 'HC_index'])
mq = pipe.compute_malmquist_tfp(dea_df)

# Step 4: AI patents
print(f"\n{'─'*50}")
print("Loading WIPO AI patents...")
patents = pipe.load_ai_patents()

# Step 5: Merge into panel
print(f"\n{'─'*50}")
print("Building merged panel dataset...")
df = pipe.build_merged_dataset(patents, solow_df, mq, wdi_df)
df['ln_TFP'] = np.log(df['TFP'].clip(lower=1e-15))

print(f"\n  Panel ready: {df.shape[0]} obs, {df['Country'].nunique()} countries, "
      f"{df['Year'].min()}–{df['Year'].max()}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Augment with RQ.EST and GE.EST
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "═"*70)
print("Loading extra governance indicators (RQ.EST, GE.EST)...")
print("═"*70)

raw = pd.read_csv(WB_CSV)
raw = raw[
    (raw['year'] >= pipe.START_YR) &
    (raw['year'] <= pipe.END_YR) &
    raw['country_code'].isin(pipe.COUNTRIES)
]

extra_map = {
    'RQ.EST': 'INST_reg_quality',
    'GE.EST': 'INST_gov_eff',
}

extra_raw = raw[raw['indicator_code'].isin(extra_map)].copy()
extra_raw['var_name'] = extra_raw['indicator_code'].map(extra_map)

extra_wide = extra_raw.pivot_table(
    index=['country_code', 'year'],
    columns='var_name',
    values='value',
    aggfunc='first',
).reset_index().rename(columns={'country_code': 'Country', 'year': 'Year'})

df = df.merge(extra_wide, on=['Country', 'Year'], how='left')

# Create interaction terms for the two new moderators
df['AI_x_RQ'] = df['LN_AI_Patents'] * df['INST_reg_quality']
df['AI_x_GE'] = df['LN_AI_Patents'] * df['INST_gov_eff']

# Coverage report
print("\nGovernance indicator coverage (panel):")
print(f"  {'Indicator':<30} {'Non-null':>8}  {'Share':>7}")
print(f"  {'─'*47}")
for col, code in [
    ('INST_rule_of_law', 'RL.EST'),
    ('INST_reg_quality', 'RQ.EST'),
    ('INST_gov_eff',     'GE.EST'),
]:
    nn    = df[col].notna().sum()
    total = len(df)
    print(f"  {col:<30} {nn:>8}/{total}  {nn/total*100:>5.1f}%")

# Descriptive stats for the three moderators
print("\nDescriptive statistics (governance indicators):")
gov_cols = ['INST_rule_of_law', 'INST_reg_quality', 'INST_gov_eff']
desc = df[gov_cols].agg(['mean','std','min','max']).round(4)
print(desc.to_string())

print("\nCorrelations between governance indicators:")
print(df[gov_cols].corr().round(4).to_string())

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Run the three H3 moderation regressions
# ══════════════════════════════════════════════════════════════════════════════

def stars(p):
    if   p < 0.01: return '***'
    elif p < 0.05: return '**'
    elif p < 0.10: return '*'
    return ''

CONTROLS_PARS = pipe.CONTROLS_PARS  # ['LNPGDP_constant2015','OPEN_trade','LN_HC_index','FDI_inflows','GOV_consumption','URB_urban_pop']

configs = [
    ('RL.EST — Rule of Law',              'INST_rule_of_law', 'AI_x_RL'),
    ('RQ.EST — Regulatory Quality',       'INST_reg_quality', 'AI_x_RQ'),
    ('GE.EST — Government Effectiveness', 'INST_gov_eff',     'AI_x_GE'),
]

results_store = {}

for label, moderator_var, interaction_var in configs:
    print(f"\n{'═'*70}")
    print(f"H3 Moderation — {label}")
    print(f"Moderator: {moderator_var}  |  Interaction: {interaction_var}")
    print(f"{'═'*70}")

    results_store[label] = {}

    for y_col, tfp_label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {tfp_label} TFP:")
        controls_with_mod = CONTROLS_PARS + [moderator_var]

        mod = pipe.moderation_analysis(
            df, y_col,
            moderator_var=moderator_var,
            interaction_var=interaction_var,
            controls=controls_with_mod,
        )
        results_store[label][tfp_label] = mod

        for est, r in mod.items():
            if 'error' in r:
                print(f"    {est}: ERROR — {r['error']}")
            else:
                sig = stars(r['p_interaction'])
                print(
                    f"    {est}: "
                    f"β(AI)={r['beta_AI']:+.5f}(p={r['p_AI']:.3f})  "
                    f"β(AI×INST)={r['beta_interaction']:+.7f}(p={r['p_interaction']:.3f}){sig}  "
                    f"β(MOD)={r['beta_moderator']:+.5f}  "
                    f"N={r['obs']}  R²={r['r2']:.4f}"
                )

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Print structured comparison tables
# ══════════════════════════════════════════════════════════════════════════════

SEP = "═" * 118

def print_comparison_table(estimator='FE'):
    print(f"\n{SEP}")
    print(f"COMPARISON TABLE — H3 Moderation ({estimator} Estimator, Cluster-Robust SE)")
    print(SEP)
    hdr = (f"{'Indicator':<38} {'TFP':<12} {'β(AI)':>10} {'p(AI)':>7} "
           f"{'β(AI×INST)':>13} {'SE':>10} {'p(int.)':>8} {'Sig':>4} "
           f"{'β(MOD)':>10} {'N':>5} {'R²':>7}")
    print(hdr)
    print("─" * 118)
    for label, moderator_var, interaction_var in configs:
        for tfp_label in ['Solow', 'Malmquist']:
            mod = results_store[label][tfp_label]
            if estimator in mod and 'error' not in mod[estimator]:
                r = mod[estimator]
                sig = stars(r['p_interaction'])
                row = (
                    f"{label:<38} {tfp_label:<12} {r['beta_AI']:>+10.5f} {r['p_AI']:>7.3f} "
                    f"{r['beta_interaction']:>+13.7f} {r['se_interaction']:>10.7f} "
                    f"{r['p_interaction']:>8.4f} {sig:>4} "
                    f"{r['beta_moderator']:>+10.5f} {r['obs']:>5} {r['r2']:>7.4f}"
                )
                print(row)
        print("─" * 118)
    print(f"\n  Notes: *** p<0.01  ** p<0.05  * p<0.10. Country fixed effects. "
          f"Controls: log(GDPpc), trade openness, log(HC index), FDI, govt consumption, urbanisation.")

print_comparison_table('FE')
print_comparison_table('RE')

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: Save results to CSV + JSON
# ══════════════════════════════════════════════════════════════════════════════

records = []
for label, moderator_var, interaction_var in configs:
    for tfp_label in ['Solow', 'Malmquist']:
        for est in ['FE', 'RE']:
            mod = results_store[label][tfp_label]
            if est in mod:
                r = mod[est]
                rec = {
                    'indicator_label':  label,
                    'indicator_code':   label.split(' — ')[0].strip(),
                    'moderator_var':    moderator_var,
                    'interaction_var':  interaction_var,
                    'tfp_measure':      tfp_label,
                    'estimator':        est,
                }
                if 'error' in r:
                    rec.update({'error': r['error']})
                else:
                    rec.update({
                        'beta_AI':          r['beta_AI'],
                        'p_AI':             r['p_AI'],
                        'sig_AI':           stars(r['p_AI']),
                        'beta_interaction': r['beta_interaction'],
                        'se_interaction':   r['se_interaction'],
                        'p_interaction':    r['p_interaction'],
                        'sig_interaction':  stars(r['p_interaction']),
                        'beta_moderator':   r['beta_moderator'],
                        'obs':              r['obs'],
                        'r2':               r['r2'],
                    })
                records.append(rec)

results_df = pd.DataFrame(records)
csv_path = OUT_DIR / 'h3_institutional_comparison.csv'
results_df.to_csv(csv_path, index=False)
print(f"\n✓ Results CSV saved: {csv_path}")

# JSON for full detail
json_path = OUT_DIR / 'h3_institutional_comparison.json'
with open(json_path, 'w') as f:
    # convert numpy types for json serialisation
    def to_py(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, dict):  return {k: to_py(v) for k, v in obj.items()}
        if isinstance(obj, list):  return [to_py(v) for v in obj]
        return obj
    json.dump(to_py(results_store), f, indent=2)
print(f"✓ Results JSON saved: {json_path}")

print(f"\n{'═'*70}")
print("DONE — H3 institutional moderation comparison complete.")
print(f"{'═'*70}")
