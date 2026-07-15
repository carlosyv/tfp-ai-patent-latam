"""
GTFP pipeline v1.1 refinements (post-diagnostics).

R1  Region×year fixed effects for the Solow specifications — absorbs the
    between-region common factor identified in D4 (CD=5.49 pooled, ns within
    regions). Also reports the post-R1 CD statistic.
R2  Formal H3 test: paired coefficient-difference between the AI coefficient
    in the GTFP-ML equation and the conventional-Malmquist equation. Because
    both DVs are observed on the same country-years, regressing the
    DIFFERENCE (GTFP_ML − MALM_CRS) on AI + controls with two-way FE gives
    the coefficient difference with correct paired inference. Run at L0/L1/L2.
R3  Lag-profile table (L0/L1/L2, full and common sample) exported as a
    publication table (t7_lag_profile.csv).

Run: python3 refinements.py       Outputs → output/tables/t7-t9, results.json merge.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import OUT_DIR                                  # noqa: E402
from run_gtfp_v1 import (CONTROLS, _dk_se, _merge_results,  # noqa: E402
                         fe_dk, pesaran_cd, prep_panel)

TABLES = OUT_DIR / 'tables'
AI = 'LN_AI_L1'
DEPS = ['GTFP_ML', 'MALM_CRS', 'LN_TFP_SOLOW']


def star(p):
    return '***' if p < .01 else '**' if p < .05 else '*' if p < .10 else ''


def fe_region_year(df, ycol, xcols):
    """FE with country AND region×year effects; DK SEs over years."""
    sub = df[[ycol] + xcols + ['Country', 'Year', 'REGION']].dropna().reset_index(drop=True)
    sub['RYEAR'] = sub['REGION'] + '_' + sub['Year'].astype(str)
    z = sub[[ycol] + xcols].copy()
    for _ in range(80):
        before = z.values.copy()
        z = z - z.groupby(sub['Country']).transform('mean')
        z = z - z.groupby(sub['RYEAR']).transform('mean')
        if np.nanmax(np.abs(z.values - before)) < 1e-10:
            break
    y, X = z[ycol].values, z[xcols].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = n - k - sub['Country'].nunique() - sub['RYEAR'].nunique() + 1
    se = _dk_se(X, resid * np.sqrt(n / max(dof, 1)), sub['Year'].values)
    tv = beta / se
    pv = 2 * stats.t.sf(np.abs(tv), df=max(dof, 1))
    return {'coefs': {x: {'b': float(beta[i]), 'se': float(se[i]),
                          't': float(tv[i]), 'p': float(pv[i])}
                      for i, x in enumerate(xcols)},
            'N': int(n), 'resid': resid, 'sub': sub}


def main():
    panel = prep_panel().sort_values(['Country', 'Year'])
    panel['LN_AI_L2'] = panel.groupby('Country')['LN_AI'].shift(2)
    lag_vars = {'L0': 'LN_AI', 'L1': 'LN_AI_L1', 'L2': 'LN_AI_L2'}

    # ---------- R1: region×year FE ----------
    print("R1 — Region×year FE specifications")
    r1 = {}
    for dep in DEPS:
        r = fe_region_year(panel, dep, [AI] + CONTROLS)
        cd, cdp = pesaran_cd(r['resid'], r['sub'].Country.values,
                             r['sub'].Year.values)
        c = r['coefs'][AI]
        r1[dep] = {'b': round(c['b'], 4), 'se': round(c['se'], 4),
                   'p': round(c['p'], 4), 'N': r['N'],
                   'CD_after': round(cd, 3), 'CD_p': round(cdp, 4)}
        print(f"  {dep:14s}: {c['b']:+.4f}{star(c['p'])} (SE {c['se']:.4f}) | "
              f"residual CD {cd:.2f} (p={cdp:.3f})")
    pd.DataFrame(r1).T.to_csv(TABLES / 't8_region_year_fe.csv')

    # ---------- R2: H3 paired coefficient-difference ----------
    print("\nR2 — H3 paired test: β(AI→GTFP_ML) − β(AI→MALM_CRS)")
    both = panel.dropna(subset=['GTFP_ML', 'MALM_CRS']).copy()
    both['DIFF'] = both['GTFP_ML'] - both['MALM_CRS']
    r2 = {}
    for lab, v in lag_vars.items():
        r = fe_dk(both, 'DIFF', [v] + CONTROLS)
        if r:
            c = r['coefs'][v]
            r2[lab] = {'b': round(c['b'], 4), 'se': round(c['se'], 4),
                       'p': round(c['p'], 4), 'N': r['N']}
            print(f"  {lab}: Δβ = {c['b']:+.4f}{star(c['p'])} "
                  f"(SE {c['se']:.4f}, N={r['N']})")
    pd.DataFrame(r2).T.to_csv(TABLES / 't9_h3_paired_diff.csv')

    # ---------- R3: lag-profile table ----------
    print("\nR3 — Lag-profile table (common sample)")
    common = panel.dropna(subset=DEPS + list(lag_vars.values()) + CONTROLS)
    rows = []
    for dep in DEPS:
        for lab, v in lag_vars.items():
            for sample, d in [('full', panel), ('common', common)]:
                r = fe_dk(d, dep, [v] + CONTROLS)
                if r:
                    c = r['coefs'][v]
                    rows.append({'dep': dep, 'lag': lab, 'sample': sample,
                                 'b': round(c['b'], 4), 'se': round(c['se'], 4),
                                 'p': round(c['p'], 4), 'N': r['N']})
    t7 = pd.DataFrame(rows)
    t7.to_csv(TABLES / 't7_lag_profile.csv', index=False)
    piv = t7[t7['sample'] == 'common'].pivot(index='dep', columns='lag',
                                             values='b')
    print(piv.to_string())

    _merge_results({'r1_region_year_fe': r1, 'r2_h3_paired': r2,
                    'r3_lag_profile': json.loads(t7.to_json(orient='records'))})
    print(f"\nrefinements → {TABLES}")


if __name__ == '__main__':
    main()
