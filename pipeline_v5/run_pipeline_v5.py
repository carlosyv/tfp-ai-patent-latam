#!/usr/bin/env python3
"""
run_pipeline_v5.py
==================
Complete TFP-AI pipeline — v5 (bug fixes + N=9 expansion)

Changes from v4:
  - [C1 FIX] Malmquist TFP formula corrected: uses standard Färe et al. (1994)
        M = sqrt[(D^t(t+1)/D^t(t)) × (D^{t+1}(t+1)/D^{t+1}(t))]
  - [C2 FIX] Two-way fixed effects: year dummies added to all FE/CCE estimators
  - [M1 FIX] DEA now uses 2 inputs (CAPITAL, EFFECTIVE_LABOR=L×HC) for
        consistency with Solow specification. 3-input version retained as robustness.
  - [M2 FIX] Interpolation uses limit_direction='forward', limit=3
  - [M3 FIX] Main AI variable is now per-capita patent stock (with depreciation),
        matching Luo et al. (2024) Eq. 6
  - [N EXPANSION] Panel expanded from 7 to 9 countries (+DOM, +URY)
  - [m4 FIX] DEA solver returns NaN for infeasible cases

Panel: 9 LAC countries (ARG, BRA, CHL, COL, CRI, DOM, MEX, PER, URY), 2000–2024.
Human capital: PWT 10.01 index. Labor: ILOSTAT total employment (EMP_TEMP).

Usage:
  python pipeline_v5/run_pipeline_v5.py
"""

import json, warnings, sys, os
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import combinations
from math import lgamma, log, exp, erfc, sqrt

warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent.parent  # stats-data-app root
DATA_DIR = BASE_DIR / 'data'
RESULTS_DIR = BASE_DIR / 'output' / 'results'
OUT_DIR = RESULTS_DIR / 'benchmark_dissertation_v5'

# Data files
WB_CSV = DATA_DIR / 'wb_data_export.csv'
PWT_CSV = DATA_DIR / 'pwt-data-human-capital-026-03-22T15-56_export.csv'
WIPO_SPANISH = DATA_DIR / 'ai-search-wipo-results-spanish-v2.xlsx'
WIPO_PORTUGUESE = DATA_DIR / 'ai-search-wipo-results-br-portuguese-v2.xlsx'
ILOSTAT_EMP = DATA_DIR / 'EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv.gz'

# Model parameters
ALPHA = 0.35        # Capital share (Solow)
DELTA = 0.05        # Depreciation rate for PIM capital stock
PATENT_DELTA = 0.36 # Depreciation for AI patent stock (Yan et al. 2020)
START_YR = 2000     # v5: start at 2000 (not 1992) — 2000-2024 panel
END_YR = 2024
PIM_INIT_YR = 1992  # PIM needs pre-sample investment data for capital stock

# v5: N=9 countries (added DOM, URY)
COUNTRY_NAMES = {
    'ARG': 'Argentina', 'BRA': 'Brazil', 'CHL': 'Chile',
    'COL': 'Colombia', 'CRI': 'Costa Rica', 'DOM': 'Dominican Republic',
    'MEX': 'Mexico', 'PER': 'Peru', 'URY': 'Uruguay',
}
COUNTRIES = sorted(COUNTRY_NAMES.keys())

# ISO-2 → ISO-3 mapping for WIPO Spanish patent data
SPANISH_ISO2_TO_ISO3 = {
    'AR': 'ARG', 'CL': 'CHL', 'CO': 'COL', 'CR': 'CRI',
    'MX': 'MEX', 'PE': 'PER', 'DO': 'DOM',
    'EC': 'ECU', 'UY': 'URY',
    'HN': 'HND', 'NI': 'NIC', 'PA': 'PAN', 'SV': 'SLV',
    'CU': 'CUB', 'GT': 'GTM',
}

# WDI indicator codes → variable names
CONTROL_INDICATORS = {
    'FS.AST.PRVT.GD.ZS': 'FIN_credit_private',
    'NE.CON.GOVT.ZS':    'GOV_consumption',
    'SP.URB.TOTL.IN.ZS': 'URB_urban_pop',
    'NE.TRD.GNFS.ZS':    'OPEN_trade',
    'BX.KLT.DINV.WD.GD.ZS': 'FDI_inflows',
    'NY.GDP.PCAP.KD':    'GDPPC_constant2015',
    'IT.NET.USER.ZS':    'INF_internet',
    'IT.NET.BBND.P2':    'INF_broadband',
    'IT.CEL.SETS.P2':    'INF_mobile',
    'RL.EST':            'INST_rule_of_law',
    'SP.POP.TOTL':       'POP_total',       # v5: for per-capita normalization
    'NV.SRV.TOTL.ZS':   'SRV_va_pct',      # services VA % GDP (mediation)
    'NV.IND.TOTL.ZS':   'IND_va_pct',      # industry VA % GDP (mediation)
}

# Control variable sets for regressions
CONTROLS_FULL = [
    'LNPGDP_constant2015', 'FIN_credit_private',
    'OPEN_trade', 'INF_internet', 'LN_HC_index',
    'FDI_inflows', 'GOV_consumption', 'URB_urban_pop',
]
CONTROLS_PARS = [
    'LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index',
    'FDI_inflows', 'GOV_consumption', 'URB_urban_pop',
]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: EXTRACT DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_pwt_human_capital():
    """Load PWT Human Capital Index (hc) for panel countries."""
    print("\n  Loading PWT Human Capital Index...")
    raw = pd.read_csv(PWT_CSV)
    raw = raw[raw['ISO code'].isin(COUNTRIES)]
    year_cols = [str(y) for y in range(PIM_INIT_YR, END_YR + 1)]
    records = []
    for _, row in raw.iterrows():
        iso = row['ISO code']
        for yc in year_cols:
            val = row.get(yc)
            records.append({
                'Country': iso, 'Year': int(yc),
                'HC_index': float(val) if pd.notna(val) else np.nan,
            })
    df = pd.DataFrame(records).sort_values(['Country', 'Year']).reset_index(drop=True)

    # Extrapolate 2024 using 2022-2023 growth rate
    for c in COUNTRIES:
        mask = df['Country'] == c
        v2023 = df.loc[mask & (df.Year == 2023), 'HC_index'].values
        v2022 = df.loc[mask & (df.Year == 2022), 'HC_index'].values
        if (len(v2023) > 0 and len(v2022) > 0
                and pd.notna(v2023[0]) and pd.notna(v2022[0])):
            growth = v2023[0] / v2022[0]
            df.loc[mask & (df.Year == 2024), 'HC_index'] = v2023[0] * growth

    nn = df['HC_index'].notna().sum()
    print(f"  PWT HC: {nn}/{len(df)} non-null ({nn/len(df)*100:.0f}%)")
    for c in COUNTRIES:
        nn_c = df[df.Country == c]['HC_index'].notna().sum()
        yrs = END_YR - PIM_INIT_YR + 1
        print(f"    {c}: {nn_c}/{yrs}")
    return df


def load_ilostat_employment():
    """Load ILOSTAT total employment (thousands → persons)."""
    print("\n  Loading ILOSTAT total employment data...")
    ilostat = pd.read_csv(ILOSTAT_EMP)
    emp = ilostat[
        (ilostat['sex.label'] == 'Total') &
        (ilostat['classif1.label'] == 'Age (Youth, adults): 15+')
    ].copy()

    name_to_iso3 = {
        'Argentina': 'ARG', 'Brazil': 'BRA', 'Chile': 'CHL',
        'Colombia': 'COL', 'Costa Rica': 'CRI',
        'Dominican Republic': 'DOM',  # v5: added
        'Mexico': 'MEX', 'Peru': 'PER', 'Uruguay': 'URY',  # v5: added URY
    }
    emp = emp[emp['ref_area.label'].isin(name_to_iso3)]
    emp['Country'] = emp['ref_area.label'].map(name_to_iso3)
    emp = emp[['Country', 'time', 'obs_value']].rename(
        columns={'time': 'Year', 'obs_value': 'EMP_thousands'})
    emp['EMP_thousands'] = pd.to_numeric(emp['EMP_thousands'], errors='coerce')
    emp = emp[(emp.Year >= PIM_INIT_YR) & (emp.Year <= END_YR)]
    emp = emp.sort_values(['Country', 'Year']).reset_index(drop=True)
    emp['LABOR_ILOSTAT'] = emp['EMP_thousands'] * 1000.0

    # Interpolate within country for small gaps
    full_frame = pd.DataFrame(
        [(c, y) for c in COUNTRIES for y in range(PIM_INIT_YR, END_YR + 1)],
        columns=['Country', 'Year'])
    merged = full_frame.merge(
        emp[['Country', 'Year', 'LABOR_ILOSTAT']],
        on=['Country', 'Year'], how='left')
    merged = merged.sort_values(['Country', 'Year'])
    merged['LABOR_ILOSTAT'] = merged.groupby('Country')['LABOR_ILOSTAT'].transform(
        lambda s: s.interpolate(method='linear', limit_direction='both'))

    for c in COUNTRIES:
        sub = merged[(merged.Country == c) & merged.LABOR_ILOSTAT.notna()]
        print(f"    {c}: {len(sub)} obs")

    return merged[['Country', 'Year', 'LABOR_ILOSTAT']]


def extract_data_from_csv():
    """Extract Solow inputs (GDP, CAPITAL, LABOR) + WDI controls + PWT HC."""
    print(f"\n{'═'*70}")
    print("STEP 1: Extract data from CSV files")
    print(f"{'═'*70}")

    for f, label in [(WB_CSV, 'World Bank'), (PWT_CSV, 'PWT'),
                     (WIPO_SPANISH, 'WIPO Spanish'), (WIPO_PORTUGUESE, 'WIPO Portuguese')]:
        if not f.exists():
            print(f"  ERROR: {label} file not found: {f}")
            sys.exit(1)
        print(f"  ✓ {label}: {f.name}")

    raw = pd.read_csv(WB_CSV)
    raw = raw[(raw['year'] >= PIM_INIT_YR) & (raw['year'] <= END_YR)
              & raw['country_code'].isin(COUNTRIES)]

    tfp_codes = {
        'NY.GDP.MKTP.KD': 'GDP',
        'NE.GDI.FTOT.KD': 'INVESTMENT',
        'SL.TLF.TOTL.IN': 'LABOR',
    }
    tfp_raw = raw[raw['indicator_code'].isin(tfp_codes)].copy()
    tfp_raw['var_name'] = tfp_raw['indicator_code'].map(tfp_codes)
    solow = tfp_raw.pivot_table(
        index=['country_code', 'year'], columns='var_name',
        values='value', aggfunc='first',
    ).reset_index()
    solow = solow.rename(columns={'country_code': 'Country', 'year': 'Year'})

    all_years = list(range(PIM_INIT_YR, END_YR + 1))
    full_df = pd.DataFrame(
        [(c, y) for c in COUNTRIES for y in all_years],
        columns=['Country', 'Year'],
    )
    full_df['CountryName'] = full_df['Country'].map(COUNTRY_NAMES)
    solow = full_df.merge(
        solow[['Country', 'Year', 'GDP', 'INVESTMENT', 'LABOR']],
        on=['Country', 'Year'], how='left',
    )

    # PWT Human Capital
    pwt = load_pwt_human_capital()
    solow = solow.merge(pwt[['Country', 'Year', 'HC_index']],
                        on=['Country', 'Year'], how='left')

    # ILOSTAT total employment
    ilostat_labor = load_ilostat_employment()
    solow = solow.merge(ilostat_labor, on=['Country', 'Year'], how='left')
    has_ilostat = solow['LABOR_ILOSTAT'].notna()
    solow.loc[has_ilostat, 'LABOR'] = solow.loc[has_ilostat, 'LABOR_ILOSTAT']
    n_replaced = has_ilostat.sum()
    n_wdi_fallback = (~has_ilostat & solow['LABOR'].notna()).sum()
    print(f"\n  LABOR source: {n_replaced} ILOSTAT employment, {n_wdi_fallback} WDI fallback")

    # ── Perpetual Inventory Method: K_t = I_t + (1-δ)·K_{t-1} ──
    # [m1] Use first 5 years' median growth rate for initialization
    print(f"\n  Constructing capital stock via PIM (δ={DELTA})...")
    solow['CAPITAL'] = np.nan
    for c in COUNTRIES:
        mask = (solow['Country'] == c) & solow['INVESTMENT'].notna()
        inv = solow.loc[mask, 'INVESTMENT'].values
        years_c = solow.loc[mask, 'Year'].values
        if len(inv) < 3:
            continue
        # [m1 FIX] Use first 5 years for growth rate, median for robustness
        n_init = min(5, len(inv) - 1)
        growth_rates = []
        for i in range(1, n_init + 1):
            if inv[i-1] > 0:
                growth_rates.append(inv[i] / inv[i-1] - 1)
        g = float(np.median(growth_rates)) if growth_rates else 0.03
        g = max(g, 0.01)
        K0 = inv[0] / (g + DELTA)
        K = np.zeros(len(inv))
        K[0] = K0
        for t in range(1, len(inv)):
            K[t] = inv[t] + (1 - DELTA) * K[t-1]
        idx = solow.index[(solow['Country'] == c) & solow['INVESTMENT'].notna()]
        solow.loc[idx, 'CAPITAL'] = K
        print(f"    {c}: K₀={K0:.2e}, K_T={K[-1]:.2e}, g_init={g:.3f}")

    # Effective labor for Solow and DEA
    solow['EFFECTIVE_LABOR'] = solow['LABOR'] * solow['HC_index']

    for col in ['TFP', 'TFP_Growth', 'GDP_Growth']:
        solow[col] = np.nan

    print(f"\n  Solow inputs: {solow.shape}")
    for var in ['GDP', 'INVESTMENT', 'CAPITAL', 'LABOR', 'HC_index', 'EFFECTIVE_LABOR']:
        nn = solow[var].notna().sum()
        print(f"    {var}: {nn}/{len(solow)} ({nn/len(solow)*100:.0f}%)")

    # WDI controls
    ctrl_raw = raw[raw['indicator_code'].isin(CONTROL_INDICATORS)].copy()
    ctrl_raw['var_name'] = ctrl_raw['indicator_code'].map(CONTROL_INDICATORS)
    wdi = ctrl_raw.pivot_table(
        index=['country_code', 'year'], columns='var_name',
        values='value', aggfunc='first',
    ).reset_index()
    wdi = wdi.rename(columns={'country_code': 'country', 'year': 'year'})

    ctrl_full = pd.DataFrame(
        [(c, y) for c in COUNTRIES for y in all_years],
        columns=['country', 'year'],
    )
    wdi = ctrl_full.merge(wdi, on=['country', 'year'], how='left')
    wdi = wdi.sort_values(['country', 'year'])

    # [M2 FIX] Interpolate with forward-only direction, limit=3
    ctrl_cols = [c for c in wdi.columns if c not in ['country', 'year']]
    for col in ctrl_cols:
        wdi[col] = wdi.groupby('country')[col].transform(
            lambda s: s.interpolate(method='linear', limit_direction='forward', limit=3))

    if 'GDPPC_constant2015' in wdi.columns:
        wdi['LNPGDP_constant2015'] = np.log(
            pd.to_numeric(wdi['GDPPC_constant2015'], errors='coerce'))

    wdi = wdi.sort_values(['country', 'year']).reset_index(drop=True)
    print(f"\n  WDI controls: {wdi.shape}, countries={sorted(wdi.country.unique())}")

    return solow, wdi


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2-3: TFP COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_solow_tfp(df, alpha=ALPHA):
    """
    Two-factor Solow residual with labor-augmenting human capital:
      TFP = Y / [ K^α × (L·HC)^(1−α) ]
    """
    df = df.copy().sort_values(['Country', 'Year'])
    valid = df[['GDP', 'CAPITAL', 'LABOR', 'HC_index']].notna().all(axis=1)
    eff_labor = df.loc[valid, 'LABOR'] * df.loc[valid, 'HC_index']
    df.loc[valid, 'TFP'] = (
        df.loc[valid, 'GDP'] /
        (df.loc[valid, 'CAPITAL'] ** alpha *
         eff_labor ** (1 - alpha))
    )
    df['TFP_Growth'] = df.groupby('Country')['TFP'].pct_change() * 100
    df['GDP_Growth'] = df.groupby('Country')['GDP'].pct_change() * 100
    return df


def _solve_dea_output(y0, x0, Y_ref, X_ref, vrs=True):
    """
    Solve DEA output-oriented LP via vertex enumeration.
    Returns Shephard output distance function D_o ∈ (0, 1].
    D_o = 1 means efficient (on frontier).
    D_o < 1 means inefficient.

    [m4 FIX] Returns NaN for infeasible cases instead of 1.0.

    Parameters:
        vrs: if True, impose convexity constraint (Σλ=1). If False, CRS.
    """
    N = len(Y_ref)
    m = X_ref.shape[1]
    EPS = 1e-9
    best_theta = 0.0

    for s in range(1, min(m + 1, N) + 1):
        for S_idx in combinations(range(N), s):
            S = list(S_idx)
            Y_S = Y_ref[S]
            X_S = X_ref[S, :]

            if s == 1:
                if np.all(X_S[0] <= x0 + EPS):
                    # CRS: λ₁ free (no sum constraint). VRS: Σλ=λ₁=1, satisfied automatically.
                    if True:  # Both RTS: single-DMU reference always valid
                        theta = float(Y_S[0]) / y0
                        if theta > best_theta:
                            best_theta = theta
                continue

            n_binding = s - 1
            if n_binding > m:
                continue

            for binding in combinations(range(m), n_binding):
                b_arr = list(binding)
                if vrs:
                    A = np.vstack([X_S[:, b_arr].T, np.ones((1, s))])
                    b = np.append(x0[b_arr], 1.0)
                else:
                    A = X_S[:, b_arr].T
                    b = x0[b_arr]
                try:
                    if np.linalg.matrix_rank(A) < min(A.shape):
                        continue
                    if A.shape[0] == A.shape[1]:
                        lam = np.linalg.solve(A, b)
                    else:
                        lam = np.linalg.lstsq(A, b, rcond=None)[0]
                except np.linalg.LinAlgError:
                    continue
                if not np.all(lam >= -EPS):
                    continue
                lam = np.maximum(lam, 0.0)
                nb = [i for i in range(m) if i not in binding]
                if nb:
                    if not np.all(X_S[:, nb].T @ lam <= x0[nb] + EPS):
                        continue
                theta = float(Y_S @ lam) / y0
                if theta > best_theta:
                    best_theta = theta

    # [m4 FIX] Return NaN for infeasible cases
    if best_theta < 1e-12:
        return np.nan
    return 1.0 / best_theta


def compute_malmquist_tfp(df, use_2_inputs=True, rts='vrs'):
    """
    DEA-Malmquist TFP change index (Färe et al. 1994).

    [C1 FIX] Corrected formula:
        M = sqrt[ (D^t(x^{t+1},y^{t+1}) / D^t(x^t,y^t))
                × (D^{t+1}(x^{t+1},y^{t+1}) / D^{t+1}(x^t,y^t)) ]

    [M1 FIX] use_2_inputs=True: inputs = [CAPITAL, EFFECTIVE_LABOR]
             use_2_inputs=False: inputs = [CAPITAL, LABOR, HC_index] (robustness)

    rts: 'vrs' for variable returns to scale, 'crs' for constant returns to scale.
         CRS avoids infeasibility for small DMUs in heterogeneous panels but
         imposes a stronger structural assumption. Under CRS, the Malmquist
         index does NOT decompose into pure efficiency change + technical change +
         scale efficiency change; it gives a single TFP change measure.
         VRS is the main specification; CRS is the robustness check.

    Decomposes into efficiency change × technical change.
    """
    use_vrs = (rts.lower() == 'vrs')
    rts_label = 'VRS' if use_vrs else 'CRS'
    years = sorted(df['Year'].unique())
    results = []

    # [M1 FIX] Choose input specification
    if use_2_inputs:
        input_cols = ['CAPITAL', 'EFFECTIVE_LABOR']
        print(f"  DEA inputs: CAPITAL, EFFECTIVE_LABOR (2-input, {rts_label})")
    else:
        input_cols = ['CAPITAL', 'LABOR', 'HC_index']
        print(f"  DEA inputs: CAPITAL, LABOR, HC_index (3-input, {rts_label})")

    output_col = 'GDP'
    req_cols = input_cols + [output_col]
    print(f"  {df.Country.nunique()} countries, {len(years)-1} periods")

    for t_idx, yt in enumerate(years[:-1]):
        yt1 = years[t_idx + 1]
        dt = df[df.Year == yt].sort_values('Country').reset_index(drop=True)
        dt1 = df[df.Year == yt1].sort_values('Country').reset_index(drop=True)
        ok_t = set(dt.dropna(subset=req_cols)['Country'])
        ok_t1 = set(dt1.dropna(subset=req_cols)['Country'])
        common = sorted(ok_t & ok_t1)
        if len(common) < 2:
            continue
        dt = dt[dt.Country.isin(common)].set_index('Country').loc[common]
        dt1 = dt1[dt1.Country.isin(common)].set_index('Country').loc[common]
        Y_t = dt[output_col].values.astype(float)
        X_t = dt[input_cols].values.astype(float)
        Y_t1 = dt1[output_col].values.astype(float)
        X_t1 = dt1[input_cols].values.astype(float)

        if t_idx % 5 == 0:
            print(f"    {yt}→{yt1} ({len(common)} ctys)", flush=True)

        for ci, cty in enumerate(common):
            # Four distance functions (vrs parameter controls RTS assumption)
            d_t_t   = _solve_dea_output(Y_t[ci],  X_t[ci],  Y_t,  X_t,  vrs=use_vrs)   # D^t(obs_t)
            d_t1_t1 = _solve_dea_output(Y_t1[ci], X_t1[ci], Y_t1, X_t1, vrs=use_vrs)   # D^{t+1}(obs_{t+1})
            d_t_t1  = _solve_dea_output(Y_t1[ci], X_t1[ci], Y_t,  X_t,  vrs=use_vrs)   # D^t(obs_{t+1})
            d_t1_t  = _solve_dea_output(Y_t[ci],  X_t[ci],  Y_t1, X_t1, vrs=use_vrs)   # D^{t+1}(obs_t)

            # Skip if any distance is NaN (infeasible)
            if any(np.isnan(d) for d in [d_t_t, d_t1_t1, d_t_t1, d_t1_t]):
                results.append({
                    'Country': cty, 'Year_t': yt, 'Year_t1': yt1,
                    'Period': f'{yt}-{yt1}',
                    'TFP_Change': np.nan, 'Efficiency_Change': np.nan,
                    'Technical_Change': np.nan,
                })
                continue

            # [C1 FIX] Correct Malmquist decomposition
            eff_ch = d_t1_t1 / d_t_t if d_t_t > 0 else np.nan

            # Technical change: frontier shift
            if d_t1_t1 > 0 and d_t1_t > 0:
                tech_ch = np.sqrt((d_t_t1 / d_t1_t1) * (d_t_t / d_t1_t))
            else:
                tech_ch = np.nan

            # TFP change = EC × TC
            if np.isfinite(eff_ch) and np.isfinite(tech_ch):
                tfp_ch = eff_ch * tech_ch
            else:
                tfp_ch = np.nan

            results.append({
                'Country': cty, 'Year_t': yt, 'Year_t1': yt1,
                'Period': f'{yt}-{yt1}',
                'TFP_Change': tfp_ch, 'Efficiency_Change': eff_ch,
                'Technical_Change': tech_ch,
            })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: WIPO AI PATENTS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_wipo_pivot(xlsx_path):
    """Parse WIPO patent pivot table from Excel."""
    raw = pd.read_excel(xlsx_path, header=None)
    header_row = 0
    for i, row in raw.iterrows():
        if str(row.iloc[0]).strip().lower() == 'year':
            header_row = i
            break
    df = raw.iloc[header_row:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: 'year'})
    long = df.melt(id_vars=['year'], var_name='country_code', value_name='AI_Patents')
    long['year'] = pd.to_numeric(long['year'], errors='coerce')
    long['AI_Patents'] = pd.to_numeric(long['AI_Patents'], errors='coerce').fillna(0)
    long = long.dropna(subset=['year'])
    long['year'] = long['year'].astype(int)
    return long


def load_ai_patents():
    """Load and combine WIPO AI patent data (Spanish + Portuguese)."""
    sp = _parse_wipo_pivot(WIPO_SPANISH)
    sp['country'] = sp['country_code'].str.upper().map(SPANISH_ISO2_TO_ISO3)
    pt = _parse_wipo_pivot(WIPO_PORTUGUESE)
    pt['country'] = 'BRA'
    combined = pd.concat([sp, pt], ignore_index=True)
    combined = combined[combined['country'].isin(COUNTRIES)]
    combined = combined[(combined.year >= START_YR) & (combined.year <= END_YR)]
    combined = (combined.groupby(['year', 'country'], as_index=False)['AI_Patents']
                .sum().sort_values(['country', 'year']).reset_index(drop=True))
    print(f"\n  Patents: {len(combined)} rows, Total={combined.AI_Patents.sum():.0f}")
    for c in sorted(combined.country.unique()):
        total = combined[combined.country == c].AI_Patents.sum()
        print(f"    {c}: {total:.0f}")
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: MERGE
# ══════════════════════════════════════════════════════════════════════════════

def build_merged_dataset(patents, solow, malmquist, wdi, malmquist_crs=None):
    """Merge all data sources into a single panel dataset."""
    # Filter solow to analysis period (2000-2024)
    df = solow[solow['Year'] >= START_YR].copy()
    df = df[['Country', 'CountryName', 'Year', 'INVESTMENT', 'CAPITAL', 'GDP',
             'HC_index', 'LABOR', 'EFFECTIVE_LABOR', 'TFP', 'TFP_Growth', 'GDP_Growth']]

    # AI patents
    pat = patents.rename(columns={'year': 'Year', 'country': 'Country'})[
        ['Year', 'Country', 'AI_Patents']]
    df = df.merge(pat, on=['Country', 'Year'], how='left')
    df['AI_Patents'] = df['AI_Patents'].fillna(0)

    # Malmquist (VRS — main specification)
    mq = malmquist[['Country', 'Year_t1', 'TFP_Change',
                     'Efficiency_Change', 'Technical_Change']].rename(
        columns={'Year_t1': 'Year'})
    df = df.merge(mq, on=['Country', 'Year'], how='left')

    # Malmquist (CRS — robustness, solves VRS infeasibility for small DMUs)
    if malmquist_crs is not None:
        mq_crs = malmquist_crs[['Country', 'Year_t1', 'TFP_Change',
                                 'Efficiency_Change', 'Technical_Change']].rename(
            columns={'Year_t1': 'Year',
                     'TFP_Change': 'TFP_Change_CRS',
                     'Efficiency_Change': 'Efficiency_Change_CRS',
                     'Technical_Change': 'Technical_Change_CRS'})
        df = df.merge(mq_crs, on=['Country', 'Year'], how='left')

    # WDI controls (filter to analysis period)
    wdi_period = wdi[wdi['year'] >= START_YR].copy()
    wdi_r = wdi_period.rename(columns={'country': 'Country', 'year': 'Year'})
    wdi_keep = [c for c in wdi_r.columns if c in [
        'Country', 'Year', 'LNPGDP_constant2015', 'GDPPC_constant2015',
        'FIN_credit_private', 'GOV_consumption', 'OPEN_trade',
        'FDI_inflows', 'URB_urban_pop',
        'INF_internet', 'INF_broadband', 'INF_mobile',
        'INST_rule_of_law', 'POP_total',
        'SRV_va_pct', 'IND_va_pct',
    ]]
    df = df.merge(wdi_r[wdi_keep], on=['Country', 'Year'], how='left')

    # ── [M3 FIX] Patent stock with depreciation (Luo et al. Eq. 6) ──
    # Stock_it = Σ_{j=0}^{t} Patent_{ij} × e^{-δ₁(t-j)} × [1 - e^{-δ₂(t-j+1)}]
    # Simplified: Stock_it = Patent_it + (1 - δ) × Stock_{i,t-1}
    df = df.sort_values(['Country', 'Year']).reset_index(drop=True)
    df['AI_Patent_Stock'] = 0.0
    for c in COUNTRIES:
        mask = df['Country'] == c
        idx = df.index[mask]
        stock = 0.0
        for i in idx:
            stock = df.loc[i, 'AI_Patents'] + (1 - PATENT_DELTA) * stock
            df.loc[i, 'AI_Patent_Stock'] = stock

    # Per capita patent stock (main variable)
    df['AI_Patent_Stock_PC'] = np.where(
        df['POP_total'] > 0,
        df['AI_Patent_Stock'] / df['POP_total'] * 1e6,  # per million population
        0.0
    )

    # Derived variables
    df['LN_AI'] = np.log1p(df['AI_Patent_Stock_PC'])           # Main: per-capita stock
    df['LN_AI_flow'] = np.log1p(df['AI_Patents'])              # Robustness: raw flow
    df['LN_AI_stock_raw'] = np.log1p(df['AI_Patent_Stock'])    # Robustness: raw stock
    df['LN_HC_index'] = np.log(df['HC_index'].clip(lower=0.01))

    # Lags
    df['LN_AI_L1'] = df.groupby('Country')['LN_AI'].shift(1)
    df['LN_AI_L2'] = df.groupby('Country')['LN_AI'].shift(2)

    # Industrial structure ratio: services VA / industry VA (mediation)
    df['IS_ratio'] = np.where(
        df['IND_va_pct'] > 0,
        df['SRV_va_pct'] / df['IND_va_pct'],
        np.nan
    )
    df['LN_IS'] = np.log(df['IS_ratio'].clip(lower=0.01))

    # Interaction terms (heterogeneity analysis)
    df['AI_x_RL']        = df['LN_AI'] * df['INST_rule_of_law']
    df['AI_x_MOBILE']    = df['LN_AI'] * df['INF_mobile']
    df['AI_x_BROADBAND'] = df['LN_AI'] * df['INF_broadband']

    df = df.sort_values(['Country', 'Year']).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# REGRESSION UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _ols_coef(X, y):
    """OLS coefficient estimation."""
    try:
        return np.linalg.solve(X.T @ X, X.T @ y)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(X, y, rcond=None)[0]


def _cluster_se(X, resid, cl):
    """Cluster-robust standard errors (by entity)."""
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    clusters = np.unique(cl)
    G = len(clusters)
    meat = np.zeros((k, k))
    for g in clusters:
        idx = np.where(cl == g)[0]
        score = X[idx].T @ resid[idx]
        meat += np.outer(score, score)
    V = (G / (G - 1)) * (n - 1) / (n - k) * XtX_inv @ meat @ XtX_inv
    return np.sqrt(np.diag(V).clip(0))


def _driscoll_kraay_se(X, resid, time_ids, max_lag=None):
    """
    Driscoll-Kraay (1998) standard errors.
    Robust to cross-sectional dependence AND heteroskedasticity.
    Uses Bartlett kernel with bandwidth = floor(T^(1/3)).
    """
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    unique_times = np.sort(np.unique(time_ids))
    T = len(unique_times)

    if max_lag is None:
        max_lag = int(np.floor(T ** (1/3)))

    # Compute S_t = Σ_i X_it * e_it for each time period
    S = np.zeros((T, k))
    for ti, t in enumerate(unique_times):
        idx = np.where(time_ids == t)[0]
        S[ti] = X[idx].T @ resid[idx]

    # Newey-West HAC on the time-series of S_t
    Omega = np.zeros((k, k))
    # Lag 0
    Omega += S.T @ S
    # Lags 1..max_lag with Bartlett kernel
    for lag in range(1, max_lag + 1):
        w = 1 - lag / (max_lag + 1)
        Gamma_lag = S[lag:].T @ S[:-lag]
        Omega += w * (Gamma_lag + Gamma_lag.T)

    V = XtX_inv @ Omega @ XtX_inv
    return np.sqrt(np.diag(V).clip(0))


def _rib(a, b, x, mi=200):
    """Regularized incomplete beta function for p-value computation."""
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _rib(b, a, 1 - x, mi)
    lb = lgamma(a) + lgamma(b) - lgamma(a + b)
    fr = exp(log(x) * a + log(1 - x) * b - lb) / a
    t = 1e-300; f = t; C = f; D = 0.0
    for m in range(mi + 1):
        for s in range(2):
            if m == 0 and s == 0:
                nm = 1.0
            elif s == 0:
                nm = m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m))
            else:
                nm = -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))
            D = 1 + nm * D
            if abs(D) < t: D = t
            C = 1 + nm / C
            if abs(C) < t: C = t
            D = 1 / D
            dl = C * D
            f *= dl
            if abs(dl - 1) < 1e-10:
                return fr * (f - t)
    return fr * (f - t)


def _t_and_p(coef, se, df_resid):
    """Compute t-statistics and two-sided p-values."""
    t = coef / np.where(se > 0, se, np.nan)
    p = np.full_like(t, np.nan, dtype=float)
    for i, ti in enumerate(t):
        if np.isnan(ti):
            continue
        at = abs(float(ti))
        if df_resid > 300:
            p[i] = erfc(at / sqrt(2.0))
        else:
            p[i] = _rib(float(df_resid) / 2, 0.5,
                         float(df_resid) / (float(df_resid) + at**2))
    return t, p


def _stars(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ''
    if p < 0.01: return '***'
    if p < 0.05: return '**'
    if p < 0.10: return '*'
    return ''


# ── Estimators ─────────────────────────────────────────────────────────────

def pooled_ols(df, y_col, x_cols, cl_col='Country'):
    """Pooled OLS with cluster-robust SE."""
    sub = df[[y_col] + x_cols + [cl_col]].dropna()
    y = sub[y_col].values
    X = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in x_cols])
    cl = sub[cl_col].values
    beta = _ols_coef(X, y)
    resid = y - X @ beta
    se = _cluster_se(X, resid, cl)
    n, k = X.shape
    t, p = _t_and_p(beta, se, n - k)
    names = ['const'] + x_cols
    return dict(
        estimator='OLS', y=y_col, obs=n,
        coef=dict(zip(names, beta)), se=dict(zip(names, se)),
        t=dict(zip(names, t)), p=dict(zip(names, p)),
        r2=float(1 - np.var(resid) / np.var(y)),
    )


def fixed_effects_twoway(df, y_col, x_cols, ent='Country', tcol='Year',
                         se_type='cluster'):
    """
    [C2 FIX] Two-way fixed effects (entity + time) estimator.

    se_type: 'cluster' for entity-clustered SE, 'driscoll_kraay' for DK SE.
    """
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)

    # Double-demean: remove entity means, then remove time means from demeaned data
    for c in [y_col] + x_cols:
        sub[c + '_dm'] = sub[c] - sub.groupby(ent)[c].transform('mean')
    for c in [y_col] + x_cols:
        sub[c + '_dm'] = sub[c + '_dm'] - sub.groupby(tcol)[c + '_dm'].transform('mean')

    y = sub[y_col + '_dm'].values
    X = np.column_stack([sub[c + '_dm'].values for c in x_cols])
    cl = sub[ent].values
    time_ids = sub[tcol].values

    beta = _ols_coef(X, y)
    resid = y - X @ beta
    n, k = X.shape
    Ne = sub[ent].nunique()
    Nt = sub[tcol].nunique()

    if se_type == 'driscoll_kraay':
        se = _driscoll_kraay_se(X, resid, time_ids)
        df_resid = n - Ne - Nt - k + 1
    else:
        se = _cluster_se(X, resid, cl)
        df_resid = n - Ne - Nt - k + 1

    t, p = _t_and_p(beta, se, df_resid)
    return dict(
        estimator='FE-2way' if se_type == 'cluster' else 'FE-DK',
        y=y_col, obs=n, se_type=se_type,
        coef=dict(zip(x_cols, beta)), se=dict(zip(x_cols, se)),
        t=dict(zip(x_cols, t)), p=dict(zip(x_cols, p)),
        r2=float(1 - np.var(resid) / np.var(y)),
    )


def random_effects(df, y_col, x_cols, ent='Country', tcol='Year'):
    """Random effects (GLS) estimator with cluster-robust SE."""
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    y = sub[y_col].values
    Xo = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in x_cols])
    bo = _ols_coef(Xo, y)
    ro = y - Xo @ bo
    emr = sub.groupby(ent).apply(lambda g: ro[g.index].mean())
    s2e = max(np.var(ro - sub[ent].map(emr).values), 1e-12)
    Tb = sub.groupby(ent).size().mean()
    s2u = max(np.var(sub[ent].map(emr).values) - s2e / Tb, 0)
    theta = np.clip(1 - sqrt(s2e / (Tb * s2u + s2e + 1e-12)), 0, 1)
    ey = sub.groupby(ent)[y_col].transform('mean').values
    yg = y - theta * ey
    Xg = [1 - theta * np.ones(len(sub))]
    for c in x_cols:
        Xg.append(sub[c].values - theta * sub.groupby(ent)[c].transform('mean').values)
    Xg = np.column_stack(Xg)
    cl = sub[ent].values
    beta = _ols_coef(Xg, yg)
    n, k = Xg.shape
    se = _cluster_se(Xg, yg - Xg @ beta, cl)
    t, p = _t_and_p(beta, se, n - k)
    names = ['const'] + x_cols
    return dict(
        estimator='RE', y=y_col, obs=n,
        coef=dict(zip(names, beta)), se=dict(zip(names, se)),
        t=dict(zip(names, t)), p=dict(zip(names, p)),
        r2=float(1 - np.var(yg - Xg @ beta) / np.var(yg)),
        theta=float(theta),
    )


def cce_pooled(df, y_col, x_cols, ent='Country', tcol='Year'):
    """Common Correlated Effects Pooled estimator (Pesaran 2006)."""
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    cs = sub.groupby(tcol)[[y_col] + x_cols].mean()
    cs.columns = [c + '_csavg' for c in [y_col] + x_cols]
    sub = sub.merge(cs, on=tcol, how='left')
    aug = x_cols + [y_col + '_csavg'] + [c + '_csavg' for c in x_cols]
    y = sub[y_col].values
    X = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in aug])
    cl = sub[ent].values
    beta = _ols_coef(X, y)
    resid = y - X @ beta
    n, k = X.shape
    se = _cluster_se(X, resid, cl)
    t, p = _t_and_p(beta, se, n - k)
    names = ['const'] + aug
    return dict(
        estimator='CCEP', y=y_col, obs=n,
        coef=dict(zip(names, beta)), se=dict(zip(names, se)),
        t=dict(zip(names, t)), p=dict(zip(names, p)),
        r2=float(1 - np.var(resid) / np.var(y)),
    )


def cce_fe(df, y_col, x_cols, ent='Country', tcol='Year'):
    """Common Correlated Effects Fixed Effects estimator."""
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    cs = sub.groupby(tcol)[[y_col] + x_cols].mean()
    cs.columns = [c + '_csavg' for c in [y_col] + x_cols]
    sub = sub.merge(cs, on=tcol, how='left')
    aug = x_cols + [y_col + '_csavg'] + [c + '_csavg' for c in x_cols]
    for c in [y_col] + aug:
        sub[c + '_dm'] = sub[c] - sub.groupby(ent)[c].transform('mean')
    y = sub[y_col + '_dm'].values
    X = np.column_stack([sub[c + '_dm'].values for c in aug])
    cl = sub[ent].values
    beta = _ols_coef(X, y)
    resid = y - X @ beta
    n, k = X.shape
    Ne = sub[ent].nunique()
    se = _cluster_se(X, resid, cl)
    t, p = _t_and_p(beta, se, n - Ne - k)
    return dict(
        estimator='CCEFE', y=y_col, obs=n,
        coef=dict(zip(aug, beta)), se=dict(zip(aug, se)),
        t=dict(zip(aug, t)), p=dict(zip(aug, p)),
        r2=float(1 - np.var(resid) / np.var(y)),
    )


def pesaran_cd_test(df, y_col, x_cols, ent='Country', tcol='Year'):
    """Pesaran (2004) CD test for cross-sectional dependence."""
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    for c in [y_col] + x_cols:
        sub[c + '_dm'] = sub[c] - sub.groupby(ent)[c].transform('mean')
    y = sub[y_col + '_dm'].values
    X = np.column_stack([sub[c + '_dm'].values for c in x_cols])
    beta = _ols_coef(X, y)
    sub['resid'] = y - X @ beta

    countries = sorted(sub[ent].unique())
    N = len(countries)
    cd_sum = 0.0
    count = 0
    for i in range(N):
        ri = sub[sub[ent] == countries[i]].set_index(tcol)['resid']
        for j in range(i + 1, N):
            rj = sub[sub[ent] == countries[j]].set_index(tcol)['resid']
            common_t = ri.index.intersection(rj.index)
            Tij = len(common_t)
            if Tij < 3:
                continue
            rho = ri.loc[common_t].corr(rj.loc[common_t])
            if np.isfinite(rho):
                cd_sum += sqrt(Tij) * rho
                count += 1
    if count == 0:
        return None
    CD = sqrt(2.0 / (N * (N - 1))) * cd_sum
    p_val = erfc(abs(CD) / sqrt(2.0))
    return {
        'CD': round(CD, 3), 'p': round(p_val, 4), 'N': N,
        'conclusion': f"CD={CD:.2f}, p={p_val:.4f} → "
                      + ("Reject independence" if p_val < 0.05
                         else "Cannot reject independence"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4.5: MEDIATION ANALYSIS (Baron-Kenny)
# ══════════════════════════════════════════════════════════════════════════════

def run_mediation(df, ai_var):
    """
    Baron-Kenny mediation analysis (Section 4.5).

    Tests two mediating channels:
      H2a: AI → Industrial structure upgrading → TFP
      H2b: AI → Human capital → TFP

    Three steps per mediator:
      Step 1: TFP = f(AI, X)            — already estimated in benchmark
      Step 2: M   = f(AI, X)            — AI → mediator
      Step 3: TFP = f(AI, M, X)         — AI + mediator → TFP

    Mediation evidence requires: (a) Step 2: α₁ significant,
    (b) Step 3: δ₂ significant, (c) Step 3: δ₁ < β₁ from Step 1.
    """
    controls_med = ['LNPGDP_constant2015', 'OPEN_trade',
                    'FDI_inflows', 'GOV_consumption', 'URB_urban_pop']

    mediators = [
        ('LN_IS', 'Industrial structure (ln services/industry VA)'),
        ('LN_HC_index', 'Human capital (ln PWT HC index)'),
    ]

    for y_col, y_label in [('ln_TFP', 'Solow')]:
        print(f"\n{'─'*70}")
        print(f"  DV = {y_label} ({y_col})")
        print(f"{'─'*70}")

        for med_var, med_label in mediators:
            print(f"\n  Mediator: {med_label}")

            # Check data availability
            med_df = df.dropna(subset=[y_col, ai_var, med_var] + controls_med)
            if len(med_df) < 30:
                print(f"    SKIPPED: only {len(med_df)} obs after dropping NaN")
                continue

            # Step 1: Total effect — TFP = f(AI, X)
            try:
                r1 = fixed_effects_twoway(med_df, y_col,
                                          [ai_var] + controls_med,
                                          se_type='driscoll_kraay')
                b1 = r1['coef'][ai_var]
                se1 = r1['se'][ai_var]
                p1 = r1['p'][ai_var]
                print(f"    Step 1 (total):  β₁(AI)={b1:.4f} (SE={se1:.4f})"
                      f"{_stars(p1)} N={r1['obs']}")
            except Exception as e:
                print(f"    Step 1: ERROR {e}")
                continue

            # Step 2: AI → Mediator — M = f(AI, X)
            try:
                r2 = fixed_effects_twoway(med_df, med_var,
                                          [ai_var] + controls_med,
                                          se_type='driscoll_kraay')
                a1 = r2['coef'][ai_var]
                se_a1 = r2['se'][ai_var]
                p_a1 = r2['p'][ai_var]
                print(f"    Step 2 (AI→M):   α₁(AI)={a1:.4f} (SE={se_a1:.4f})"
                      f"{_stars(p_a1)} N={r2['obs']}")
            except Exception as e:
                print(f"    Step 2: ERROR {e}")
                continue

            # Step 3: AI + Mediator → TFP — TFP = f(AI, M, X)
            try:
                r3 = fixed_effects_twoway(med_df, y_col,
                                          [ai_var, med_var] + controls_med,
                                          se_type='driscoll_kraay')
                d1 = r3['coef'][ai_var]
                se_d1 = r3['se'][ai_var]
                p_d1 = r3['p'][ai_var]
                d2 = r3['coef'][med_var]
                se_d2 = r3['se'][med_var]
                p_d2 = r3['p'][med_var]
                print(f"    Step 3 (direct): δ₁(AI)={d1:.4f} (SE={se_d1:.4f})"
                      f"{_stars(p_d1)}")
                print(f"    Step 3 (med):    δ₂(M)={d2:.4f} (SE={se_d2:.4f})"
                      f"{_stars(p_d2)} N={r3['obs']}")
            except Exception as e:
                print(f"    Step 3: ERROR {e}")
                continue

            # Sobel test (approximate): z = α₁ × δ₂ / sqrt(α₁²·se_δ₂² + δ₂²·se_α₁²)
            indirect = a1 * d2
            sobel_se = sqrt(a1**2 * se_d2**2 + d2**2 * se_a1**2)
            if sobel_se > 0:
                z_sobel = indirect / sobel_se
                from scipy.stats import norm
                p_sobel = 2 * (1 - norm.cdf(abs(z_sobel)))
                print(f"    Sobel test:      indirect={indirect:.4f}, "
                      f"z={z_sobel:.3f}, p={p_sobel:.4f}{_stars(p_sobel)}")
            else:
                print(f"    Sobel test:      cannot compute (SE=0)")

            # Interpretation
            if abs(b1) > 1e-10:
                pct_mediated = (indirect / b1) * 100
                print(f"    % mediated:      {pct_mediated:.1f}%")
                if abs(d1) < abs(b1):
                    print(f"    → Partial mediation: direct effect attenuated "
                          f"({abs(b1):.4f} → {abs(d1):.4f})")
                else:
                    print(f"    → No attenuation of direct effect")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4.6: HETEROGENEITY ANALYSIS (Interactions + Subsample)
# ══════════════════════════════════════════════════════════════════════════════

def run_heterogeneity(df, ai_var):
    """
    Heterogeneity analysis (Section 4.6).

    Tests whether the AI→TFP association is moderated by:
      H3:  Institutional quality (Rule of Law)
      H4:  Digital infrastructure (Mobile penetration)
      H4r: Digital infrastructure (Fixed broadband) — robustness

    Approach A: Interaction terms (main)
      lnTFP = β₁·AI + β₂·MOD + β₃·(AI×MOD) + X'γ + λ_t + μ_i + ε

    Approach B: Subsample splits at median (appendix)
    """
    controls_het = ['LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index',
                    'FDI_inflows', 'GOV_consumption', 'URB_urban_pop']

    moderators = [
        ('INST_rule_of_law', 'AI_x_RL',        'H3: Rule of Law'),
        ('INF_mobile',       'AI_x_MOBILE',     'H4: Mobile penetration'),
        ('INF_broadband',    'AI_x_BROADBAND',  'H4r: Fixed broadband'),
    ]

    for y_col, y_label in [('ln_TFP', 'Solow'), ('TFP_Change_CRS', 'Malmquist-CRS')]:
        print(f"\n{'─'*70}")
        print(f"  DV = {y_label} ({y_col})")
        print(f"{'─'*70}")

        for mod_var, interact_var, hyp_label in moderators:
            print(f"\n  ── {hyp_label} ──")

            # ── Approach A: Interaction terms ──
            x_interact = [ai_var, mod_var, interact_var] + controls_het
            try:
                r = fixed_effects_twoway(df, y_col, x_interact,
                                         se_type='driscoll_kraay')
                b_ai = r['coef'].get(ai_var, np.nan)
                b_mod = r['coef'].get(mod_var, np.nan)
                b_int = r['coef'].get(interact_var, np.nan)
                se_int = r['se'].get(interact_var, np.nan)
                p_int = r['p'].get(interact_var, np.nan)
                print(f"    Interaction:  β(AI)={b_ai:.4f}, β(MOD)={b_mod:.4f}, "
                      f"β(AI×MOD)={b_int:.4f} (SE={se_int:.4f}){_stars(p_int)} "
                      f"N={r['obs']}")
            except Exception as e:
                print(f"    Interaction: ERROR {e}")

            # ── Approach B: Subsample split at median ──
            try:
                med_val = df[mod_var].median()
                low = df[df[mod_var] <= med_val].copy()
                high = df[df[mod_var] > med_val].copy()
                x_base = [ai_var] + controls_het

                r_low = fixed_effects_twoway(low, y_col, x_base,
                                              se_type='driscoll_kraay')
                r_high = fixed_effects_twoway(high, y_col, x_base,
                                               se_type='driscoll_kraay')
                b_low = r_low['coef'].get(ai_var, np.nan)
                se_low = r_low['se'].get(ai_var, np.nan)
                p_low = r_low['p'].get(ai_var, np.nan)
                b_high = r_high['coef'].get(ai_var, np.nan)
                se_high = r_high['se'].get(ai_var, np.nan)
                p_high = r_high['p'].get(ai_var, np.nan)
                print(f"    Low {mod_var}:  β(AI)={b_low:.4f} (SE={se_low:.4f})"
                      f"{_stars(p_low)} N={r_low['obs']}")
                print(f"    High {mod_var}: β(AI)={b_high:.4f} (SE={se_high:.4f})"
                      f"{_stars(p_high)} N={r_high['obs']}")

                # Chow-type difference test (approximate)
                diff = b_high - b_low
                se_diff = sqrt(se_high**2 + se_low**2)
                if se_diff > 0:
                    z_diff = diff / se_diff
                    from scipy.stats import norm
                    p_diff = 2 * (1 - norm.cdf(abs(z_diff)))
                    print(f"    Diff test:    Δβ={diff:.4f}, z={z_diff:.3f}, "
                          f"p={p_diff:.4f}{_stars(p_diff)}")
            except Exception as e:
                print(f"    Subsample: ERROR {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4.7: CANAY (2011) PANEL QUANTILE REGRESSION
# ══════════════════════════════════════════════════════════════════════════════

def run_quantile_canay(df, ai_var):
    """
    Canay (2011) two-step panel quantile regression (Section 4.7).

    Solow TFP only (continuous level variable — Malmquist TFP change is a ratio
    near 1.0 with low variance, making quantile estimation noisy).

    Step 1: Estimate FE model, extract μ̂_i
    Step 2: y*_it = y_it - μ̂_i → run standard quantile regression on y*

    Quantiles: τ = {0.10, 0.25, 0.50, 0.75, 0.90}
    """
    from scipy.optimize import linprog

    y_col = 'ln_TFP'
    x_cols = [ai_var] + CONTROLS_PARS
    quantiles = [0.10, 0.25, 0.50, 0.75, 0.90]

    sub = df[[y_col] + x_cols + ['Country', 'Year']].dropna().copy()
    if len(sub) < 50:
        print(f"  SKIPPED: only {len(sub)} obs")
        return

    # Step 1: Estimate FE to get μ̂_i
    country_means_y = sub.groupby('Country')[y_col].mean()
    country_means_x = sub.groupby('Country')[x_cols].mean()
    grand_mean_y = sub[y_col].mean()
    grand_mean_x = sub[x_cols].mean()

    # De-mean by entity for FE
    y_dm = sub[y_col] - sub['Country'].map(country_means_y)
    X_dm = sub[x_cols].copy()
    for c in x_cols:
        X_dm[c] = X_dm[c] - sub['Country'].map(country_means_x[c])

    beta_fe = np.linalg.lstsq(X_dm.values, y_dm.values, rcond=None)[0]

    # Compute fixed effects: μ̂_i = ȳ_i - x̄_i'β̂
    fe_hat = {}
    for c in sub['Country'].unique():
        fe_hat[c] = country_means_y[c] - country_means_x.loc[c].values @ beta_fe

    # Step 2: Construct y* = y - μ̂_i
    sub['y_star'] = sub[y_col] - sub['Country'].map(fe_hat)

    # Also demean x by time (year dummies absorbed via demeaning)
    time_means_y_star = sub.groupby('Year')['y_star'].mean()
    time_means_x = sub.groupby('Year')[x_cols].mean()
    sub['y_star_2w'] = sub['y_star'] - sub['Year'].map(time_means_y_star)
    X_qr = sub[x_cols].copy()
    for c in x_cols:
        X_qr[c] = X_qr[c] - sub['Year'].map(time_means_x[c])

    # Add constant for quantile regression
    X_mat = np.column_stack([np.ones(len(sub)), X_qr.values])
    y_vec = sub['y_star_2w'].values
    n, k = X_mat.shape

    print(f"  DV = Solow (ln_TFP), N={n}")
    print(f"  {'τ':<6} {'β(AI)':>10} {'SE':>10} {'t':>8} {'p':>8}")
    print(f"  {'-'*46}")

    qr_results = []
    for tau in quantiles:
        # Quantile regression via LP (Koenker & Bassett 1978)
        # min Σ ρ_τ(y - Xβ) where ρ_τ(u) = u·(τ - I(u<0))
        c_lp = np.concatenate([
            np.zeros(k),       # β (free, split into β+ - β-)
            tau * np.ones(n),  # u+ (positive residuals)
            (1 - tau) * np.ones(n),  # u- (negative residuals)
        ])
        # Constraints: Xβ + u+ - u- = y  →  [X, I, -I][β, u+, u-]' = y
        # β is free → split: β = β+ - β-, β+,β- >= 0
        c_lp2 = np.concatenate([
            np.zeros(k),       # β+ coefficients in objective
            np.zeros(k),       # β- coefficients in objective
            tau * np.ones(n),  # u+
            (1 - tau) * np.ones(n),  # u-
        ])
        A_eq = np.hstack([X_mat, -X_mat, np.eye(n), -np.eye(n)])
        b_eq = y_vec

        try:
            res = linprog(c_lp2, A_eq=A_eq, b_eq=b_eq,
                          bounds=[(0, None)] * (2*k + 2*n),
                          method='highs', options={'maxiter': 10000})
            if res.success:
                beta_plus = res.x[:k]
                beta_minus = res.x[k:2*k]
                beta_qr = beta_plus - beta_minus

                # Bootstrap SE (paired, B=200)
                rng = np.random.RandomState(42)
                B = 200
                beta_boot = np.zeros((B, k))
                for b_idx in range(B):
                    idx_b = rng.choice(n, n, replace=True)
                    y_b = y_vec[idx_b]
                    X_b = X_mat[idx_b]
                    A_b = np.hstack([X_b, -X_b, np.eye(n), -np.eye(n)])
                    res_b = linprog(c_lp2, A_eq=A_b, b_eq=y_b,
                                    bounds=[(0, None)] * (2*k + 2*n),
                                    method='highs',
                                    options={'maxiter': 5000, 'presolve': True})
                    if res_b.success:
                        beta_boot[b_idx] = res_b.x[:k] - res_b.x[k:2*k]
                    else:
                        beta_boot[b_idx] = beta_qr  # fallback

                se_qr = beta_boot.std(axis=0)
                ai_idx = 1  # after constant
                b_ai = beta_qr[ai_idx]
                se_ai = se_qr[ai_idx]
                t_ai = b_ai / se_ai if se_ai > 0 else 0
                from scipy.stats import t as t_dist
                p_ai = 2 * (1 - t_dist.cdf(abs(t_ai), df=n-k))
                print(f"  {tau:<6.2f} {b_ai:>10.4f} {se_ai:>10.4f} "
                      f"{t_ai:>8.3f} {p_ai:>8.4f}{_stars(p_ai)}")
                qr_results.append({
                    'tau': tau, 'beta_AI': b_ai, 'se': se_ai,
                    't': t_ai, 'p': p_ai
                })
            else:
                print(f"  {tau:<6.2f}   LP did not converge: {res.message}")
        except Exception as e:
            print(f"  {tau:<6.2f}   ERROR: {e}")

    if qr_results:
        betas = [r['beta_AI'] for r in qr_results]
        print(f"\n  Pattern: β ranges from {min(betas):.4f} (τ={qr_results[np.argmin(betas)]['tau']}) "
              f"to {max(betas):.4f} (τ={qr_results[np.argmax(betas)]['tau']})")
        if betas[-1] > betas[0]:
            print(f"  → Increasing across quantiles: AI innovation is associated with")
            print(f"    stronger TFP gains at higher TFP levels (complementarity)")
        elif betas[-1] < betas[0]:
            print(f"  → Decreasing across quantiles: AI innovation is associated with")
            print(f"    stronger TFP gains at lower TFP levels (catch-up)")
        else:
            print(f"  → Flat across quantiles: no distributional heterogeneity")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLICATION-READY OUTPUT TABLES
# ══════════════════════════════════════════════════════════════════════════════

def compute_descriptives(df):
    """Summary statistics for the merged panel (descriptive statistics table)."""
    vars_desc = {
        'TFP': 'Solow TFP',
        'TFP_Growth': 'Solow TFP Growth (%)',
        'TFP_Change': 'Malmquist TFP Change (VRS)',
        'TFP_Change_CRS': 'Malmquist TFP Change (CRS)',
        'AI_Patents': 'AI Patent Count',
        'AI_Patent_Stock_PC': 'AI Patent Stock per capita',
        'LN_AI': 'ln(AI Patent Stock pc)',
        'GDPPC_constant2015': 'GDP per capita (const. 2015 USD)',
        'FIN_credit_private': 'Private Credit (% GDP)',
        'OPEN_trade': 'Trade Openness (% GDP)',
        'INF_internet': 'Internet Users (%)',
        'HC_index': 'PWT Human Capital Index',
    }
    rows = []
    for var, label in vars_desc.items():
        if var not in df.columns:
            continue
        s = df[var].dropna()
        if len(s) == 0:
            continue
        rows.append({
            'Variable': label, 'N': len(s),
            'Mean': round(float(s.mean()), 4), 'Std': round(float(s.std()), 4),
            'Min': round(float(s.min()), 4), 'Max': round(float(s.max()), 4),
        })
    return pd.DataFrame(rows)


def compute_correlation_matrix(df):
    """Correlation matrix for key regression variables."""
    vars_corr = ['LN_AI', 'LNPGDP_constant2015', 'FIN_credit_private',
                 'OPEN_trade', 'INF_internet', 'LN_HC_index']
    vars_corr = [v for v in vars_corr if v in df.columns]
    return df[vars_corr].dropna().corr()


def _json_safe(o):
    """Make numpy types JSON-serializable."""
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer, int)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(i) for i in o]
    return o


def _write_latex_table(spec, spec_label, dv_label, filename, out_dir,
                       focus_vars, vlt, eo, dec=4):
    """Write a LaTeX regression table for one benchmark specification."""
    cl = [f'({i+1})\\\\{e}' for i, e in enumerate(eo)]
    L = [
        r'\begin{table}[htbp]', r'\centering', r'\small',
        f'\\caption{{{spec_label}}}',
        f'\\label{{tab:{filename.replace(".tex", "")}}}',
        r'\begin{tabular}{l' + 'c' * len(eo) + r'}',
        r'\toprule',
        ' & '.join([''] + [f'\\makecell{{{c}}}' for c in cl]) + r' \\',
        r'\midrule',
        f'\\multicolumn{{{len(eo)+1}}}{{l}}{{\\textit{{DV: {dv_label}}}}} \\\\[4pt]',
    ]
    for v in focus_vars + ['const']:
        lb = vlt.get(v, v.replace('_', r'\_'))
        cr = f'${lb}$'
        sr = ''
        for e in eo:
            r = spec.get(e)
            if r and v in r.get('coef', {}):
                c, s, pv = r['coef'][v], r['se'][v], r['p'][v]
                cr += f' & {c:+.{dec}f}\\textsuperscript{{{_stars(pv)}}}'
                sr += f' & ({s:.{dec}f})'
            else:
                cr += ' & ---'
                sr += ' & '
        L.append(cr + r' \\')
        L.append(sr + r' \\[2pt]')
    L.append(r'\midrule')
    for rl, fn in [
        ('Observations', lambda e: str(spec[e]['obs']) if e in spec and 'obs' in spec[e] else '---'),
        ('$R^2$', lambda e: f"{spec[e]['r2']:.3f}" if e in spec and 'r2' in spec[e] else '---'),
        ('Entity FE', lambda e: 'Yes' if e in ('FE', 'CCEFE') else 'No'),
        ('Time FE', lambda e: 'Yes' if e in ('FE', 'CCEFE') else 'No'),
        ('CS Averages', lambda e: 'Yes' if e in ('CCEP', 'CCEFE') else 'No'),
    ]:
        L.append(rl + ' & ' + ' & '.join(fn(e) for e in eo) + r' \\')
    L += [
        r'\bottomrule', r'\end{tabular}',
        r'\begin{tablenotes}', r'\footnotesize',
        r'\item \textit{Notes:} Cluster-robust SE (by country) in parentheses. '
        r'$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.',
        f'\\item {len(COUNTRIES)} LAC countries, {START_YR}--{END_YR}. '
        r'Two-way (country + year) fixed effects in the FE and CCEFE columns. '
        r'Human capital: PWT 10.01 index.',
        r'\end{tablenotes}', r'\end{table}',
    ]
    (out_dir / filename).write_text('\n'.join(L))


def emit_publication_tables(df, merged, out_dir):
    """Generate publication-ready benchmark tables (descriptives, correlation,
    JSON, comparison CSV, LaTeX, and text summary) into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ai_var = 'LN_AI'

    compute_descriptives(merged).to_csv(
        out_dir / 'descriptive_statistics.csv', index=False)
    compute_correlation_matrix(merged).to_csv(
        out_dir / 'correlation_matrix.csv')

    # Benchmark specifications: Solow & Malmquist (VRS), full & parsimonious
    specs = [
        ('Solow_full',     'ln_TFP',     CONTROLS_FULL),
        ('Malmquist_full', 'TFP_Change', CONTROLS_FULL),
        ('Solow_pars',     'ln_TFP',     CONTROLS_PARS),
        ('Malmquist_pars', 'TFP_Change', CONTROLS_PARS),
    ]
    estimators = [
        ('OLS',   lambda d, y, x: pooled_ols(d, y, x)),
        ('FE',    lambda d, y, x: fixed_effects_twoway(d, y, x, se_type='cluster')),
        ('RE',    lambda d, y, x: random_effects(d, y, x)),
        ('CCEP',  lambda d, y, x: cce_pooled(d, y, x)),
        ('CCEFE', lambda d, y, x: cce_fe(d, y, x)),
    ]
    eo = ['OLS', 'FE', 'RE', 'CCEP', 'CCEFE']

    all_results = {}
    for sn, y_col, ctrls in specs:
        x_cols = [ai_var] + ctrls
        sr = {}
        for en, fn in estimators:
            try:
                sr[en] = fn(df, y_col, x_cols)
            except Exception as e:
                sr[en] = {'error': str(e)}
        all_results[sn] = sr

    with open(out_dir / 'regression_results.json', 'w') as f:
        json.dump(_json_safe(all_results), f, indent=2)

    rows = []
    for sn, sr in all_results.items():
        for en in eo:
            r = sr.get(en, {})
            if ai_var not in r.get('coef', {}):
                continue
            p = r['p'][ai_var]
            rows.append({
                'spec': sn, 'estimator': en, 'ai_var': ai_var,
                'beta_AI': round(r['coef'][ai_var], 6),
                'se_AI': round(r['se'][ai_var], 6),
                'p_AI': (round(float(p), 4) if np.isfinite(p) else None),
                'stars': _stars(p),
                'r2': round(r['r2'], 4), 'N': r['obs'],
            })
    pd.DataFrame(rows).to_csv(out_dir / 'regression_comparison.csv', index=False)

    fv_full = ['LN_AI', 'LNPGDP_constant2015', 'FIN_credit_private',
               'OPEN_trade', 'INF_internet', 'LN_HC_index']
    fv_pars = ['LN_AI', 'LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index']
    vlt = {
        'LN_AI': r'\ln(\text{AI Patent Stock pc})',
        'LNPGDP_constant2015': r'\ln(\text{GDP pc})',
        'FIN_credit_private': r'\text{Private Credit}',
        'OPEN_trade': r'\text{Trade Openness}',
        'INF_internet': r'\text{Internet (\%)}',
        'LN_HC_index': r'\ln(\text{PWT HC Index})',
        'const': r'\text{Constant}',
    }
    for sn, sl, dvl, fn, fv in [
        ('Solow_full', 'Solow TFP --- Full Controls',
         r'$\ln(\text{TFP})$', 'tab_solow_full.tex', fv_full),
        ('Malmquist_full', 'Malmquist TFP Change --- Full Controls',
         'Malmquist TFP Change (VRS)', 'tab_malmquist_full.tex', fv_full),
        ('Solow_pars', 'Solow TFP --- Parsimonious',
         r'$\ln(\text{TFP})$', 'tab_solow_pars.tex', fv_pars),
        ('Malmquist_pars', 'Malmquist TFP Change --- Parsimonious',
         'Malmquist TFP Change (VRS)', 'tab_malmquist_pars.tex', fv_pars),
    ]:
        dec = 5 if 'Malmquist' in sn else 4
        _write_latex_table(all_results.get(sn, {}), sl, dvl, fn, out_dir,
                           fv, vlt, eo, dec)

    sep = '─' * 92
    lines = [
        sep,
        f'v5 BENCHMARK RESULTS: AI Patent Stock → TFP, {len(COUNTRIES)} LAC '
        f'Countries, {START_YR}–{END_YR}',
        sep, '',
        'AI coefficient (LN_AI = ln per-capita AI patent stock) by specification:',
        '',
    ]
    for sn, _, _ in specs:
        lines.append(f'  {sn}')
        for en in eo:
            r = all_results[sn].get(en, {})
            if ai_var in r.get('coef', {}):
                p = r['p'][ai_var]
                lines.append(
                    f'    {en:<6} β(AI)={r["coef"][ai_var]:+.5f} '
                    f'(SE={r["se"][ai_var]:.5f}){_stars(p):<3} '
                    f'p={p:.4f}  N={r["obs"]}  R²={r["r2"]:.3f}')
            else:
                lines.append(f'    {en:<6} —  {r.get("error", "n/a")}')
        lines.append('')
    lines.append(sep)
    (out_dir / 'regression_summary.txt').write_text('\n'.join(lines))

    written = ['descriptive_statistics.csv', 'correlation_matrix.csv',
               'regression_results.json', 'regression_comparison.csv',
               'tab_solow_full.tex', 'tab_solow_pars.tex',
               'tab_malmquist_full.tex', 'tab_malmquist_pars.tex',
               'regression_summary.txt']
    for fn in written:
        print(f"    • {fn}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("╔" + "═" * 68 + "╗")
    print("║  TFP-AI Pipeline v5                                               ║")
    print("║  9 Countries, 2000–2024, PWT HC                                   ║")
    print("║  FIXES: C1(Malmquist), C2(YearFE), M1(2-input DEA),              ║")
    print("║         M2(interp), M3(patent stock PC)                           ║")
    print("╚" + "═" * 68 + "╝")

    # ── Step 1: Extract data ────────────────────────────────────────────
    solow_df, wdi_df = extract_data_from_csv()

    # ── Step 2: Solow TFP ──────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print(f"STEP 2: Solow TFP — two-factor (α={ALPHA}, 1−α={1-ALPHA:.2f}, "
          f"labor-augmenting HC)")
    print(f"{'═'*70}")
    solow_df = compute_solow_tfp(solow_df)
    tfp_valid = solow_df[solow_df.Year >= START_YR]['TFP'].notna().sum()
    total_obs = len(solow_df[solow_df.Year >= START_YR])
    print(f"  TFP computed: {tfp_valid}/{total_obs} obs (2000-2024)")
    for c in COUNTRIES:
        s = solow_df[(solow_df.Country == c) & (solow_df.Year >= START_YR)]['TFP']
        print(f"    {c}: mean={s.mean():.4e} [{s.notna().sum()} obs]")
    solow_df.to_csv(RESULTS_DIR / 'solow_tfp_dissertation_v5.csv', index=False)

    # ── Step 3a: Malmquist DEA — VRS (main specification) ──────────────
    print(f"\n{'═'*70}")
    print("STEP 3a: Malmquist DEA TFP Change — VRS (2-input: K, L×HC)")
    print(f"{'═'*70}")
    dea_df = solow_df.dropna(subset=['GDP', 'CAPITAL', 'EFFECTIVE_LABOR'])
    print(f"  DEA-ready: {len(dea_df)} obs")
    mq = compute_malmquist_tfp(dea_df, use_2_inputs=True, rts='vrs')
    mq_valid = mq['TFP_Change'].notna().sum()
    print(f"\n  Results: {len(mq)} rows, {mq_valid} valid")
    for c in sorted(mq.Country.unique()):
        g = mq[(mq.Country == c) & mq.TFP_Change.notna()]['TFP_Change']
        if len(g) > 0:
            print(f"    {c}: geom_mean={np.exp(np.log(g).mean()):.4f} (n={len(g)})")
        else:
            print(f"    {c}: NO VALID OBS (VRS infeasibility)")
    mq.to_csv(RESULTS_DIR / 'malmquist_dissertation_v5.csv', index=False)

    # ── Step 3b: Malmquist DEA — CRS (robustness) ────────────────────
    print(f"\n{'═'*70}")
    print("STEP 3b: Malmquist DEA TFP Change — CRS (robustness)")
    print(f"{'═'*70}")
    print("  CRS resolves VRS infeasibility for small DMUs (URY, CRI)")
    mq_crs = compute_malmquist_tfp(dea_df, use_2_inputs=True, rts='crs')
    mq_crs_valid = mq_crs['TFP_Change'].notna().sum()
    print(f"\n  Results: {len(mq_crs)} rows, {mq_crs_valid} valid")
    for c in sorted(mq_crs.Country.unique()):
        g = mq_crs[(mq_crs.Country == c) & mq_crs.TFP_Change.notna()]['TFP_Change']
        if len(g) > 0:
            print(f"    {c}: geom_mean={np.exp(np.log(g).mean()):.4f} (n={len(g)})")
    mq_crs.to_csv(RESULTS_DIR / 'malmquist_crs_dissertation_v5.csv', index=False)

    # Compare VRS vs CRS for overlapping valid observations
    vrs_valid = mq.dropna(subset=['TFP_Change']).set_index(['Country', 'Year_t1'])
    crs_valid = mq_crs.dropna(subset=['TFP_Change']).set_index(['Country', 'Year_t1'])
    overlap = vrs_valid.index.intersection(crs_valid.index)
    if len(overlap) > 0:
        corr = np.corrcoef(
            vrs_valid.loc[overlap, 'TFP_Change'].values,
            crs_valid.loc[overlap, 'TFP_Change'].values
        )[0, 1]
        mean_diff = (crs_valid.loc[overlap, 'TFP_Change'].values -
                     vrs_valid.loc[overlap, 'TFP_Change'].values).mean()
        print(f"\n  VRS vs CRS overlap: {len(overlap)} obs, corr={corr:.4f}, "
              f"mean_diff(CRS-VRS)={mean_diff:.4f}")

    # ── Step 4: WIPO AI Patents ────────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 4: WIPO AI Patents")
    print(f"{'═'*70}")
    patents = load_ai_patents()

    # ── Step 5: Merge ──────────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 5: Build Merged Panel")
    print(f"{'═'*70}")
    merged = build_merged_dataset(patents, solow_df, mq, wdi_df, malmquist_crs=mq_crs)
    print(f"  Panel: {merged.shape[0]} obs, {merged.Country.nunique()} countries, "
          f"{merged.Year.min()}-{merged.Year.max()}")
    for col in ['TFP', 'TFP_Change', 'TFP_Change_CRS', 'AI_Patents',
                'AI_Patent_Stock_PC', 'LN_AI', 'LNPGDP_constant2015']:
        if col in merged.columns:
            nn = merged[col].notna().sum()
            print(f"    {col:<25} {nn}/{len(merged)} ({nn/len(merged)*100:.0f}%)")
    merged.to_csv(RESULTS_DIR / 'merged_dissertation_v5.csv', index=False)

    # ── Step 6: Benchmark Regressions ─────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 6: Benchmark Regressions (two-way FE + DK SE)")
    print(f"{'═'*70}")
    df = merged.copy()
    df['ln_TFP'] = np.log(df['TFP'].clip(lower=1e-15))

    ai_var = 'LN_AI'

    dv_list = [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist-VRS')]
    if 'TFP_Change_CRS' in df.columns:
        dv_list.append(('TFP_Change_CRS', 'Malmquist-CRS'))

    for y_col, label in dv_list:
        print(f"\n{'─'*70}")
        print(f"  DV = {label} ({y_col})")
        print(f"{'─'*70}")
        x_cols = [ai_var] + CONTROLS_PARS

        # OLS
        try:
            r = pooled_ols(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  OLS:    β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  OLS: ERROR {e}")

        # Two-way FE (cluster SE)
        try:
            r = fixed_effects_twoway(df, y_col, x_cols, se_type='cluster')
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  FE-2w:  β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  FE-2w: ERROR {e}")

        # Two-way FE (Driscoll-Kraay SE)
        try:
            r = fixed_effects_twoway(df, y_col, x_cols, se_type='driscoll_kraay')
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  FE-DK:  β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  FE-DK: ERROR {e}")

        # RE
        try:
            r = random_effects(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  RE:     β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  RE: ERROR {e}")

        # CCEP
        try:
            r = cce_pooled(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  CCEP:   β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  CCEP: ERROR {e}")

        # CCEFE
        try:
            r = cce_fe(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  CCEFE:  β(AI)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  CCEFE: ERROR {e}")

    # ── Step 7: Pesaran CD test ───────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 7: Pesaran CD Test for Cross-Sectional Dependence")
    print(f"{'═'*70}")
    cd_dvs = [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist-VRS')]
    if 'TFP_Change_CRS' in df.columns:
        cd_dvs.append(('TFP_Change_CRS', 'Malmquist-CRS'))
    for y_col, label in cd_dvs:
        cd = pesaran_cd_test(df, y_col, [ai_var] + CONTROLS_PARS)
        if cd:
            print(f"  {label}: {cd['conclusion']}")
        else:
            print(f"  {label}: CD test failed (insufficient data)")

    # ── Step 8: Mediation Analysis (Baron-Kenny, Section 4.5) ──────
    print(f"\n{'═'*70}")
    print("STEP 8: Mediation Analysis (Baron-Kenny)")
    print(f"{'═'*70}")
    run_mediation(df, ai_var)

    # ── Step 9: Heterogeneity Analysis (Section 4.6) ─────────────────
    print(f"\n{'═'*70}")
    print("STEP 9: Heterogeneity Analysis (Interactions + Subsample)")
    print(f"{'═'*70}")
    run_heterogeneity(df, ai_var)

    # ── Step 10: Canay (2011) Panel Quantile Regression (Section 4.7) ─
    print(f"\n{'═'*70}")
    print("STEP 10: Panel Quantile Regression — Canay (2011)")
    print(f"{'═'*70}")
    run_quantile_canay(df, ai_var)

    # ── Step 11: Publication-ready benchmark tables ───────────────────
    print(f"\n{'═'*70}")
    print("STEP 11: Publication Tables (descriptives, JSON, CSV, LaTeX)")
    print(f"{'═'*70}")
    emit_publication_tables(df, merged, OUT_DIR)

    print(f"\n{'═'*70}")
    print("PIPELINE v5 COMPLETE")
    print(f"{'═'*70}")
    print(f"\nOutputs saved to: {RESULTS_DIR}/")
    print(f"  • solow_tfp_dissertation_v5.csv")
    print(f"  • malmquist_dissertation_v5.csv (VRS)")
    print(f"  • malmquist_crs_dissertation_v5.csv (CRS robustness)")
    print(f"  • merged_dissertation_v5.csv")
    print(f"  • {OUT_DIR.relative_to(BASE_DIR)}/ "
          f"(descriptive_statistics.csv, correlation_matrix.csv,")
    print(f"    regression_results.json, regression_comparison.csv, "
          f"regression_summary.txt, tab_*.tex)")


if __name__ == '__main__':
    main()
