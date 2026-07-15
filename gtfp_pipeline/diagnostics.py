"""
GTFP pipeline — diagnostics pass on v1 results.

D1  Lag structure vs sample composition: is the L2-negative GTFP result a lag
    effect or a composition effect? Re-estimate L0/L1/L2 on the common L2 sample.
D2  ML infeasibility map: which countries/years drive the 17 invalid ML obs.
D3  Environmental margin (H3): GTFP_ML − MALM_CRS wedge by region/year; paired test.
D4  Solow CSD: CD on FE-DK vs CCEP residuals; region-subsample CDs.
D5  Sensitivity: drop-CHN, trim 1% GTFP tails, leave-one-region-out jackknife.
D6  LatAm-only Canay quantile in this panel (does Paper 1's negative gradient
    replicate with publications?) + CCEMG (mean-group) benchmark estimates.

Run: python3 diagnostics.py [d1|d2|d3|d4|d5|d6|all]   (default: all)
Outputs → output/diagnostics/: diagnostics.json (incremental), report lines.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import OUT_DIR, REGIONS                       # noqa: E402
from run_gtfp_v1 import (CONTROLS, _two_way_demean, canay_quantile,  # noqa: E402
                         ccep, fe_dk, pesaran_cd, prep_panel)

DIAG = OUT_DIR / 'diagnostics'
AI = 'LN_AI_L1'
DEPS = ['GTFP_ML', 'MALM_CRS', 'LN_TFP_SOLOW']
LINES = []


def log(msg=''):
    print(msg)
    LINES.append(str(msg))


def save(update):
    DIAG.mkdir(exist_ok=True)
    p = DIAG / 'diagnostics.json'
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur.update(update)
    p.write_text(json.dumps(cur, indent=2, default=str))
    with open(DIAG / 'report.txt', 'a') as f:
        f.write('\n'.join(LINES) + '\n')
    LINES.clear()


def coef(res, key=AI):
    if res is None:
        return None
    c = res['coefs'][key]
    return {'b': round(c['b'], 4), 'se': round(c['se'], 4),
            'p': round(c['p'], 4), 'N': res['N']}


def star(p):
    return '***' if p < .01 else '**' if p < .05 else '*' if p < .10 else ''


def fmtc(c):
    return f"{c['b']:+.4f}{star(c['p'])} (SE {c['se']:.4f}, N={c['N']})" if c else 'n/a'


# ─────────────────────────────────────────────────────────────────────────────

def d1_lag_vs_sample(panel):
    log("D1 — Lag structure vs sample composition")
    out = {}
    panel = panel.sort_values(['Country', 'Year']).copy()
    panel['LN_AI_L2'] = panel.groupby('Country')['LN_AI'].shift(2)
    lag_vars = {'L0': 'LN_AI', 'L1': 'LN_AI_L1', 'L2': 'LN_AI_L2'}
    for dep in DEPS:
        out[dep] = {}
        # full-sample estimates per lag
        for lab, v in lag_vars.items():
            out[dep][f'full_{lab}'] = coef(fe_dk(panel, dep, [v] + CONTROLS), v)
        # common sample: obs where ALL three lags observed
        common = panel.dropna(subset=[dep, 'LN_AI', 'LN_AI_L1', 'LN_AI_L2'] + CONTROLS)
        for lab, v in lag_vars.items():
            out[dep][f'common_{lab}'] = coef(fe_dk(common, dep, [v] + CONTROLS), v)
        log(f"  {dep}")
        for lab in lag_vars:
            log(f"    {lab}: full {fmtc(out[dep][f'full_{lab}'])}   | common-sample "
                f"{fmtc(out[dep][f'common_{lab}'])}")
    log("  READ: if full_L2 is significant but common_L2 is not (or sign differs\n"
        "  from common_L0/L1), the L2 result is composition, not dynamics.")
    save({'d1_lag_vs_sample': out})


def d2_ml_infeasibility(panel):
    log("\nD2 — ML infeasibility map")
    m = panel[panel.Year >= 2017]  # index years
    bad = m[m.GTFP_ML.isna()][['Country', 'Year', 'REGION']]
    by_c = bad.groupby('Country').size().sort_values(ascending=False)
    by_y = bad.groupby('Year').size()
    log(f"  invalid ML obs: {len(bad)} of {len(m)}")
    log("  by country: " + ", ".join(f"{c}({n})" for c, n in by_c.items()))
    log("  by year:    " + ", ".join(f"{y}({n})" for y, n in by_y.items()))
    # CO2/GDP extremity of infeasible countries
    m2 = panel.copy()
    m2['co2_int'] = m2.CO2 / m2.GDP
    ranks = m2.groupby('Country')['co2_int'].mean().rank(pct=True)
    log("  CO2-intensity percentile of infeasible countries: "
        + ", ".join(f"{c}:{ranks.get(c, np.nan):.2f}" for c in by_c.index))
    save({'d2_ml_infeasibility': {'by_country': by_c.to_dict(),
                                  'by_year': {int(k): int(v) for k, v in by_y.items()},
                                  'co2_intensity_pctile':
                                      {c: round(float(ranks.get(c, np.nan)), 3)
                                       for c in by_c.index}}})


def d3_wedge(panel):
    log("\nD3 — Environmental margin: GTFP_ML − MALM_CRS wedge")
    m = panel.dropna(subset=['GTFP_ML', 'MALM_CRS']).copy()
    m['WEDGE'] = m.GTFP_ML - m.MALM_CRS
    out = {'overall': {}}
    t, p = stats.ttest_1samp(m.WEDGE, 0)
    out['overall'] = {'mean': round(float(m.WEDGE.mean()), 5),
                      'sd': round(float(m.WEDGE.std()), 5),
                      't': round(float(t), 3), 'p': round(float(p), 4),
                      'corr_indices': round(float(m.GTFP_ML.corr(m.MALM_CRS)), 3),
                      'N': len(m)}
    log(f"  overall wedge: {out['overall']['mean']:+.5f} "
        f"(t={out['overall']['t']}, p={out['overall']['p']}); "
        f"index correlation {out['overall']['corr_indices']}")
    for reg, g in m.groupby('REGION'):
        t, p = stats.ttest_1samp(g.WEDGE, 0)
        out[reg] = {'mean': round(float(g.WEDGE.mean()), 5),
                    't': round(float(t), 3), 'p': round(float(p), 4), 'N': len(g)}
        log(f"  {reg:7s}: wedge {out[reg]['mean']:+.5f}{star(p)} "
            f"(t={out[reg]['t']}, N={len(g)})")
    # does AI relate to the wedge? (cleaner-vs-faster growth question)
    r = fe_dk(m, 'WEDGE', [AI] + CONTROLS)
    out['ai_on_wedge'] = coef(r)
    log(f"  FE-DK AI(t-1) → wedge: {fmtc(out['ai_on_wedge'])}")
    save({'d3_wedge': out})


def d4_solow_csd(panel):
    log("\nD4 — Solow cross-sectional dependence anatomy")
    out = {}
    r = fe_dk(panel, 'LN_TFP_SOLOW', [AI] + CONTROLS)
    cd, p = pesaran_cd(r['resid'], r['sub'].Country.values, r['sub'].Year.values)
    out['fe_dk'] = {'CD': round(cd, 3), 'p': round(p, 4)}
    # CD after CCE augmentation
    sub = panel[['LN_TFP_SOLOW', AI] + CONTROLS + ['Country', 'Year']].dropna().reset_index(drop=True)
    for v in ['LN_TFP_SOLOW', AI] + CONTROLS:
        sub[f'CSA_{v}'] = sub.groupby('Year')[v].transform('mean')
    csa = [f'CSA_{v}' for v in ['LN_TFP_SOLOW', AI] + CONTROLS]
    z = sub[['LN_TFP_SOLOW', AI] + CONTROLS + csa]
    z = z - z.groupby(sub['Country']).transform('mean')
    X = z[[AI] + CONTROLS + csa].values
    y = z['LN_TFP_SOLOW'].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    cd2, p2 = pesaran_cd(resid, sub.Country.values, sub.Year.values)
    out['cce_augmented'] = {'CD': round(cd2, 3), 'p': round(p2, 4)}
    log(f"  FE-DK residual CD: {out['fe_dk']}   → CCE-augmented: {out['cce_augmented']}")
    # region-subsample CDs
    for reg, lst in REGIONS.items():
        rr = fe_dk(panel[panel.Country.isin(lst)], 'LN_TFP_SOLOW', [AI] + CONTROLS)
        if rr:
            cds, ps = pesaran_cd(rr['resid'], rr['sub'].Country.values,
                                 rr['sub'].Year.values)
            out[f'cd_{reg}'] = {'CD': round(cds, 3), 'p': round(ps, 4)}
            log(f"  {reg:7s} subsample CD: {out[f'cd_{reg}']}")
    save({'d4_solow_csd': out})


def d5_sensitivity(panel):
    log("\nD5 — Sensitivity of the benchmark (AI L1)")
    out = {}
    for dep in DEPS:
        out[dep] = {'baseline': coef(fe_dk(panel, dep, [AI] + CONTROLS))}
        out[dep]['drop_CHN'] = coef(fe_dk(panel[panel.Country != 'CHN'],
                                          dep, [AI] + CONTROLS))
        if dep != 'LN_TFP_SOLOW':
            lo, hi = panel[dep].quantile([.01, .99])
            trimmed = panel[(panel[dep].isna()) | panel[dep].between(lo, hi)]
            out[dep]['trim_1pct'] = coef(fe_dk(trimmed, dep, [AI] + CONTROLS))
        for reg, lst in REGIONS.items():
            out[dep][f'drop_{reg}'] = coef(
                fe_dk(panel[~panel.Country.isin(lst)], dep, [AI] + CONTROLS))
        log(f"  {dep}")
        for k, v in out[dep].items():
            log(f"    {k:12s}: {fmtc(v)}")
    save({'d5_sensitivity': out})


def d6_latam_quantile_ccemg(panel):
    log("\nD6a — LatAm-only Canay quantile (publications), this panel")
    latam = panel[panel.REGION == 'LATAM']
    q = canay_quantile(latam, 'LN_TFP_SOLOW', [AI] + CONTROLS, n_boot=150)
    for tau, v in q.items():
        s = star(v['p']) if v['p'] else ''
        log(f"    τ={tau}: {v['b']:+.4f}{s} (boot SE {v['se']})")
    log("  READ: Paper 1 (patents, 2000-2024) had negative at all τ; this checks\n"
        "  whether the sign difference is measure/window or region composition.")

    log("\nD6b — CCEMG (mean-group with CSAs) benchmark")
    outmg = {}
    for dep in DEPS:
        sub = panel[[dep, AI] + CONTROLS + ['Country', 'Year']].dropna()
        for v in [dep, AI] + CONTROLS:
            sub[f'CSA_{v}'] = sub.groupby('Year')[v].transform('mean')
        csa = [f'CSA_{v}' for v in [dep, AI] + CONTROLS]
        betas = []
        for c, g in sub.groupby('Country'):
            if len(g) < len(CONTROLS) + len(csa) + 3:
                # not enough dof for full country regression: use reduced CSA set
                X = np.column_stack([np.ones(len(g)), g[AI].values,
                                     g[f'CSA_{dep}'].values, g[f'CSA_{AI}'].values])
            else:
                X = np.column_stack([np.ones(len(g)), g[AI].values,
                                     g[CONTROLS].values, g[csa].values])
            try:
                b, *_ = np.linalg.lstsq(X, g[dep].values, rcond=None)
                if np.isfinite(b[1]) and abs(b[1]) < 10:
                    betas.append(b[1])
            except np.linalg.LinAlgError:
                continue
        betas = np.array(betas)
        mg = betas.mean()
        se = betas.std(ddof=1) / np.sqrt(len(betas))
        p = 2 * stats.norm.sf(abs(mg / se))
        outmg[dep] = {'b': round(float(mg), 4), 'se': round(float(se), 4),
                      'p': round(float(p), 4), 'n_countries': int(len(betas))}
        log(f"    {dep:14s}: {mg:+.4f}{star(p)} (MG SE {se:.4f}, "
            f"{len(betas)} country slopes)")
    log("  NOTE: with T=7-8 the country regressions are heavily parameterised;\n"
        "  CCEMG here is indicative, not headline.")
    save({'d6_latam_quantile': q, 'd6_ccemg': outmg})


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    panel = prep_panel()
    steps = {'d1': d1_lag_vs_sample, 'd2': d2_ml_infeasibility, 'd3': d3_wedge,
             'd4': d4_solow_csd, 'd5': d5_sensitivity,
             'd6': d6_latam_quantile_ccemg}
    if which == 'all':
        for f in steps.values():
            f(panel)
    else:
        steps[which](panel)
    print(f"\ndiagnostics → {DIAG}")
