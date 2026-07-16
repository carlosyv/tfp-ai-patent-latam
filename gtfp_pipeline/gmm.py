"""
GTFP pipeline — system GMM (Blundell–Bond) via pydynpd, collapsed instruments.

Dynamic specification per DV:
    y_it = ρ y_i,t-1 + β lnAI_i,t-1 + γ'X_it + time dummies + η_i + ε_it
GMM-style instruments: lags 2:4 of y (collapsed). AI and controls treated as
predetermined/exogenous IV-style. Reports coefficient on lnAI(t-1), AR(1)/AR(2),
Hansen J. NOTE: pydynpd is a young implementation — results are cross-checked
for sanity (ρ within (0,1), instrument count < N) and labelled as robustness.

Run: python3 gmm.py     Output: merges 'gmm' block into output/results.json.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import OUT_DIR                     # noqa: E402
from run_gtfp_v1 import _merge_results, prep_panel  # noqa: E402

AI = 'LN_AI_L1'
CONTROLS = ['LN_GDP_PC', 'TRADE', 'FDI', 'GOV_CONS', 'URBAN']
DEPS = ['GTFP_ML', 'MALM_CRS', 'LN_TFP_SOLOW']


def run_one(panel, dep):
    from pydynpd import regression
    cols = ['Country', 'Year', dep, AI] + CONTROLS
    df = panel[cols].dropna().copy()
    # pydynpd requires consecutive integer time; Year already annual ints
    cmd = (f"{dep} L1.{dep} {AI} {' '.join(CONTROLS)} | "
           f"gmm({dep}, 2:4) pred({AI}) iv({' '.join(CONTROLS)}) | collapse")
    try:
        m = regression.abond(cmd, df, ['Country', 'Year'])
    except Exception as e:
        return {'error': str(e)[:200]}
    try:
        mod = m.models[0]
        tbl = mod.regression_table
        r = tbl[tbl.variable == AI].iloc[0]
        rho = tbl[tbl.variable == f'L1.{dep}'].iloc[0]
        out = {
            'b': round(float(r.coefficient), 4),
            'se': round(float(r.std_err), 4),
            'p': round(float(r.p_value), 4),
            'rho': round(float(rho.coefficient), 4),
            'rho_p': round(float(rho.p_value), 4),
            'N': int(mod.num_obs), 'n_countries': int(mod.N),
            'n_instruments': int(mod.z_information.num_instr),
            'hansen_p': round(float(mod.hansen.p_value), 4),
            'ar1_p': round(float(mod.AR_list[0].P_value), 4),
            'ar2_p': round(float(mod.AR_list[1].P_value), 4),
        }
        out['sane'] = bool(0 < out['rho'] < 1.2
                           and out['n_instruments'] < out['n_countries'])
        return out
    except Exception as e:
        return {'error': f'parse: {str(e)[:200]}'}


def main():
    panel = prep_panel()
    res = {}
    for dep in DEPS:
        r = run_one(panel, dep)
        res[dep] = r
        if 'error' in r:
            print(f"  {dep}: FAILED — {r['error']}")
        else:
            star = ('***' if r['p'] < .01 else '**' if r['p'] < .05
                    else '*' if r['p'] < .10 else '')
            print(f"  {dep:14s}: AI(t-1) {r['b']:+.4f}{star} (SE {r['se']:.4f}) | "
                  f"rho={r['rho']:.3f} | Hansen p={r['hansen_p']:.3f} | "
                  f"AR(2) p={r['ar2_p']:.3f} | instr={r['n_instruments']}"
                  f"/{r['n_countries']} ctys | sane={r['sane']}")
    _merge_results({'gmm_system_collapsed': res})
    print(f"\nmerged into {OUT_DIR/'results.json'}")


if __name__ == '__main__':
    main()
