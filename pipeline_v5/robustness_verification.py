"""
Paper 1 (EAP) — Table 6 Panel B robustness verification.

PURPOSE (integrity audit 2026-07): the consolidated EAP manuscript's Table 6
Panel B was rendered with coefficients that do not trace to pipeline output.
This script computes the TRUE values of every robustness specification on the
official v5 Panel A data (output/results/merged_dissertation_v5.csv), using
the dissertation's parsimonious two-way FE-DK specification, and prints a
comparison against the values currently in the submitted manuscript.

Specs (DVs: ln Solow TFP; Malmquist CRS change index):
  1. Baseline           : LN_AI  (ln per-capita patent stock, delta=0.36)
  2. Raw patent count   : ln(1 + AI_Patents flow)
  3. Alt depreciation   : stock rebuilt with delta=0.22, per-capita, ln(+1)
  4. Per-GDP norm.      : ln(1 + stock per billion USD GDP)
  5. One-period lag     : LN_AI_L1
  6. Two-period lag     : LN_AI_L2
  7. 2SLS predetermined : LN_AI instrumented by LN_AI_L1 (within-2SLS, DK SEs
                          on second stage; approximation, labelled as such)

Run: python3 robustness_verification.py
Out: output/results/robustness_verification_v5.json (+ console comparison)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'gtfp_pipeline'))
from run_gtfp_v1 import _two_way_demean, _dk_se, fe_dk  # noqa: E402

MERGED = REPO / 'output' / 'results' / 'merged_dissertation_v5.csv'
OUTJ = REPO / 'output' / 'results' / 'robustness_verification_v5.json'

CONTROLS = ['LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index',
            'FDI_inflows', 'GOV_consumption', 'URB_urban_pop']

# Values currently printed in the submitted EAP manuscript (Table 6 Panel B)
SUBMITTED = {
    'Baseline':        {'solow': -0.016, 'malm': -0.009},
    'Raw count':       {'solow': -0.012, 'malm': -0.005},
    'delta_p=0.22':    {'solow': -0.018, 'malm': -0.010},
    'Per-GDP':         {'solow': -0.014, 'malm': -0.008},
    'Lag 1':           {'solow': -0.014, 'malm': -0.008},
    'Lag 2':           {'solow': -0.011, 'malm': -0.007},
    '2SLS lagged AI':  {'solow': -0.019, 'malm': -0.011},
}


def stock_delta(df, delta):
    out = []
    for c, g in df.sort_values('Year').groupby('Country'):
        s = 0.0
        for _, r in g.iterrows():
            s = r['AI_Patents'] + (1 - delta) * s
            out.append({'Country': c, 'Year': r['Year'], 'S': s})
    return pd.DataFrame(out)


def within_2sls(df, ycol, endog, instr, controls):
    """Two-way within 2SLS: endog instrumented by instr. DK SEs on 2nd stage."""
    from scipy import stats as sst
    sub = df[[ycol, endog, instr] + controls + ['Country', 'Year']].dropna().reset_index(drop=True)
    z = _two_way_demean(sub, [ycol, endog, instr] + controls)
    # first stage
    X1 = z[[instr] + controls].values
    g1, *_ = np.linalg.lstsq(X1, z[endog].values, rcond=None)
    fit = X1 @ g1
    # second stage
    X2 = np.column_stack([fit, z[controls].values])
    b, *_ = np.linalg.lstsq(X2, z[ycol].values, rcond=None)
    resid = z[ycol].values - np.column_stack([z[endog].values, z[controls].values]) @ b
    n, k = X2.shape
    dof = n - k - sub['Country'].nunique() - sub['Year'].nunique() + 1
    se = _dk_se(X2, resid * np.sqrt(n / max(dof, 1)), sub['Year'].values)
    t = b[0] / se[0]
    p = 2 * sst.t.sf(abs(t), df=max(dof, 1))
    return {'b': float(b[0]), 'se': float(se[0]), 'p': float(p), 'N': int(n)}


def main():
    df = pd.read_csv(MERGED)
    df['LN_TFP'] = np.log(df['TFP'])
    df['MALM'] = df['TFP_Change_CRS']

    # spec regressors
    df['X_raw'] = np.log1p(df['AI_Patents'])
    s22 = stock_delta(df[['Country', 'Year', 'AI_Patents']], 0.22)
    df = df.merge(s22, on=['Country', 'Year'], how='left')
    df['X_d22'] = np.log1p(df['S'] / df['POP_total'] * 1e6)   # per million pop, ln(+1)
    df['X_gdp'] = np.log1p(df['AI_Patent_Stock'] / (df['GDP'] / 1e9))

    specs = {
        'Baseline': 'LN_AI',
        'Raw count': 'X_raw',
        'delta_p=0.22': 'X_d22',
        'Per-GDP': 'X_gdp',
        'Lag 1': 'LN_AI_L1',
        'Lag 2': 'LN_AI_L2',
    }

    res = {}
    print(f"{'spec':16s} {'DV':6s} {'TRUE b':>10s} {'SE':>8s} {'p':>7s} {'N':>4s}"
          f"   {'submitted':>10s}  match?")
    for name, x in specs.items():
        res[name] = {}
        for dv, col in [('solow', 'LN_TFP'), ('malm', 'MALM')]:
            r = fe_dk(df, col, [x] + CONTROLS)
            c = r['coefs'][x]
            res[name][dv] = {'b': round(c['b'], 4), 'se': round(c['se'], 4),
                             'p': round(c['p'], 4), 'N': r['N']}
            sub_v = SUBMITTED[name][dv]
            match = "≈" if abs(c['b'] - sub_v) < 0.0015 else "DIFFERS"
            print(f"{name:16s} {dv:6s} {c['b']:+10.4f} {c['se']:8.4f} "
                  f"{c['p']:7.3f} {r['N']:4d}   {sub_v:+10.3f}  {match}")

    # 2SLS
    res['2SLS lagged AI'] = {}
    for dv, col in [('solow', 'LN_TFP'), ('malm', 'MALM')]:
        r = within_2sls(df, col, 'LN_AI', 'LN_AI_L1', CONTROLS)
        res['2SLS lagged AI'][dv] = {k: round(v, 4) if isinstance(v, float) else v
                                     for k, v in r.items()}
        sub_v = SUBMITTED['2SLS lagged AI'][dv]
        match = "≈" if abs(r['b'] - sub_v) < 0.0015 else "DIFFERS"
        print(f"{'2SLS lagged AI':16s} {dv:6s} {r['b']:+10.4f} {r['se']:8.4f} "
              f"{r['p']:7.3f} {r['N']:4d}   {sub_v:+10.3f}  {match}")

    OUTJ.write_text(json.dumps(res, indent=2))
    print(f"\nsaved {OUTJ}")


if __name__ == '__main__':
    main()
