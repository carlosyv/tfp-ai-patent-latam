#!/usr/bin/env python3
"""
run_dissertation_v4_noimput_pipeline.py
========================================
Complete TFP-AI pipeline — v4 NO IMPUTATION (updated moderation hypotheses & expanded controls)

Imputation removed vs v4 baseline:
  - ILOSTAT labor: raw observed values only — no interpolate(limit_direction='both')
  - WDI controls: raw values only — no interpolate(limit_direction='both')
  - AI Patents: no fillna(0) — unobserved country-years remain NaN
  - PWT HC 2024 forward extrapolation: RETAINED (low-risk)
  - PIM capital stock gap-skipping: RETAINED (GFCF coverage complete)

"The Impact of AI Adoption on Total Factor Productivity (TFP) in Latin America"

Panel: 7 LAC countries (ARG, BRA, CHL, COL, CRI, MEX, PER), 1992–2024.
Human capital: PWT 10.01 index. Labor: ILOSTAT total employment (EMP_TEMP).

Changes from v3:
  - H3 (REVISED): Institutional quality moderation via Rule of Law (RL.EST).
        Financial development moderation dropped — private credit and deposits
        both failed to show significance in LAC context (v3/v4 testing).
        Rule of Law captures the enabling institutional environment for AI
        patent spillovers to translate into productivity gains.
  - H4 (REVISED): Primary moderator → Mobile cellular per 100 (IT.CEL.SETS.P2).
        Rationale: in LATAM, mobile penetration precedes fixed broadband and
        drives AI tool adoption via cloud/SaaS/mobile-first applications.
  - H4r (ROBUSTNESS): Fixed broadband per 100 (IT.NET.BBND.P2) retained as
        quality-of-infrastructure robustness check for H4.
  - New controls added to ALL regressions:
      FDI net inflows % GDP  (BX.KLT.DINV.WD.GD.ZS)
      Govt final consumption % GDP  (NE.CON.GOVT.ZS)
      Urban population % total  (SP.URB.TOTL.IN.ZS)
  - Retained controls: Trade, lnGDPpc, Internet users, Private credit, HC

Pipeline Steps:
  1. Extract data from CSV files (WDI + PWT + ILOSTAT + WIPO)
  2. Compute Solow TFP: two-factor with labor-augmenting HC (α=0.35)
  3. Compute DEA-Malmquist TFP change index
  4. Parse WIPO AI patent files (Spanish + Portuguese)
  5. Merge all sources into panel dataset
  6. H1: Benchmark regressions (OLS, FE, RE, CCEP, CCEFE) × (Full, Parsimonious)
     + Robustness: Lag-1, Lag-2, cumulative stock specifications
  7. H2: Mediation analysis (AI → HC → TFP, Baron & Kenny 1986)
  8. H3: Institutional quality moderation — Rule of Law (RL.EST interaction)
  9. H4: Mobile cellular moderation — primary (IT.CEL.SETS.P2 interaction)
 10. H4r: Fixed broadband moderation — robustness (IT.NET.BBND.P2 interaction)
 11. H5: Panel quantile regression (τ = 0.10, 0.25, 0.50, 0.75, 0.90)
 12. Cross-sectional dependence diagnostics (Pesaran CD test)
 13. Save all outputs (CSV, JSON, LaTeX, TXT summary)

Data sources (all in ./data/):
  - wb_data_export.csv                              → WDI indicators
  - pwt-data-human-capital-026-03-22T15-56_export.csv → PWT 10.01 HC index
  - ai-search-wipo-results-spanish-v2.xlsx          → WIPO AI patents (Spanish)
  - ai-search-wipo-results-br-portuguese-v2.xlsx    → WIPO AI patents (Portuguese)

Usage:
  python run_dissertation_v4_pipeline.py
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

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
RESULTS_DIR = BASE_DIR / 'output' / 'results'
OUT_DIR = RESULTS_DIR / 'benchmark_dissertation_v4_noimput'

# Data files
WB_CSV = DATA_DIR / 'wb_data_export.csv'
PWT_CSV = DATA_DIR / 'pwt-data-human-capital-026-03-22T15-56_export.csv'
WIPO_SPANISH = DATA_DIR / 'ai-search-wipo-results-spanish-v2.xlsx'
WIPO_PORTUGUESE = DATA_DIR / 'ai-search-wipo-results-br-portuguese-v2.xlsx'
ILOSTAT_LFPR = DATA_DIR / 'ilostat-labor-force-participation-rate.xlsx'
ILOSTAT_EMP = DATA_DIR / 'EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv'

# Model parameters — two-factor Solow with labor-augmenting HC (dissertation eq. 1)
# TFP = Y / [ K^α × (L·HC)^(1−α) ]
# where effective labor = L × HC
ALPHA = 0.35        # Capital share
DELTA = 0.05        # Depreciation rate for PIM capital stock
START_YR = 1992
END_YR = 2024

# Countries
COUNTRY_NAMES = {
    'ARG': 'Argentina', 'BRA': 'Brazil', 'CHL': 'Chile',
    'COL': 'Colombia', 'CRI': 'Costa Rica',
    'MEX': 'Mexico', 'PER': 'Peru',
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
    # Financial development
    'FS.AST.PRVT.GD.ZS': 'FIN_credit_private',      # kept from v3 (control)
    'FS.AST.DOMS.GD.ZS': 'FIN_credit_financial',
    'GFDD.DI.08':        'FIN_deposits',              # financial depth control (not moderated)
    # Government size
    'NE.CON.GOVT.ZS':    'GOV_consumption',           # NEW: added to all models
    'GC.XPN.TOTL.GD.ZS': 'GOV_expense',
    # Urbanization
    'SP.URB.TOTL.IN.ZS': 'URB_urban_pop',             # NEW: added to all models
    # Trade & openness
    'NE.TRD.GNFS.ZS':    'OPEN_trade',
    'BX.KLT.DINV.WD.GD.ZS': 'FDI_inflows',           # NEW: added to all models
    # GDP per capita
    'NY.GDP.PCAP.KD':    'GDPPC_constant2015',
    'NY.GDP.PCAP.PP.KD': 'GDPPC_ppp',
    # ICT / digital
    'IT.NET.USER.ZS':    'INF_internet',              # kept from v3 (control)
    'IT.NET.BBND.P2':    'INF_broadband',             # H4r: robustness moderator
    'IT.CEL.SETS.P2':    'INF_mobile',                # H4: primary moderator
    'IT.MLT.MAIN.P2':    'INF_telephone',
    # Institutions
    'RL.EST':            'INST_rule_of_law',           # H3: institutional quality moderator
}

# Control variable sets for regressions
# v4: adds FDI, govt consumption, urbanization to all specs
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
    """Load PWT Human Capital Index (hc) for 7 countries."""
    print("\n  Loading PWT Human Capital Index...")
    raw = pd.read_csv(PWT_CSV)
    raw = raw[raw['ISO code'].isin(COUNTRIES)]
    year_cols = [str(y) for y in range(START_YR, END_YR + 1)]
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
        yrs = END_YR - START_YR + 1
        print(f"    {c}: {nn_c}/{yrs}")
    return df


def load_ilostat_employment():
    """
    Load ILOSTAT total employment (EMP_TEMP_SEX_AGE_NB, thousands, 15+, Total).

    Dissertation: "Labor (Lt) is measured as total employment from ILOSTAT."
    This uses the actual employment series. Values are in thousands; we
    convert to persons (×1000) for consistency with WDI fallback.
    NO interpolation applied — country-years with missing employment remain NaN
    and are excluded downstream from TFP computation and all regressions.
    """
    print("\n  Loading ILOSTAT total employment data...")
    ilostat = pd.read_csv(ILOSTAT_EMP)

    # Filter: Total sex, Youth/adults 15+ age band
    emp = ilostat[
        (ilostat['sex.label'] == 'Total') &
        (ilostat['classif1.label'] == 'Age (Youth, adults): 15+')
    ].copy()

    name_to_iso3 = {
        'Argentina': 'ARG', 'Brazil': 'BRA', 'Chile': 'CHL',
        'Colombia': 'COL', 'Costa Rica': 'CRI',
        'Mexico': 'MEX', 'Peru': 'PER',
    }
    emp = emp[emp['ref_area.label'].isin(name_to_iso3)]
    emp['Country'] = emp['ref_area.label'].map(name_to_iso3)
    emp = emp[['Country', 'time', 'obs_value']].rename(
        columns={'time': 'Year', 'obs_value': 'EMP_thousands'})
    emp['EMP_thousands'] = pd.to_numeric(emp['EMP_thousands'], errors='coerce')
    emp = emp[(emp.Year >= START_YR) & (emp.Year <= END_YR)]
    emp = emp.sort_values(['Country', 'Year']).reset_index(drop=True)

    # Convert thousands → persons
    emp['LABOR_ILOSTAT'] = emp['EMP_thousands'] * 1000.0

    # No interpolation: keep only directly observed country-years; NaN = excluded
    merged = emp[['Country', 'Year', 'LABOR_ILOSTAT']].copy()
    merged = merged.sort_values(['Country', 'Year']).reset_index(drop=True)

    for c in COUNTRIES:
        sub = merged[(merged.Country == c) & merged.LABOR_ILOSTAT.notna()]
        print(f"    {c}: {len(sub)} observed (no interpolation), "
              f"range {sub.LABOR_ILOSTAT.min()/1e6:.1f}M–"
              f"{sub.LABOR_ILOSTAT.max()/1e6:.1f}M")

    return merged[['Country', 'Year', 'LABOR_ILOSTAT']]


def extract_data_from_csv():
    """Extract Solow inputs (GDP, CAPITAL, LABOR) + WDI controls + PWT HC."""
    print(f"\n{'═'*70}")
    print("STEP 1: Extract data from CSV files")
    print(f"{'═'*70}")

    # Validate data files exist
    for f, label in [(WB_CSV, 'World Bank'), (PWT_CSV, 'PWT'),
                     (WIPO_SPANISH, 'WIPO Spanish'), (WIPO_PORTUGUESE, 'WIPO Portuguese')]:
        if not f.exists():
            print(f"  ERROR: {label} file not found: {f}")
            sys.exit(1)
        print(f"  ✓ {label}: {f.name}")

    raw = pd.read_csv(WB_CSV)
    raw = raw[(raw['year'] >= START_YR) & (raw['year'] <= END_YR)
              & raw['country_code'].isin(COUNTRIES)]

    # Solow inputs — use GFCF for PIM capital stock construction
    tfp_codes = {
        'NY.GDP.MKTP.KD': 'GDP',
        'NE.GDI.FTOT.KD': 'INVESTMENT',   # Gross fixed capital formation (for PIM)
        'SL.TLF.TOTL.IN': 'LABOR',
    }
    tfp_raw = raw[raw['indicator_code'].isin(tfp_codes)].copy()
    tfp_raw['var_name'] = tfp_raw['indicator_code'].map(tfp_codes)
    solow = tfp_raw.pivot_table(
        index=['country_code', 'year'], columns='var_name',
        values='value', aggfunc='first',
    ).reset_index()
    solow = solow.rename(columns={'country_code': 'Country', 'year': 'Year'})

    # Full balanced panel frame
    all_years = list(range(START_YR, END_YR + 1))
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

    # ILOSTAT total employment (EMP_TEMP_SEX_AGE_NB, thousands → persons)
    ilostat_labor = load_ilostat_employment()
    solow = solow.merge(ilostat_labor, on=['Country', 'Year'], how='left')
    # Replace WDI labor force with ILOSTAT employment where available
    has_ilostat = solow['LABOR_ILOSTAT'].notna()
    solow.loc[has_ilostat, 'LABOR'] = solow.loc[has_ilostat, 'LABOR_ILOSTAT']
    n_replaced = has_ilostat.sum()
    n_wdi_fallback = (~has_ilostat & solow['LABOR'].notna()).sum()
    print(f"\n  LABOR source: {n_replaced} ILOSTAT employment, {n_wdi_fallback} WDI fallback")

    # ── Perpetual Inventory Method: K_t = I_t + (1-δ)·K_{t-1} ──
    # Initialize K_0 = I_0 / (g + δ) where g = avg investment growth rate
    print(f"\n  Constructing capital stock via PIM (δ={DELTA})...")
    solow['CAPITAL'] = np.nan
    for c in COUNTRIES:
        mask = (solow['Country'] == c) & solow['INVESTMENT'].notna()
        inv = solow.loc[mask, 'INVESTMENT'].values
        years_c = solow.loc[mask, 'Year'].values
        if len(inv) < 3:
            continue
        # Average investment growth rate for initialization
        growth_rates = []
        for i in range(1, len(inv)):
            if inv[i-1] > 0:
                growth_rates.append(inv[i] / inv[i-1] - 1)
        g = np.mean(growth_rates) if growth_rates else 0.03
        g = max(g, 0.01)  # Floor at 1%
        K0 = inv[0] / (g + DELTA)
        # Build capital stock series
        K = np.zeros(len(inv))
        K[0] = K0
        for t in range(1, len(inv)):
            K[t] = inv[t] + (1 - DELTA) * K[t-1]
        # Assign back
        idx = solow.index[(solow['Country'] == c) & solow['INVESTMENT'].notna()]
        solow.loc[idx, 'CAPITAL'] = K
        print(f"    {c}: K₀={K0:.2e}, K_T={K[-1]:.2e} ({len(K)} periods)")

    for col in ['TFP', 'TFP_Growth', 'GDP_Growth']:
        solow[col] = np.nan

    print(f"\n  Solow inputs: {solow.shape}")
    for var in ['GDP', 'INVESTMENT', 'CAPITAL', 'LABOR', 'HC_index']:
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

    # No interpolation: missing control values remain NaN and propagate to regressions
    ctrl_cols = [c for c in wdi.columns if c not in ['country', 'year']]
    for col in ctrl_cols:
        nn = wdi[col].notna().sum()
        print(f"    {col}: {nn}/{len(wdi)} non-null ({nn/len(wdi)*100:.0f}%)")

    if 'GDPPC_constant2015' in wdi.columns:
        wdi['LNPGDP_constant2015'] = np.log(
            pd.to_numeric(wdi['GDPPC_constant2015'], errors='coerce'))
    if 'GDPPC_ppp' in wdi.columns:
        wdi['LNPGDP_ppp'] = np.log(
            pd.to_numeric(wdi['GDPPC_ppp'], errors='coerce'))

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
    where α=0.35 (capital share), effective labor = L × HC.
    This embeds human capital as a labor-augmenting factor rather
    than treating it as a separate input.
    """
    df = df.copy().sort_values(['Country', 'Year'])
    valid = df[['GDP', 'CAPITAL', 'LABOR', 'HC_index']].notna().all(axis=1)
    # Effective labor = L × HC
    eff_labor = df.loc[valid, 'LABOR'] * df.loc[valid, 'HC_index']
    df.loc[valid, 'TFP'] = (
        df.loc[valid, 'GDP'] /
        (df.loc[valid, 'CAPITAL'] ** alpha *
         eff_labor ** (1 - alpha))
    )
    df['TFP_Growth'] = df.groupby('Country')['TFP'].pct_change() * 100
    df['GDP_Growth'] = df.groupby('Country')['GDP'].pct_change() * 100
    return df


def _solve_dea_vrs_output(y0, x0, Y_ref, X_ref):
    """Solve DEA VRS output-oriented LP via vertex enumeration."""
    N = len(Y_ref); m = X_ref.shape[1]; EPS = 1e-9; best_theta = 0.0
    for s in range(1, min(m + 1, N) + 1):
        for S_idx in combinations(range(N), s):
            S = list(S_idx); Y_S = Y_ref[S]; X_S = X_ref[S, :]
            if s == 1:
                if np.all(X_S[0] <= x0 + EPS):
                    theta = float(Y_S[0]) / y0
                    if theta > best_theta:
                        best_theta = theta
                continue
            n_binding = s - 1
            if n_binding > m:
                continue
            for binding in combinations(range(m), n_binding):
                b_arr = list(binding)
                A = np.vstack([X_S[:, b_arr].T, np.ones((1, s))])
                b = np.append(x0[b_arr], 1.0)
                try:
                    if np.linalg.matrix_rank(A) < s:
                        continue
                    lam = np.linalg.solve(A, b)
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
    return 1.0 / best_theta if best_theta > 1e-12 else 1.0


def compute_malmquist_tfp(df):
    """
    DEA-Malmquist TFP change index (Färe et al. 1992).
    Decomposes into efficiency change and technical change.
    """
    years = sorted(df['Year'].unique())
    results = []
    input_cols = ['CAPITAL', 'LABOR', 'HC_index']
    output_col = 'GDP'
    print(f"\n  {df.Country.nunique()} countries, {len(years)-1} periods")

    for t_idx, yt in enumerate(years[:-1]):
        yt1 = years[t_idx + 1]
        dt = df[df.Year == yt].sort_values('Country').reset_index(drop=True)
        dt1 = df[df.Year == yt1].sort_values('Country').reset_index(drop=True)
        ok_t = set(dt.dropna(subset=input_cols + [output_col])['Country'])
        ok_t1 = set(dt1.dropna(subset=input_cols + [output_col])['Country'])
        common = sorted(ok_t & ok_t1)
        if len(common) < 2:
            continue
        dt = dt[dt.Country.isin(common)].set_index('Country').loc[common]
        dt1 = dt1[dt1.Country.isin(common)].set_index('Country').loc[common]
        Y_t = dt[output_col].values.astype(float)
        X_t = dt[input_cols].values.astype(float)
        Y_t1 = dt1[output_col].values.astype(float)
        X_t1 = dt1[input_cols].values.astype(float)
        if t_idx % 6 == 0:
            print(f"    {yt}→{yt1} ({len(common)} ctys)", flush=True)
        for ci, cty in enumerate(common):
            d_t_t = _solve_dea_vrs_output(Y_t[ci], X_t[ci], Y_t, X_t)
            d_t1_t1 = _solve_dea_vrs_output(Y_t1[ci], X_t1[ci], Y_t1, X_t1)
            d_t_t1 = _solve_dea_vrs_output(Y_t1[ci], X_t1[ci], Y_t, X_t)
            d_t1_t = _solve_dea_vrs_output(Y_t[ci], X_t[ci], Y_t1, X_t1)
            eff_ch = d_t1_t1 / d_t_t if d_t_t > 0 else 1.0
            tfp_ch = (np.sqrt((d_t1_t1 / d_t_t1) * (d_t1_t / d_t_t))
                      if (d_t_t1 > 0 and d_t_t > 0) else eff_ch)
            tech_ch = tfp_ch / eff_ch if eff_ch > 0 else 1.0
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
    long['AI_Patents'] = pd.to_numeric(long['AI_Patents'], errors='coerce')
    # No fillna(0): blank WIPO cells remain NaN
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

def build_merged_dataset(patents, solow, malmquist, wdi):
    """Merge all data sources into a single panel dataset."""
    df = solow[['Country', 'CountryName', 'Year', 'INVESTMENT', 'CAPITAL', 'GDP',
                'HC_index', 'LABOR', 'TFP', 'TFP_Growth', 'GDP_Growth']].copy()

    # AI patents
    pat = patents.rename(columns={'year': 'Year', 'country': 'Country'})[
        ['Year', 'Country', 'AI_Patents']]
    df = df.merge(pat, on=['Country', 'Year'], how='left')
    # No fillna(0): country-years absent from WIPO file remain NaN

    # Malmquist
    mq = malmquist[['Country', 'Year_t1', 'TFP_Change',
                     'Efficiency_Change', 'Technical_Change']].rename(
        columns={'Year_t1': 'Year'})
    df = df.merge(mq, on=['Country', 'Year'], how='left')

    # WDI controls
    wdi_r = wdi.rename(columns={'country': 'Country', 'year': 'Year'})
    wdi_keep = [c for c in wdi_r.columns if c in [
        'Country', 'Year', 'LNPGDP_constant2015', 'GDPPC_constant2015',
        'GDPPC_ppp', 'LNPGDP_ppp', 'FIN_credit_private',
        'FIN_credit_financial', 'FIN_deposits',
        'GOV_consumption', 'GOV_expense', 'OPEN_trade',
        'FDI_inflows', 'URB_urban_pop',
        'INF_internet', 'INF_broadband', 'INF_mobile', 'INF_telephone',
        'INST_rule_of_law',
    ]]
    df = df.merge(wdi_r[wdi_keep], on=['Country', 'Year'], how='left')

    # Derived variables
    df['LN_AI_Patents'] = np.log1p(df['AI_Patents'])
    df['LN_HC_index'] = np.log(df['HC_index'].clip(lower=0.01))
    df['AI_Patents_L1'] = df.groupby('Country')['AI_Patents'].shift(1)
    df['LN_AI_Patents_L1'] = np.log1p(df['AI_Patents_L1'])
    df['AI_Patents_L2'] = df.groupby('Country')['AI_Patents'].shift(2)
    df['LN_AI_Patents_L2'] = np.log1p(df['AI_Patents_L2'])
    # NaN-safe cumsum: NaN in the sequence propagates forward to avoid spurious stock levels
    df['AI_Patent_Stock'] = (df.groupby('Country')['AI_Patents']
                               .transform(lambda s: s.where(s.notna()).cumsum()))
    df['LN_AI_Patent_Stock'] = np.log1p(df['AI_Patent_Stock'])

    # Interaction terms — v4 moderators
    # H3: institutional quality — Rule of Law (primary moderation hypothesis)
    df['AI_x_RL']        = df['LN_AI_Patents'] * df['INST_rule_of_law']
    # H4: mobile cellular subscriptions per 100 (primary digital moderation)
    df['AI_x_MOBILE']    = df['LN_AI_Patents'] * df['INF_mobile']
    # H4r: fixed broadband per 100 (robustness check for H4)
    df['AI_x_BROADBAND'] = df['LN_AI_Patents'] * df['INF_broadband']

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
    """Significance stars."""
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


def fixed_effects(df, y_col, x_cols, ent='Country'):
    """Fixed effects (within) estimator with cluster-robust SE."""
    sub = df[[y_col] + x_cols + [ent]].dropna().copy().reset_index(drop=True)
    for c in [y_col] + x_cols:
        sub[c + '_dm'] = sub[c] - sub.groupby(ent)[c].transform('mean')
    y = sub[y_col + '_dm'].values
    X = np.column_stack([sub[c + '_dm'].values for c in x_cols])
    cl = sub[ent].values
    beta = _ols_coef(X, y)
    resid = y - X @ beta
    n, k = X.shape
    Ne = sub[ent].nunique()
    se = _cluster_se(X, resid, cl)
    t, p = _t_and_p(beta, se, n - Ne - k)
    return dict(
        estimator='FE', y=y_col, obs=n,
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
    """Common Correlated Effects Fixed Effects estimator (Pesaran 2006)."""
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


def hausman_test(df, y_col, x_cols, ent='Country', tcol='Year'):
    """Mundlak-variant Hausman specification test (FE vs RE)."""
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    if len(sub) < 20:
        return None
    mc = []
    for c in x_cols:
        m = c + '_emean'
        sub[m] = sub.groupby(ent)[c].transform('mean')
        mc.append(m)
    try:
        r = random_effects(sub, y_col, x_cols + mc, ent, tcol)
    except Exception:
        return None
    mcoefs = np.array([r['coef'].get(m, 0) for m in mc])
    mses = np.array([r['se'].get(m, 1e10) for m in mc])
    chi2 = float(np.sum((mcoefs / np.where(mses > 0, mses, 1e10))**2))
    k = len(mc)
    try:
        z = ((chi2 / k)**(1/3) - (1 - 2 / (9 * k))) / sqrt(2 / (9 * k))
        p = float(erfc(max(z, 0) / sqrt(2)))
    except Exception:
        p = 1.0
    return {
        'chi2': round(chi2, 3), 'df': k, 'p': round(p, 4),
        'conclusion': 'Reject RE → use FE' if p < 0.05 else 'Cannot reject RE',
    }


def pesaran_cd_test(df, y_col, x_cols, ent='Country', tcol='Year'):
    """
    Pesaran (2004) CD test for cross-sectional dependence.
    Reports CD statistic and p-value.
    """
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    # Compute FE residuals
    for c in [y_col] + x_cols:
        sub[c + '_dm'] = sub[c] - sub.groupby(ent)[c].transform('mean')
    y = sub[y_col + '_dm'].values
    X = np.column_stack([sub[c + '_dm'].values for c in x_cols])
    beta = _ols_coef(X, y)
    sub['resid'] = y - X @ beta

    countries = sorted(sub[ent].unique())
    N = len(countries)
    T_common = sub.groupby(ent).size().min()

    # Pairwise correlation of residuals
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
# H2: MEDIATION ANALYSIS (Baron & Kenny 1986)
# ══════════════════════════════════════════════════════════════════════════════

def mediation_analysis(df, y_col, x_ai='LN_AI_Patents', mediator='LN_HC_index',
                       controls=None, ent='Country'):
    """
    Three-step mediation (Baron & Kenny 1986):
      Step 1: Y = c*AI + controls           → total effect (c)
      Step 2: M = a*AI + controls            → AI → mediator (a path)
      Step 3: Y = c'*AI + b*M + controls     → direct (c') + mediator (b)
    Indirect = a × b; Mediation % = |a×b| / |c|
    """
    if controls is None:
        controls = CONTROLS_PARS.copy()

    # Remove mediator from controls if present
    ctrls_no_med = [c for c in controls if c != mediator]
    results = {}

    for est_name, est_fn in [('FE', fixed_effects), ('RE', random_effects)]:
        try:
            # Step 1: Total effect (c path)
            step1 = est_fn(df, y_col, [x_ai] + ctrls_no_med)
            c_total = step1['coef'].get(x_ai, np.nan)
            c_p = step1['p'].get(x_ai, np.nan)

            # Step 2: AI → Mediator (a path)
            step2 = est_fn(df, mediator, [x_ai] + ctrls_no_med)
            a_path = step2['coef'].get(x_ai, np.nan)
            a_p = step2['p'].get(x_ai, np.nan)

            # Step 3: Direct effect + mediator (c' and b paths)
            step3 = est_fn(df, y_col, [x_ai, mediator] + ctrls_no_med)
            c_prime = step3['coef'].get(x_ai, np.nan)
            c_prime_p = step3['p'].get(x_ai, np.nan)
            b_path = step3['coef'].get(mediator, np.nan)
            b_p = step3['p'].get(mediator, np.nan)

            indirect = a_path * b_path
            mediation_pct = (abs(indirect) / abs(c_total) * 100
                             if abs(c_total) > 1e-10 else 0.0)

            results[est_name] = {
                'step1_c': round(c_total, 5), 'step1_p': round(c_p, 4),
                'step2_a': round(a_path, 5), 'step2_p': round(a_p, 4),
                'step3_c_prime': round(c_prime, 5), 'step3_c_prime_p': round(c_prime_p, 4),
                'step3_b': round(b_path, 5), 'step3_b_p': round(b_p, 4),
                'indirect_ab': round(indirect, 5),
                'mediation_pct': round(mediation_pct, 1),
                'obs': step3['obs'],
            }
        except Exception as e:
            results[est_name] = {'error': str(e)}

    return results


# ══════════════════════════════════════════════════════════════════════════════
# H3-H4: MODERATION ANALYSIS (Interaction Terms)
# ══════════════════════════════════════════════════════════════════════════════

def moderation_analysis(df, y_col, x_ai='LN_AI_Patents',
                        moderator_var=None, interaction_var=None,
                        controls=None, ent='Country'):
    """
    Moderation via interaction term:
      Y = β1*AI + β2*Moderator + β3*(AI×Moderator) + controls + FE
    H3 predicts β3 > 0 (institutional quality), H4 predicts β3 > 0 (digital/mobile)
    """
    if controls is None:
        controls = CONTROLS_PARS.copy()

    # Ensure moderator is in controls
    all_ctrls = controls.copy()
    if moderator_var and moderator_var not in all_ctrls:
        all_ctrls.append(moderator_var)

    x_cols = [x_ai, interaction_var] + all_ctrls
    # Remove duplicates while preserving order
    seen = set()
    x_cols_unique = []
    for c in x_cols:
        if c not in seen:
            seen.add(c)
            x_cols_unique.append(c)
    x_cols = x_cols_unique

    results = {}
    for est_name, est_fn in [('FE', fixed_effects), ('RE', random_effects)]:
        try:
            r = est_fn(df, y_col, x_cols)
            results[est_name] = {
                'beta_AI': round(r['coef'].get(x_ai, np.nan), 5),
                'p_AI': round(r['p'].get(x_ai, np.nan), 4),
                'beta_interaction': round(r['coef'].get(interaction_var, np.nan), 6),
                'se_interaction': round(r['se'].get(interaction_var, np.nan), 6),
                'p_interaction': round(r['p'].get(interaction_var, np.nan), 4),
                'beta_moderator': round(r['coef'].get(moderator_var, np.nan), 5),
                'obs': r['obs'], 'r2': round(r['r2'], 4),
            }
        except Exception as e:
            results[est_name] = {'error': str(e)}

    return results


# ══════════════════════════════════════════════════════════════════════════════
# H5: PANEL QUANTILE REGRESSION
# ══════════════════════════════════════════════════════════════════════════════

def _quantile_loss(u, tau):
    """Check (asymmetric) loss function for quantile regression."""
    return np.where(u >= 0, tau * u, (tau - 1) * u).sum()


def _quantile_reg_irls(y, X, tau, max_iter=500, tol=1e-8):
    """
    Iteratively Reweighted Least Squares (IRLS) for quantile regression.
    Uses the interior-point / MM approach with proper tau-specific initialization.
    """
    n, k = X.shape

    # Initialize with tau-weighted quantile-aware starting point
    # Sort by y, take the tau-th fraction as reference
    sort_idx = np.argsort(y)
    tau_idx = int(tau * n)
    tau_idx = max(k, min(tau_idx, n - 1))
    # Weighted OLS initialization: weight observations near the tau-th quantile
    w_init = np.exp(-0.5 * ((np.arange(n) - tau_idx) / (0.2 * n))**2)
    w_init = w_init[np.argsort(sort_idx)]  # back to original order
    W_init = np.diag(w_init)
    try:
        beta = np.linalg.solve(X.T @ W_init @ X, X.T @ W_init @ y)
    except np.linalg.LinAlgError:
        beta = _ols_coef(X, y)

    eps_scale = max(1e-6 * np.std(y), 1e-12)

    for iteration in range(max_iter):
        resid = y - X @ beta
        # Asymmetric weights for quantile loss
        abs_resid = np.maximum(np.abs(resid), eps_scale)
        weights = np.where(resid >= 0, tau / abs_resid, (1 - tau) / abs_resid)

        XtWX = X.T * weights @ X
        XtWy = X.T * weights @ y
        try:
            beta_new = np.linalg.solve(XtWX, XtWy)
        except np.linalg.LinAlgError:
            beta_new = np.linalg.lstsq(XtWX, XtWy, rcond=None)[0]

        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new

    return beta


def panel_quantile_regression(df, y_col, x_cols, ent='Country',
                              quantiles=(0.10, 0.25, 0.50, 0.75, 0.90),
                              n_bootstrap=500):
    """
    Panel quantile regression with entity fixed effects.
    Uses IRLS estimation with bootstrap inference.

    Implements Koenker (2004) / Lamarche (2010) approach:
      Q_τ(Y|X) = α_i + X'β_τ
    where α_i are entity-specific intercepts.
    """
    sub = df[[y_col] + x_cols + [ent]].dropna().copy().reset_index(drop=True)

    # Canay (2011) two-step approach for panel quantile regression:
    # Step 1: Estimate FE model via OLS, extract fixed effects
    fe_result = fixed_effects(df, y_col, x_cols, ent)
    fe_betas = np.array([fe_result['coef'].get(c, 0) for c in x_cols])

    # Step 2: Compute y_hat_fe = X*beta_fe, then alpha_i = mean(y - X*beta_fe) per entity
    X_vals = sub[x_cols].values
    y_vals = sub[y_col].values
    xb = X_vals @ fe_betas
    sub['_resid_fe'] = y_vals - xb
    alpha_i = sub.groupby(ent)['_resid_fe'].transform('mean').values

    # Step 3: y_tilde = y - alpha_i (remove fixed effects, keep level variation)
    y_dm = y_vals - alpha_i
    X_dm = np.column_stack([np.ones(len(sub)), X_vals])
    x_cols_with_const = ['const'] + x_cols

    results = {}
    for tau in quantiles:
        print(f"    τ = {tau:.2f}", end='', flush=True)

        # Point estimates
        beta = _quantile_reg_irls(y_dm, X_dm, tau)

        # Bootstrap inference (paired cluster bootstrap)
        entities = sub[ent].unique()
        n_ent = len(entities)
        boot_betas = []
        for b_iter in range(n_bootstrap):
            # Resample clusters (countries) with replacement
            boot_ents = np.random.choice(entities, size=n_ent, replace=True)
            boot_idx = []
            for e in boot_ents:
                boot_idx.extend(sub.index[sub[ent] == e].tolist())
            boot_y = y_dm[boot_idx]
            boot_X = X_dm[boot_idx]
            try:
                b_beta = _quantile_reg_irls(boot_y, boot_X, tau)
                boot_betas.append(b_beta)
            except Exception:
                continue

        boot_betas = np.array(boot_betas)
        if len(boot_betas) < 50:
            print(" (insufficient bootstrap samples)")
            continue

        se = np.std(boot_betas, axis=0)
        ci_lo = np.percentile(boot_betas, 2.5, axis=0)
        ci_hi = np.percentile(boot_betas, 97.5, axis=0)

        # P-values from bootstrap distribution
        p_vals = np.array([
            2 * min(np.mean(boot_betas[:, j] <= 0),
                    np.mean(boot_betas[:, j] >= 0))
            for j in range(len(x_cols_with_const))
        ])

        results[f'q{int(tau*100):02d}'] = {
            'tau': tau, 'obs': len(sub),
            'coef': dict(zip(x_cols_with_const, np.round(beta, 6))),
            'se': dict(zip(x_cols_with_const, np.round(se, 6))),
            'p': dict(zip(x_cols_with_const, np.round(p_vals, 4))),
            'ci_lo': dict(zip(x_cols_with_const, np.round(ci_lo, 6))),
            'ci_hi': dict(zip(x_cols_with_const, np.round(ci_hi, 6))),
            'n_boot': len(boot_betas),
        }
        # Report AI coefficient (index 1, after const)
        ai_idx = 1  # x_cols[0] is at position 1 in x_cols_with_const
        c = beta[ai_idx]; p = p_vals[ai_idx]
        print(f"  β(AI)={c:+.5f}  p={p:.3f}{_stars(p)}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# DESCRIPTIVE STATISTICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_descriptives(df):
    """Compute summary statistics for the merged panel (Table 5.1)."""
    vars_desc = {
        'TFP': 'Solow TFP',
        'TFP_Growth': 'Solow TFP Growth (%)',
        'TFP_Change': 'Malmquist TFP Change',
        'AI_Patents': 'AI Patent Count',
        'LN_AI_Patents': 'ln(AI Patents + 1)',
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
        rows.append({
            'Variable': label,
            'N': len(s), 'Mean': round(s.mean(), 4),
            'Std': round(s.std(), 4),
            'Min': round(s.min(), 4), 'Max': round(s.max(), 4),
        })
    return pd.DataFrame(rows)


def compute_correlation_matrix(df):
    """Correlation matrix for key variables."""
    vars_corr = ['LN_AI_Patents', 'LNPGDP_constant2015', 'FIN_credit_private',
                 'OPEN_trade', 'INF_internet', 'LN_HC_index']
    sub = df[vars_corr].dropna()
    return sub.corr()


# ══════════════════════════════════════════════════════════════════════════════
# LATEX TABLE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _write_latex_table(spec, spec_label, dv_label, filename, out_dir,
                       focus_vars, vlt, eo, dec=4):
    """Write a LaTeX regression table."""
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
                c = r['coef'][v]
                s = r['se'][v]
                pv = r['p'][v]
                cr += f' & {c:+.{dec}f}\\textsuperscript{{{_stars(pv)}}}'
                sr += f' & ({s:.{dec}f})'
            else:
                cr += ' & ---'
                sr += ' & '
        L.append(cr + r' \\')
        L.append(sr + r' \\[2pt]')
    L.append(r'\midrule')
    for rl, fn in [
        ('Observations', lambda e: str(spec[e]['obs']) if e in spec else '---'),
        ('$R^2$', lambda e: f"{spec[e]['r2']:.3f}" if e in spec else '---'),
        ('Entity FE', lambda e: 'Yes' if e in ('FE', 'CCEFE') else 'No'),
        ('CS Averages', lambda e: 'Yes' if e in ('CCEP', 'CCEFE') else 'No'),
    ]:
        L.append(rl + ' & ' + ' & '.join(fn(e) for e in eo) + r' \\')
    h = spec.get('Hausman')
    if h:
        L.append(r'\midrule')
        L.append(f"Mundlak $\\chi^2$ & \\multicolumn{{{len(eo)}}}{{c}}"
                 f"{{{h['chi2']:.2f} (p={h['p']:.3f})}}" + r' \\')
    L += [
        r'\bottomrule', r'\end{tabular}',
        r'\begin{tablenotes}', r'\footnotesize',
        r'\item \textit{Notes:} Cluster-robust SE (by country). '
        r'$^{***}p<0.01$, $^{**}p<0.05$, $^{*}p<0.10$.',
        f'\\item 7 LAC countries, {START_YR}--{END_YR}. '
        r'Human capital: PWT 10.01 index.',
        r'\end{tablenotes}', r'\end{table}',
    ]
    (out_dir / filename).write_text('\n'.join(L))


# ══════════════════════════════════════════════════════════════════════════════
# JSON SERIALIZER
# ══════════════════════════════════════════════════════════════════════════════

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
    if isinstance(o, list):
        return [_json_safe(i) for i in o]
    return o


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("╔" + "═" * 68 + "╗")
    print("║  DISSERTATION v3 PIPELINE                                          ║")
    print("║  AI Adoption → TFP in Latin America                                ║")
    print("║  7 Countries, 1992–2024, PWT HC                                    ║")
    print("╚" + "═" * 68 + "╝")

    # ── Step 1: Extract data ────────────────────────────────────────────
    solow_df, wdi_df = extract_data_from_csv()

    # ── Step 2: Solow TFP ──────────────────────────────────────────────
    print(f"\n{'═'*70}\nSTEP 2: Solow TFP — two-factor (α={ALPHA}, 1−α={1-ALPHA:.2f}, labor-augmenting HC)\n{'═'*70}")
    solow_df = compute_solow_tfp(solow_df)
    tfp_valid = solow_df['TFP'].notna().sum()
    print(f"  TFP computed: {tfp_valid}/{len(solow_df)} obs")
    for c in COUNTRIES:
        s = solow_df[solow_df.Country == c]['TFP']
        print(f"    {c}: mean={s.mean():.4e} [{s.notna().sum()} obs]")
    solow_df.to_csv(RESULTS_DIR / 'solow_tfp_dissertation_v4_noimput.csv', index=False)

    # ── Step 3: Malmquist DEA ──────────────────────────────────────────
    print(f"\n{'═'*70}\nSTEP 3: Malmquist DEA TFP Change\n{'═'*70}")
    dea_df = solow_df.dropna(subset=['GDP', 'CAPITAL', 'LABOR', 'HC_index'])
    print(f"  DEA-ready: {len(dea_df)} obs")
    mq = compute_malmquist_tfp(dea_df)
    print(f"\n  Results: {len(mq)} rows")
    for c in sorted(mq.Country.unique()):
        g = mq[mq.Country == c]['TFP_Change']
        print(f"    {c}: geom_mean={np.exp(np.log(g).mean()):.4f} (n={len(g)})")
    mq.to_csv(RESULTS_DIR / 'malmquist_dissertation_v4_noimput.csv', index=False)

    # ── Step 4: WIPO AI Patents ────────────────────────────────────────
    print(f"\n{'═'*70}\nSTEP 4: WIPO AI Patents\n{'═'*70}")
    patents = load_ai_patents()

    # ── Step 5: Merge ──────────────────────────────────────────────────
    print(f"\n{'═'*70}\nSTEP 5: Build Merged Panel\n{'═'*70}")
    merged = build_merged_dataset(patents, solow_df, mq, wdi_df)
    print(f"  Panel: {merged.shape[0]} obs, {merged.Country.nunique()} countries, "
          f"{merged.Year.min()}-{merged.Year.max()}")
    for col in ['TFP', 'TFP_Change', 'AI_Patents', 'LNPGDP_constant2015',
                'FIN_credit_private', 'HC_index']:
        if col in merged.columns:
            nn = merged[col].notna().sum()
            print(f"    {col:<25} {nn}/{len(merged)} ({nn/len(merged)*100:.0f}%)")
    merged.to_csv(RESULTS_DIR / 'merged_dissertation_v4_noimput.csv', index=False)

    # Descriptives (Table 5.1)
    desc = compute_descriptives(merged)
    desc.to_csv(OUT_DIR / 'descriptive_statistics.csv', index=False)
    corr = compute_correlation_matrix(merged)
    corr.to_csv(OUT_DIR / 'correlation_matrix.csv')

    # ── Step 6: H1 — Benchmark Regressions (Chapter 5) ────────────────
    print(f"\n{'═'*70}\nSTEP 6: H1 — Benchmark Regressions (5 Estimators)\n{'═'*70}")
    df = merged.copy()
    df['ln_TFP'] = np.log(df['TFP'].clip(lower=1e-15))

    specs = [
        ('Solow_full',     'ln_TFP',     CONTROLS_FULL),
        ('Malmquist_full', 'TFP_Change', CONTROLS_FULL),
        ('Solow_pars',     'ln_TFP',     CONTROLS_PARS),
        ('Malmquist_pars', 'TFP_Change', CONTROLS_PARS),
    ]

    lag_specs = [
        ('Solow_lag1',      'ln_TFP',     ['LN_AI_Patents_L1'] + CONTROLS_PARS),
        ('Malmquist_lag1',  'TFP_Change', ['LN_AI_Patents_L1'] + CONTROLS_PARS),
        ('Solow_stock',     'ln_TFP',     ['LN_AI_Patent_Stock'] + CONTROLS_PARS),
        ('Malmquist_stock', 'TFP_Change', ['LN_AI_Patent_Stock'] + CONTROLS_PARS),
    ]

    eo = ['OLS', 'FE', 'RE', 'CCEP', 'CCEFE']
    all_results = {}

    for spec_name, y_col, ctrls in specs:
        x_cols = ['LN_AI_Patents'] + ctrls
        print(f"\n{'─'*70}\n  {spec_name}  DV={y_col}\n{'─'*70}")
        sr = {}
        for en, fn in [('OLS', pooled_ols), ('FE', fixed_effects),
                        ('RE', random_effects), ('CCEP', cce_pooled),
                        ('CCEFE', cce_fe)]:
            try:
                r = fn(df, y_col, x_cols)
                sr[en] = r
                c = r['coef']['LN_AI_Patents']
                p = r['p']['LN_AI_Patents']
                ex = f" θ={r.get('theta', 0):.3f}" if en == 'RE' else ''
                print(f"  {en:<6} β(AI)={c:+.5f}  p={p:.3f}{_stars(p):<4} "
                      f"N={r['obs']} R²={r['r2']:.3f}{ex}")
            except Exception as e:
                print(f"  {en:<6} ERROR: {e}")
            if en == 'RE' and 'FE' in sr and 'RE' in sr:
                try:
                    h = hausman_test(df, y_col, x_cols)
                    if h:
                        print(f"  Hausman: χ²={h['chi2']:.2f} p={h['p']:.3f} "
                              f"→ {h['conclusion']}")
                        sr['Hausman'] = h
                except Exception:
                    pass
        all_results[spec_name] = sr

    # Lag / stock robustness (Table 5.3)
    for spec_name, y_col, x_cols in lag_specs:
        ai_var = x_cols[0]
        print(f"\n{'─'*70}\n  {spec_name}  DV={y_col}  AI_var={ai_var}\n{'─'*70}")
        sr = {}
        for en, fn in [('OLS', pooled_ols), ('FE', fixed_effects),
                        ('RE', random_effects)]:
            try:
                r = fn(df, y_col, x_cols)
                sr[en] = r
                c = r['coef'][ai_var]
                p = r['p'][ai_var]
                print(f"  {en:<6} β(AI)={c:+.5f}  p={p:.3f}{_stars(p):<4} "
                      f"N={r['obs']} R²={r['r2']:.3f}")
            except Exception as e:
                print(f"  {en:<6} ERROR: {e}")
        all_results[spec_name] = sr

    # Cross-sectional dependence test (Pesaran CD)
    print(f"\n{'─'*70}\n  Pesaran CD Test for Cross-Sectional Dependence\n{'─'*70}")
    cd_results = {}
    for y_col, label in [('ln_TFP', 'Solow TFP'), ('TFP_Change', 'Malmquist TFP')]:
        cd = pesaran_cd_test(df, y_col, ['LN_AI_Patents'] + CONTROLS_PARS)
        if cd:
            cd_results[label] = cd
            print(f"  {label}: {cd['conclusion']}")
    all_results['pesaran_cd'] = cd_results

    # ── Step 7: H2 — Mediation Analysis (Chapter 6) ───────────────────
    print(f"\n{'═'*70}\nSTEP 7: H2 — Mediation (AI → HC → TFP)\n{'═'*70}")
    h2_results = {}
    for y_col, label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {label} TFP:")
        med = mediation_analysis(df, y_col)
        h2_results[label] = med
        for est, r in med.items():
            if 'error' in r:
                print(f"    {est}: ERROR {r['error']}")
            else:
                print(f"    {est}: c={r['step1_c']:+.5f}(p={r['step1_p']:.3f}), "
                      f"a={r['step2_a']:+.5f}(p={r['step2_p']:.3f}), "
                      f"b={r['step3_b']:+.5f}(p={r['step3_b_p']:.3f}), "
                      f"c'={r['step3_c_prime']:+.5f}(p={r['step3_c_prime_p']:.3f}), "
                      f"indirect={r['indirect_ab']:+.5f}, "
                      f"mediation={r['mediation_pct']:.1f}%")
    all_results['H2_mediation'] = h2_results

    # ── Step 8: H3 — Institutional Quality Moderation (Rule of Law) ───────
    print(f"\n{'═'*70}\nSTEP 8: H3 — Institutional Quality Moderation (RL.EST)\n{'═'*70}")
    print("  Moderator: Rule of Law estimate (World Governance Indicators)")
    print("  Hypothesis: stronger rule of law amplifies AI-TFP complementarity")
    h3_results = {}
    for y_col, label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {label} TFP:")
        mod = moderation_analysis(
            df, y_col,
            moderator_var='INST_rule_of_law',
            interaction_var='AI_x_RL',
            controls=CONTROLS_PARS + ['INST_rule_of_law'],
        )
        h3_results[label] = mod
        for est, r in mod.items():
            if 'error' in r:
                print(f"    {est}: ERROR {r['error']}")
            else:
                print(f"    {est}: β(AI)={r['beta_AI']:+.5f}(p={r['p_AI']:.3f}), "
                      f"β(AI×RL)={r['beta_interaction']:+.6f}"
                      f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")
    all_results['H3_institutional_moderation'] = h3_results

    # ── Step 9: H4 — Mobile Cellular Moderation (primary) ──────────────
    print(f"\n{'═'*70}\nSTEP 9: H4 — Digital Infrastructure Moderation (IT.CEL.SETS.P2)\n{'═'*70}")
    print("  Moderator: Mobile cellular subscriptions per 100 people")
    print("  Rationale: mobile-first AI adoption in LATAM; mobile penetration")
    print("  precedes fixed broadband and drives cloud/SaaS AI tool usage")
    h4_results = {}
    for y_col, label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {label} TFP:")
        mod = moderation_analysis(
            df, y_col,
            moderator_var='INF_mobile',
            interaction_var='AI_x_MOBILE',
            controls=CONTROLS_PARS + ['INF_mobile'],
        )
        h4_results[label] = mod
        for est, r in mod.items():
            if 'error' in r:
                print(f"    {est}: ERROR {r['error']}")
            else:
                print(f"    {est}: β(AI)={r['beta_AI']:+.5f}(p={r['p_AI']:.3f}), "
                      f"β(AI×MOB)={r['beta_interaction']:+.6f}"
                      f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")
    all_results['H4_digital_moderation'] = h4_results

    # ── Step 9r: H4r — Fixed Broadband Robustness ──────────────────────
    print(f"\n{'═'*70}\nSTEP 9r: H4r — Digital Moderation Robustness (IT.NET.BBND.P2)\n{'═'*70}")
    print("  Moderator: Fixed broadband subscriptions per 100 (robustness for H4)")
    h4r_results = {}
    for y_col, label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {label} TFP:")
        mod = moderation_analysis(
            df, y_col,
            moderator_var='INF_broadband',
            interaction_var='AI_x_BROADBAND',
            controls=CONTROLS_PARS + ['INF_broadband'],
        )
        h4r_results[label] = mod
        for est, r in mod.items():
            if 'error' in r:
                print(f"    {est}: ERROR {r['error']}")
            else:
                print(f"    {est}: β(AI)={r['beta_AI']:+.5f}(p={r['p_AI']:.3f}), "
                      f"β(AI×BBND)={r['beta_interaction']:+.6f}"
                      f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")
    all_results['H4r_broadband_moderation'] = h4r_results

    # ── Step 10: H5 — Panel Quantile Regression (Chapter 8) ──────────
    print(f"\n{'═'*70}\nSTEP 10: H5 — Panel Quantile Regression\n{'═'*70}")
    h5_results = {}
    x_qr = ['LN_AI_Patents'] + CONTROLS_PARS
    for y_col, label in [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist')]:
        print(f"\n  {label} TFP:")
        qr = panel_quantile_regression(df, y_col, x_qr, n_bootstrap=500)
        h5_results[label] = qr
    all_results['H5_quantile'] = h5_results

    # ══════════════════════════════════════════════════════════════════
    # SAVE ALL OUTPUTS
    # ══════════════════════════════════════════════════════════════════
    print(f"\n{'═'*70}\nSAVING OUTPUTS\n{'═'*70}")

    # JSON (all results)
    with open(OUT_DIR / 'regression_results.json', 'w') as f:
        json.dump(_json_safe(all_results), f, indent=2)
    print("  ✓ regression_results.json")

    # CSV comparison table (H1 benchmark)
    rows = []
    for sn, sr in all_results.items():
        if sn.startswith('H') or sn == 'pesaran_cd':
            continue
        for en, r in sr.items():
            if en == 'Hausman':
                continue
            ai_var = 'LN_AI_Patents'
            if 'lag1' in sn: ai_var = 'LN_AI_Patents_L1'
            elif 'stock' in sn: ai_var = 'LN_AI_Patent_Stock'
            if ai_var not in r.get('coef', {}):
                continue
            rows.append({
                'spec': sn, 'estimator': en, 'ai_var': ai_var,
                'beta_AI': round(r['coef'][ai_var], 6),
                'se_AI': round(r['se'][ai_var], 6),
                'p_AI': (round(r['p'][ai_var], 4)
                         if not np.isnan(r['p'][ai_var]) else None),
                'stars': _stars(r['p'][ai_var]),
                'r2': round(r['r2'], 4), 'N': r['obs'],
            })
    pd.DataFrame(rows).to_csv(OUT_DIR / 'regression_comparison.csv', index=False)
    print("  ✓ regression_comparison.csv")

    # LaTeX tables (H1)
    fv_full = ['LN_AI_Patents', 'LNPGDP_constant2015', 'FIN_credit_private',
               'OPEN_trade', 'INF_internet', 'LN_HC_index']
    fv_pars = ['LN_AI_Patents', 'LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index']
    vlt = {
        'LN_AI_Patents': r'\ln(\text{AI Patents}+1)',
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
         'Malmquist TFP Change', 'tab_malmquist_full.tex', fv_full),
        ('Solow_pars', 'Solow TFP --- Parsimonious',
         r'$\ln(\text{TFP})$', 'tab_solow_pars.tex', fv_pars),
        ('Malmquist_pars', 'Malmquist TFP Change --- Parsimonious',
         'Malmquist TFP Change', 'tab_malmquist_pars.tex', fv_pars),
    ]:
        dec = 5 if 'Malmquist' in sn else 4
        _write_latex_table(all_results.get(sn, {}), sl, dvl, fn, OUT_DIR,
                           fv, vlt, eo, dec)
        print(f"  ✓ {fn}")

    # Text summary (all hypotheses)
    sep = "─" * 110
    lines = [
        sep,
        f"DISSERTATION v4 RESULTS: AI Patents → TFP, 7 LAC Countries, {START_YR}–{END_YR}",
        sep, '',
        '=' * 110,
        'H1: BENCHMARK REGRESSIONS',
        '=' * 110,
        f"{'Spec':<22}{'Est':<7}{'AI Var':<22}{'β(AI)':>10}{'SE':>10}"
        f"{'p':>8}{'Sig':<5}{'N':>5}{'R²':>7}",
        sep,
    ]
    for sn, sr in all_results.items():
        if sn.startswith('H') or sn == 'pesaran_cd':
            continue
        est_list = eo if sn in [s[0] for s in specs] else ['OLS', 'FE', 'RE']
        for en in est_list:
            r = sr.get(en)
            if not r:
                continue
            ai_var = 'LN_AI_Patents'
            if 'lag1' in sn: ai_var = 'LN_AI_Patents_L1'
            elif 'stock' in sn: ai_var = 'LN_AI_Patent_Stock'
            if ai_var not in r['coef']:
                continue
            c = r['coef'][ai_var]; s = r['se'][ai_var]; pv = r['p'][ai_var]
            lines.append(f"{sn:<22}{en:<7}{ai_var:<22}{c:+10.5f}{s:10.5f}"
                         f"{pv:8.3f} {_stars(pv):<4}{r['obs']:5}{r['r2']:7.3f}")
        lines.append("")

    # CD test
    lines += ['', '=' * 110, 'PESARAN CD TEST', '=' * 110]
    for label, cd in cd_results.items():
        lines.append(f"  {label}: CD={cd['CD']:.3f}, p={cd['p']:.4f}")

    # H2
    lines += ['', '=' * 110, 'H2: MEDIATION ANALYSIS', '=' * 110]
    for label, med in h2_results.items():
        lines.append(f"\n  {label} TFP:")
        for est, r in med.items():
            if 'error' not in r:
                lines.append(f"    {est}: c={r['step1_c']:+.5f}, a={r['step2_a']:+.5f}, "
                             f"b={r['step3_b']:+.5f}, c'={r['step3_c_prime']:+.5f}, "
                             f"indirect={r['indirect_ab']:+.5f}, "
                             f"mediation={r['mediation_pct']:.1f}%")

    # H3
    lines += ['', '=' * 110,
              'H3: INSTITUTIONAL QUALITY MODERATION — Rule of Law (RL.EST)',
              '=' * 110]
    for label, mod in h3_results.items():
        lines.append(f"\n  {label} TFP:")
        for est, r in mod.items():
            if 'error' not in r:
                lines.append(f"    {est}: β(AI)={r['beta_AI']:+.6f}(p={r['p_AI']:.3f})  "
                             f"β(AI×RL)={r['beta_interaction']:+.6f} "
                             f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")

    # H4
    lines += ['', '=' * 110,
              'H4: DIGITAL MODERATION — Mobile Cellular per 100 (IT.CEL.SETS.P2)',
              '=' * 110]
    for label, mod in h4_results.items():
        lines.append(f"\n  {label} TFP:")
        for est, r in mod.items():
            if 'error' not in r:
                lines.append(f"    {est}: β(AI)={r['beta_AI']:+.6f}(p={r['p_AI']:.3f})  "
                             f"β(AI×MOB)={r['beta_interaction']:+.6f} "
                             f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")

    # H4r
    lines += ['', '=' * 110,
              'H4r: DIGITAL MODERATION ROBUSTNESS — Fixed Broadband per 100 (IT.NET.BBND.P2)',
              '=' * 110]
    for label, mod in h4r_results.items():
        lines.append(f"\n  {label} TFP:")
        for est, r in mod.items():
            if 'error' not in r:
                lines.append(f"    {est}: β(AI)={r['beta_AI']:+.6f}(p={r['p_AI']:.3f})  "
                             f"β(AI×BBND)={r['beta_interaction']:+.6f} "
                             f"(p={r['p_interaction']:.3f}){_stars(r['p_interaction'])}")

    # H5
    lines += ['', '=' * 110, 'H5: QUANTILE REGRESSION', '=' * 110]
    for label, qr in h5_results.items():
        lines.append(f"\n  {label} TFP:")
        for qn, r in sorted(qr.items()):
            ai_c = r['coef'].get('LN_AI_Patents', np.nan)
            ai_p = r['p'].get('LN_AI_Patents', np.nan)
            lines.append(f"    τ={r['tau']:.2f}: β(AI)={ai_c:+.5f} "
                         f"(p={ai_p:.3f}){_stars(ai_p)}")

    lines.append('\n' + sep)
    (OUT_DIR / 'regression_summary.txt').write_text("\n".join(lines))
    print("  ✓ regression_summary.txt")

    print(f"\n{'╔' + '═'*68 + '╗'}")
    print(f"{'║'}  PIPELINE COMPLETE                                                {'║'}")
    print(f"{'╚' + '═'*68 + '╝'}")
    print(f"\n  Output directory: {OUT_DIR}")
    print(f"\n  Key outputs:")
    print(f"    • merged_dissertation_v4_noimput.csv      (full panel dataset)")
    print(f"    • regression_results.json          (all H1-H5 results)")
    print(f"    • regression_comparison.csv        (H1 coefficient summary)")
    print(f"    • descriptive_statistics.csv       (Table 5.1)")
    print(f"    • correlation_matrix.csv")
    print(f"    • regression_summary.txt           (full text report)")
    print(f"    • tab_solow_full.tex               (LaTeX Table 5.2a)")
    print(f"    • tab_solow_pars.tex               (LaTeX Table 5.2b)")
    print(f"    • tab_malmquist_full.tex           (LaTeX Table 5.2c)")
    print(f"    • tab_malmquist_pars.tex           (LaTeX Table 5.2d)")

    return all_results, merged, desc, corr


if __name__ == '__main__':
    main()
