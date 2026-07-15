"""
GTFP cross-region pipeline v1 — orchestrator (Paper 2, JCP target).

Steps:
  1. Build 40-country panel (data_build)
  2. Productivity indices: Solow ln(TFP), CRS Malmquist, Malmquist–Luenberger GTFP
  3. Estimation battery:
       3.1 descriptives by region
       3.2 Pesaran CD diagnostics
       3.3 benchmark FE-DK + CCEP for GTFP-ML, Malmquist CRS, Solow
       3.4 regional heterogeneity (interactions + subsamples)
       3.5 moderation (Rule of Law, broadband, mobile, renewables)
       3.6 Canay (2011) quantile on Solow ln(TFP)
       3.7 robustness (contemporaneous vs lagged AI, ln(1+pubs) unnormalised)
Outputs → gtfp_pipeline/output/: merged_panel_with_indices.csv, results.json,
tables/*.csv, summary.txt

System GMM is NOT estimated here (no reliable Python implementation);
run in Stata xtabond2 with collapsed instruments, or add pydynpd later.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import COUNTRIES, OUT_DIR, REGIONS  # noqa: E402
from data_build import build_panel              # noqa: E402
from ml_index import add_productivity_indices   # noqa: E402

TABLES = OUT_DIR / 'tables'
CONTROLS = ['LN_GDP_PC', 'TRADE', 'FDI', 'GOV_CONS', 'URBAN']
RESULTS = {}
LOG_LINES = []


def log(msg=''):
    print(msg)
    LOG_LINES.append(str(msg))


# ═══════════════════════════════════════════════════════════════════════════
# Econometric helpers
# ═══════════════════════════════════════════════════════════════════════════

def _two_way_demean(df, cols, ent='Country', tcol='Year'):
    """Iterative two-way within transformation (converges for unbalanced panels)."""
    z = df[cols].copy()
    for _ in range(50):
        before = z.values.copy()
        z = z - z.groupby(df[ent]).transform('mean')
        z = z - z.groupby(df[tcol]).transform('mean')
        if np.nanmax(np.abs(z.values - before)) < 1e-10:
            break
    return z


def _dk_se(Xd, resid, time_ids, max_lag=None):
    """Driscoll–Kraay SEs, Bartlett kernel, bandwidth floor(T^(1/3))."""
    n, k = Xd.shape
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    times = np.unique(time_ids)
    T = len(times)
    if max_lag is None:
        max_lag = int(np.floor(T ** (1 / 3)))
    h = np.array([Xd[time_ids == t].T @ resid[time_ids == t] for t in times])
    Omega = h.T @ h
    for lag in range(1, min(max_lag, T - 1) + 1):
        w = 1 - lag / (max_lag + 1)
        G = h[lag:].T @ h[:-lag]
        Omega += w * (G + G.T)
    V = XtX_inv @ Omega @ XtX_inv
    return np.sqrt(np.maximum(np.diag(V), 0))


def fe_dk(df, ycol, xcols, ent='Country', tcol='Year'):
    """Two-way FE with Driscoll–Kraay SEs. Returns dict of coef/se/t/p per x."""
    sub = df[[ycol] + xcols + [ent, tcol]].dropna().reset_index(drop=True)
    if sub[ent].nunique() < 5 or len(sub) < 30:
        return None
    zd = _two_way_demean(sub, [ycol] + xcols, ent, tcol)
    y = zd[ycol].values
    X = zd[xcols].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    # df correction for absorbed FE
    n, k = X.shape
    dof = n - k - sub[ent].nunique() - sub[tcol].nunique() + 1
    resid_adj = resid * np.sqrt(n / max(dof, 1))
    se = _dk_se(X, resid_adj, sub[tcol].values)
    tvals = beta / se
    pvals = 2 * stats.t.sf(np.abs(tvals), df=max(dof, 1))
    r2 = 1 - resid.var() / y.var() if y.var() > 0 else np.nan
    return {'coefs': {x: {'b': float(beta[i]), 'se': float(se[i]),
                          't': float(tvals[i]), 'p': float(pvals[i])}
                      for i, x in enumerate(xcols)},
            'N': int(n), 'countries': int(sub[ent].nunique()),
            'R2_within': float(r2), 'resid': resid, 'sub': sub}


def ccep(df, ycol, xcols, ent='Country', tcol='Year'):
    """CCE-pooled (homogeneous loadings): entity FE + cross-sectional averages."""
    sub = df[[ycol] + xcols + [ent, tcol]].dropna().reset_index(drop=True)
    if sub[ent].nunique() < 5 or len(sub) < 30:
        return None
    for v in [ycol] + xcols:
        sub[f'CSA_{v}'] = sub.groupby(tcol)[v].transform('mean')
    csa_cols = [f'CSA_{v}' for v in [ycol] + xcols]
    allc = [ycol] + xcols + csa_cols
    z = sub[allc] - sub[allc].groupby(sub[ent]).transform('mean')
    y = z[ycol].values
    X = z[xcols + csa_cols].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = n - k - sub[ent].nunique()
    se = _dk_se(X, resid * np.sqrt(n / max(dof, 1)), sub[tcol].values)
    tvals = beta / se
    pvals = 2 * stats.t.sf(np.abs(tvals), df=max(dof, 1))
    return {'coefs': {x: {'b': float(beta[i]), 'se': float(se[i]),
                          't': float(tvals[i]), 'p': float(pvals[i])}
                      for i, x in enumerate(xcols)},
            'N': int(n), 'countries': int(sub[ent].nunique())}


def pesaran_cd(resid, ent_ids, time_ids):
    """Pesaran (2004) CD statistic from residuals."""
    d = pd.DataFrame({'e': resid, 'i': ent_ids, 't': time_ids})
    piv = d.pivot_table(index='t', columns='i', values='e')
    cols = piv.columns
    stat_sum, npairs = 0.0, 0
    for a in range(len(cols)):
        for b in range(a + 1, len(cols)):
            pair = piv[[cols[a], cols[b]]].dropna()
            if len(pair) < 3:
                continue
            rho = pair.iloc[:, 0].corr(pair.iloc[:, 1])
            if np.isfinite(rho):
                stat_sum += np.sqrt(len(pair)) * rho
                npairs += 1
    if npairs == 0:
        return np.nan, np.nan
    cd = np.sqrt(1.0 / npairs) * stat_sum
    return float(cd), float(2 * stats.norm.sf(abs(cd)))


def canay_quantile(df, ycol, xcols, taus=(0.10, 0.25, 0.50, 0.75, 0.90),
                   n_boot=200, seed=42):
    """Canay (2011) two-step: purge entity FE, then pooled quantile regression
    with year dummies. Cluster (country) bootstrap SEs. Vectorised resampling."""
    import statsmodels.api as sm
    import warnings
    warnings.filterwarnings('ignore')
    sub = df[[ycol] + xcols + ['Country', 'Year']].dropna().reset_index(drop=True)
    # Step 1: within FE estimate → entity effects
    zd = _two_way_demean(sub, [ycol] + xcols)
    beta1, *_ = np.linalg.lstsq(zd[xcols].values, zd[ycol].values, rcond=None)
    mu = (sub[ycol] - sub[xcols].values @ beta1).groupby(sub['Country']).transform('mean')
    y_star = (sub[ycol] - mu).values
    ydum = pd.get_dummies(sub['Year'], prefix='Y', drop_first=True).astype(float)
    Xmat = np.column_stack([np.ones(len(sub)), sub[xcols].values, ydum.values])
    idx_of = {c: np.where(sub.Country.values == c)[0]
              for c in sub.Country.unique()}
    countries = list(idx_of)
    out = {}
    rng = np.random.default_rng(seed)
    for tau in taus:
        fit = sm.QuantReg(y_star, Xmat).fit(q=tau)
        b = float(fit.params[1])            # first regressor after constant
        boots = []
        for _ in range(n_boot):
            pick = rng.choice(len(countries), size=len(countries), replace=True)
            rows = np.concatenate([idx_of[countries[i]] for i in pick])
            try:
                fb = sm.QuantReg(y_star[rows], Xmat[rows]).fit(q=tau, max_iter=250)
                boots.append(float(fb.params[1]))
            except Exception:
                continue
        se = float(np.std(boots)) if len(boots) > 50 else np.nan
        p = 2 * stats.norm.sf(abs(b / se)) if se and np.isfinite(se) and se > 0 else np.nan
        out[str(tau)] = {'b': b, 'se': se, 'p': float(p) if np.isfinite(p) else None,
                         'n_boot_ok': len(boots)}
    return out


def _merge_results(update):
    """Incrementally merge a dict into output/results.json."""
    path = OUT_DIR / 'results.json'
    cur = json.loads(path.read_text()) if path.exists() else {}
    def deep(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                deep(dst[k], v)
            else:
                dst[k] = v
    deep(cur, update)
    path.write_text(json.dumps(cur, indent=2, default=str))


def fmt(res, xkey):
    if res is None:
        return "n/a"
    c = res['coefs'][xkey]
    star = '***' if c['p'] < .01 else '**' if c['p'] < .05 else '*' if c['p'] < .10 else ''
    return f"{c['b']:+.4f}{star} (SE {c['se']:.4f}, p={c['p']:.3f}, N={res['N']})"


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def prep_panel(force=False):
    """Step 1-2: build panel + indices (cached to CSV)."""
    cache = OUT_DIR / 'merged_panel_with_indices.csv'
    if cache.exists() and not force:
        panel = pd.read_csv(cache)
        if 'LN_AI_L1' in panel.columns:
            print(f"  loaded cached panel: {len(panel)} rows")
            return panel
    panel, _full = build_panel(save=True)
    panel = add_productivity_indices(panel)
    panel['LN_GDP_PC'] = np.log(panel['GDP_PC'])
    panel = panel.sort_values(['Country', 'Year'])
    panel['LN_AI_L1'] = panel.groupby('Country')['LN_AI'].shift(1)
    panel['RENEW_L1'] = panel.groupby('Country')['RENEWABLES'].shift(1)
    for r in ['ASIA', 'AFRICA']:
        panel[f'D_{r}'] = (panel.REGION == r).astype(float)
    panel.to_csv(cache, index=False)
    return panel


def main(stage='all'):
    OUT_DIR.mkdir(exist_ok=True)
    TABLES.mkdir(exist_ok=True)

    panel = prep_panel()
    if stage == 'prep':
        return

    AI = 'LN_AI_L1'          # baseline regressor: lagged ln(1+pubs per million)
    DEPS = {'GTFP_ML': 'Green TFP (Malmquist–Luenberger)',
            'MALM_CRS': 'Conventional Malmquist (CRS)',
            'LN_TFP_SOLOW': 'Solow ln(TFP)'}

    if stage in ('quantile', 'all'):
        log("STEP 3.6 — Canay (2011) quantile, Solow ln(TFP)")
        q = canay_quantile(panel, 'LN_TFP_SOLOW', [AI] + CONTROLS)
        _merge_results({'quantile_solow': q})
        for tau, v in q.items():
            star = ('***' if v['p'] and v['p'] < .01 else
                    '**' if v['p'] and v['p'] < .05 else
                    '*' if v['p'] and v['p'] < .10 else '')
            log(f"  τ={tau}: {v['b']:+.4f}{star} (boot SE {v['se']:.4f})")
        with open(TABLES / 't6_quantile.json', 'w') as f:
            json.dump(q, f, indent=2)
        if stage == 'quantile':
            (OUT_DIR / 'summary_quantile.txt').write_text('\n'.join(LOG_LINES))
            return

    if stage == 'quantile_gtfp':
        log("STEP 3.6b — Canay (2011) quantile, GTFP-ML")
        q = canay_quantile(panel, 'GTFP_ML', [AI] + CONTROLS)
        _merge_results({'quantile_gtfp': q})
        for tau, v in q.items():
            log(f"  τ={tau}: {v['b']:+.4f} (boot SE {v['se']})")
        return

    log("\n" + "═" * 66)
    log("STEP 3.1 — Descriptives by region")
    log("═" * 66)
    desc = panel.groupby('REGION')[['GTFP_ML', 'MALM_CRS', 'LN_TFP_SOLOW',
                                    'LN_AI', 'CO2', 'RULE_OF_LAW',
                                    'BROADBAND', 'RENEWABLES']].describe()
    desc.to_csv(TABLES / 't1_descriptives_by_region.csv')
    simple = panel.groupby('REGION')[['GTFP_ML', 'MALM_CRS', 'LN_TFP_SOLOW',
                                      'LN_AI']].agg(['mean', 'std', 'count']).round(4)
    log(simple.to_string())
    RESULTS['descriptives'] = json.loads(simple.to_json())

    # ----- Step 3.2: CD tests -----
    log("\n" + "═" * 66)
    log("STEP 3.2 — Pesaran CD tests (FE-DK residuals, baseline spec)")
    log("═" * 66)
    RESULTS['cd_tests'] = {}
    for dep in DEPS:
        r = fe_dk(panel, dep, [AI] + CONTROLS)
        if r is None:
            log(f"  {dep}: insufficient data")
            continue
        cd, p = pesaran_cd(r['resid'], r['sub']['Country'].values,
                           r['sub']['Year'].values)
        RESULTS['cd_tests'][dep] = {'CD': round(cd, 3), 'p': round(p, 4)}
        log(f"  {dep:14s}: CD = {cd:6.3f}  (p = {p:.4f})")

    # ----- Step 3.3: benchmark -----
    log("\n" + "═" * 66)
    log(f"STEP 3.3 — Benchmark: {AI} → TFP measures (FE-DK / CCEP)")
    log("═" * 66)
    RESULTS['benchmark'] = {}
    t3 = []
    for dep, label in DEPS.items():
        r1 = fe_dk(panel, dep, [AI] + CONTROLS)
        r2 = ccep(panel, dep, [AI] + CONTROLS)
        RESULTS['benchmark'][dep] = {
            'FE_DK': None if r1 is None else r1['coefs'][AI] | {'N': r1['N']},
            'CCEP': None if r2 is None else r2['coefs'][AI] | {'N': r2['N']}}
        log(f"  {label}")
        log(f"    FE-DK : {fmt(r1, AI)}")
        log(f"    CCEP  : {fmt(r2, AI)}")
        for est, rr in [('FE-DK', r1), ('CCEP', r2)]:
            if rr:
                c = rr['coefs'][AI]
                t3.append({'dep': dep, 'estimator': est, **c, 'N': rr['N']})
    pd.DataFrame(t3).to_csv(TABLES / 't3_benchmark.csv', index=False)

    # ----- Step 3.4: regional heterogeneity -----
    log("\n" + "═" * 66)
    log("STEP 3.4 — Regional heterogeneity")
    log("═" * 66)
    RESULTS['regional'] = {}
    t4 = []
    for dep in DEPS:
        panel['AIxASIA'] = panel[AI] * panel['D_ASIA']
        panel['AIxAFRICA'] = panel[AI] * panel['D_AFRICA']
        r = fe_dk(panel, dep, [AI, 'AIxASIA', 'AIxAFRICA'] + CONTROLS)
        row = {'dep': dep}
        if r:
            log(f"  {dep}: base(LatAm) {fmt(r, AI)}")
            log(f"          + Asia    {fmt(r, 'AIxASIA')}")
            log(f"          + Africa  {fmt(r, 'AIxAFRICA')}")
            row |= {f'{k}_{s}': r['coefs'][k][s] for k in [AI, 'AIxASIA', 'AIxAFRICA']
                    for s in ['b', 'se', 'p']}
        RESULTS['regional'][dep] = row
        # subsamples
        for reg, lst in REGIONS.items():
            rs = fe_dk(panel[panel.Country.isin(lst)], dep, [AI] + CONTROLS)
            if rs:
                log(f"          {reg:6s} only: {fmt(rs, AI)}")
                row[f'sub_{reg}'] = rs['coefs'][AI] | {'N': rs['N']}
        t4.append(row)
    with open(TABLES / 't4_regional.json', 'w') as f:
        json.dump(t4, f, indent=2, default=str)

    # ----- Step 3.5: moderation -----
    log("\n" + "═" * 66)
    log("STEP 3.5 — Moderation (interaction; moderator demeaned)")
    log("═" * 66)
    RESULTS['moderation'] = {}
    mods = {'RULE_OF_LAW': 'Rule of Law', 'BROADBAND': 'Broadband',
            'MOBILE': 'Mobile', 'RENEW_L1': 'Renewables (t-1)'}
    t5 = []
    for dep in DEPS:
        RESULTS['moderation'][dep] = {}
        for mv, mlabel in mods.items():
            p2 = panel.copy()
            p2['MOD'] = p2[mv] - p2[mv].mean()
            p2['AIxMOD'] = p2[AI] * p2['MOD']
            ctrl = [c for c in CONTROLS]
            r = fe_dk(p2, dep, [AI, 'AIxMOD', 'MOD'] + ctrl)
            if r:
                c = r['coefs']['AIxMOD']
                RESULTS['moderation'][dep][mv] = c | {'N': r['N']}
                log(f"  {dep:14s} × {mlabel:16s}: {fmt(r, 'AIxMOD')}")
                t5.append({'dep': dep, 'moderator': mv, **c, 'N': r['N']})
            # median split
            med = p2[mv].median()
            for side, mask in [('below', p2[mv] <= med), ('above', p2[mv] > med)]:
                rr = fe_dk(p2[mask], dep, [AI] + ctrl)
                if rr:
                    RESULTS['moderation'][dep][f'{mv}_{side}'] = \
                        rr['coefs'][AI] | {'N': rr['N']}
    pd.DataFrame(t5).to_csv(TABLES / 't5_moderation.csv', index=False)

    # ----- Step 3.7: robustness -----
    log("\n" + "═" * 66)
    log("STEP 3.7 — Robustness")
    log("═" * 66)
    RESULTS['robustness'] = {}
    panel['LN_AI_RAW'] = np.log1p(panel['AI_PUBS'])
    panel['LN_AI_RAW_L1'] = panel.groupby('Country')['LN_AI_RAW'].shift(1)
    alts = {'contemporaneous LN_AI': ('LN_AI', None),
            'unnormalised ln(1+pubs), lag': ('LN_AI_RAW_L1', None),
            'two-period lag': ('LN_AI_L2', 2)}
    panel['LN_AI_L2'] = panel.groupby('Country')['LN_AI'].shift(2)
    for label, (var, _) in alts.items():
        RESULTS['robustness'][label] = {}
        for dep in DEPS:
            r = fe_dk(panel, dep, [var] + CONTROLS)
            if r:
                RESULTS['robustness'][label][dep] = r['coefs'][var] | {'N': r['N']}
                log(f"  {label:32s} → {dep:14s}: {fmt(r, var)}")
    log("\n  NOTE: collapsed-instrument system GMM not run here — "
        "no reliable Python implementation; use Stata xtabond2 or add pydynpd.")

    # ----- save -----
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()
                    if k not in ('resid', 'sub')}
        if isinstance(o, (np.floating, np.integer)):
            return float(o)
        return o
    _merge_results(_clean(RESULTS))
    (OUT_DIR / 'summary.txt').write_text('\n'.join(LOG_LINES))
    log(f"\nAll outputs → {OUT_DIR}")


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'main'
    main(stage=stage)
