"""
TFP-AI Pipeline v5 — Panel B (OECD Publications, N=17, 2016–2024)
==================================================================

Robustness panel using OECD.AI Observatory publication counts as
the AI measure, covering all 17 Latin American countries (excl.
HTI, CUB, VEN).

This script imports shared functions from the main v5 pipeline
(estimators, DEA solver, Driscoll-Kraay SE) and adds Panel B
specific data loading and analysis.

Purpose (Section 4.8 of dissertation):
  (i)  Test sensitivity to AI measurement (publications vs patents)
  (ii) Test generalizability to full LatAm (N=17 vs N=9)
"""

import sys
import warnings
from pathlib import Path
from math import sqrt
from itertools import combinations

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore', category=FutureWarning)

# ── Import shared functions from main v5 pipeline ────────────────────────────
# Add pipeline_v5 dir to path so we can import
sys.path.insert(0, str(Path(__file__).parent))
from run_pipeline_v5 import (
    _solve_dea_output, _ols_coef, _cluster_se, _driscoll_kraay_se,
    _t_and_p, _stars,
    pooled_ols, fixed_effects_twoway, random_effects,
    cce_pooled, cce_fe, pesaran_cd_test,
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — PANEL B
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / 'data'
# OECD.AI publication counts (Panel B robustness). Shipped in the repo under
# data/cat-ai-patents-country-data/ so the pipeline is reproducible.
UPLOADS_DIR = DATA_DIR / 'cat-ai-patents-country-data'
OUT_DIR = Path(__file__).parent.parent / 'output'
RESULTS_DIR = OUT_DIR / 'results'

# 17 LatAm countries (excl. HTI, CUB, VEN)
COUNTRIES_B = [
    'ARG', 'BOL', 'BRA', 'CHL', 'COL', 'CRI', 'DOM', 'ECU',
    'SLV', 'GTM', 'HND', 'MEX', 'NIC', 'PAN', 'PRY', 'PER', 'URY',
]

START_YR = 2016
END_YR = 2024
PIM_INIT_YR = 2008   # 8 years to build up capital stock before analysis period

ALPHA = 0.35
DELTA_K = 0.05       # Physical capital depreciation

CONTROLS_PARS_B = [
    'LNPGDP_constant2015', 'OPEN_trade', 'LN_HC_index',
    'FDI_inflows', 'GOV_consumption', 'URB_urban_pop',
]

# WDI indicator codes → variable names
CONTROL_INDICATORS_B = {
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
    'SP.POP.TOTL':       'POP_total',
}

# ILOSTAT country name → ISO3 (expanded for N=17)
ILOSTAT_NAME_MAP = {
    'Argentina': 'ARG',
    'Bolivia (Plurinational State of)': 'BOL',
    'Brazil': 'BRA', 'Chile': 'CHL', 'Colombia': 'COL',
    'Costa Rica': 'CRI', 'Dominican Republic': 'DOM',
    'Ecuador': 'ECU', 'El Salvador': 'SLV', 'Guatemala': 'GTM',
    'Honduras': 'HND', 'Mexico': 'MEX', 'Nicaragua': 'NIC',
    'Panama': 'PAN', 'Paraguay': 'PRY', 'Peru': 'PER',
    'Uruguay': 'URY',
}

# OECD publications country name → ISO3
OECD_NAME_MAP = {
    'Argentina': 'ARG', 'Bolivia': 'BOL', 'Brazil': 'BRA',
    'Chile': 'CHL', 'Colombia': 'COL', 'Costa Rica': 'CRI',
    'Dominican Republic': 'DOM', 'Ecuador': 'ECU',
    'El Salvador': 'SLV', 'Guatemala': 'GTM', 'Honduras': 'HND',
    'Mexico': 'MEX', 'Nicaragua': 'NIC', 'Panama': 'PAN',
    'Paraguay': 'PRY', 'Peru': 'PER', 'Uruguay': 'URY',
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: EXTRACT DATA FOR N=17
# ══════════════════════════════════════════════════════════════════════════════

def extract_data_panelB():
    """Extract WB + PWT + ILOSTAT data for all 17 LatAm countries."""

    # ── World Bank ──
    wb_path = DATA_DIR / 'wb_data_export.csv'
    wb = pd.read_csv(wb_path)
    print(f"  ✓ World Bank: {wb_path.name}")

    # WB data already uses ISO3 codes in country_code
    wb = wb[(wb['country_code'].isin(COUNTRIES_B)) &
            (wb['year'] >= PIM_INIT_YR) & (wb['year'] <= END_YR)]

    # Core Solow variables (pivot from long to wide)
    solow_inds = {
        'NY.GDP.MKTP.KD': 'GDP',
        'NE.GDI.FTOT.KD': 'INVESTMENT',
        'SL.TLF.TOTL.IN': 'LABOR',
    }
    tfp_raw = wb[wb.indicator_code.isin(solow_inds)].copy()
    tfp_raw['var_name'] = tfp_raw['indicator_code'].map(solow_inds)
    solow = tfp_raw.pivot_table(
        index=['country_code', 'year'], columns='var_name',
        values='value', aggfunc='first',
    ).reset_index()
    solow = solow.rename(columns={'country_code': 'Country', 'year': 'Year'})
    solow.columns.name = None

    # Fill complete frame (all country-year combinations)
    all_years = list(range(PIM_INIT_YR, END_YR + 1))
    full = pd.DataFrame(
        [(c, y) for c in COUNTRIES_B for y in all_years],
        columns=['Country', 'Year'])
    solow = full.merge(solow, on=['Country', 'Year'], how='left')
    solow = solow.sort_values(['Country', 'Year']).reset_index(drop=True)

    # Country names
    name_map = {
        'ARG': 'Argentina', 'BOL': 'Bolivia', 'BRA': 'Brazil', 'CHL': 'Chile',
        'COL': 'Colombia', 'CRI': 'Costa Rica', 'DOM': 'Dominican Republic',
        'ECU': 'Ecuador', 'SLV': 'El Salvador', 'GTM': 'Guatemala',
        'HND': 'Honduras', 'MEX': 'Mexico', 'NIC': 'Nicaragua', 'PAN': 'Panama',
        'PRY': 'Paraguay', 'PER': 'Peru', 'URY': 'Uruguay',
    }
    solow['CountryName'] = solow['Country'].map(name_map)

    # ── PWT Human Capital ──
    pwt_path = DATA_DIR / 'pwt-data-human-capital-026-03-22T15-56_export.csv'
    print(f"  ✓ PWT: {pwt_path.name}")
    pwt = pd.read_csv(pwt_path)
    hci = pwt[pwt['Variable code'] == 'hc'].copy()
    hci = hci[hci['ISO code'].isin(COUNTRIES_B)]

    # Reshape wide → long
    year_cols = [c for c in hci.columns if c.isdigit()]
    hci_long = hci.melt(
        id_vars=['ISO code'], value_vars=year_cols,
        var_name='Year', value_name='HC_index')
    hci_long['Year'] = hci_long['Year'].astype(int)
    hci_long = hci_long.rename(columns={'ISO code': 'Country'})
    hci_long = hci_long[(hci_long.Year >= PIM_INIT_YR) & (hci_long.Year <= END_YR)]
    hci_long['HC_index'] = pd.to_numeric(hci_long['HC_index'], errors='coerce')

    solow = solow.merge(hci_long, on=['Country', 'Year'], how='left')

    print(f"\n  PWT HC coverage for N=17:")
    for c in sorted(COUNTRIES_B):
        nn = solow[(solow.Country == c) & solow.HC_index.notna()].shape[0]
        total = solow[solow.Country == c].shape[0]
        print(f"    {c}: {nn}/{total}")

    # ── ILOSTAT Employment ──
    ilo_path = DATA_DIR / 'EMP_TEMP_SEX_AGE_NB_A-20260325T1614.csv.gz'
    print(f"\n  Loading ILOSTAT employment (N=17)...")
    ilostat = pd.read_csv(ilo_path)
    emp = ilostat[
        (ilostat['sex.label'] == 'Total') &
        (ilostat['classif1.label'] == 'Age (Youth, adults): 15+')
    ].copy()

    emp = emp[emp['ref_area.label'].isin(ILOSTAT_NAME_MAP)]
    emp['Country'] = emp['ref_area.label'].map(ILOSTAT_NAME_MAP)
    emp = emp[['Country', 'time', 'obs_value']].rename(
        columns={'time': 'Year', 'obs_value': 'EMP_thousands'})
    emp['EMP_thousands'] = pd.to_numeric(emp['EMP_thousands'], errors='coerce')
    emp = emp[(emp.Year >= PIM_INIT_YR) & (emp.Year <= END_YR)]
    emp = emp.sort_values(['Country', 'Year']).reset_index(drop=True)
    emp['LABOR_ILOSTAT'] = emp['EMP_thousands'] * 1000.0

    # Full frame + interpolation
    full_frame = pd.DataFrame(
        [(c, y) for c in COUNTRIES_B for y in range(PIM_INIT_YR, END_YR + 1)],
        columns=['Country', 'Year'])
    merged_emp = full_frame.merge(
        emp[['Country', 'Year', 'LABOR_ILOSTAT']],
        on=['Country', 'Year'], how='left')
    merged_emp = merged_emp.sort_values(['Country', 'Year'])
    merged_emp['LABOR_ILOSTAT'] = merged_emp.groupby('Country')['LABOR_ILOSTAT'].transform(
        lambda s: s.interpolate(method='linear', limit_direction='forward', limit=3))

    for c in sorted(COUNTRIES_B):
        sub = merged_emp[(merged_emp.Country == c) & merged_emp.LABOR_ILOSTAT.notna()]
        print(f"    {c}: {len(sub)} obs")

    solow = solow.merge(merged_emp, on=['Country', 'Year'], how='left')
    has_ilo = solow['LABOR_ILOSTAT'].notna()
    solow.loc[has_ilo, 'LABOR'] = solow.loc[has_ilo, 'LABOR_ILOSTAT']
    n_ilo = has_ilo.sum()
    n_wdi = (~has_ilo & solow['LABOR'].notna()).sum()
    print(f"\n  LABOR source: {n_ilo} ILOSTAT, {n_wdi} WDI fallback")

    # ── Capital stock via PIM ──
    print(f"\n  Constructing capital stock (PIM, δ={DELTA_K})...")
    solow['CAPITAL'] = np.nan
    for c in COUNTRIES_B:
        mask = solow['Country'] == c
        sub = solow.loc[mask].sort_values('Year').copy()
        inv = sub['INVESTMENT'].dropna()
        if len(inv) < 3:
            print(f"    {c}: SKIPPED (insufficient investment data)")
            continue
        g_init = inv.head(5).pct_change().dropna().mean()
        g_init = max(g_init, 0.01)
        i0 = inv.iloc[0]
        k0 = i0 / (g_init + DELTA_K)
        cap = [k0]
        for i_val in inv.iloc[1:]:
            cap.append(i_val + (1 - DELTA_K) * cap[-1])
        idx = inv.index
        solow.loc[idx, 'CAPITAL'] = cap
        print(f"    {c}: K₀={k0:.2e}, K_T={cap[-1]:.2e}")

    # ── Effective labor ──
    solow['EFFECTIVE_LABOR'] = solow['LABOR'] * solow['HC_index']

    # ── WDI controls (pivot from long to wide) ──
    ctrl_raw = wb[wb.indicator_code.isin(CONTROL_INDICATORS_B)].copy()
    ctrl_raw['var_name'] = ctrl_raw['indicator_code'].map(CONTROL_INDICATORS_B)
    wdi = ctrl_raw.pivot_table(
        index=['country_code', 'year'], columns='var_name',
        values='value', aggfunc='first',
    ).reset_index()
    wdi = wdi.rename(columns={'country_code': 'Country', 'year': 'Year'})
    wdi.columns.name = None
    # Fill complete frame
    ctrl_full = pd.DataFrame(
        [(c, y) for c in COUNTRIES_B for y in all_years],
        columns=['Country', 'Year'])
    wdi = ctrl_full.merge(wdi, on=['Country', 'Year'], how='left')
    wdi = wdi.sort_values(['Country', 'Year']).reset_index(drop=True)

    # Forward-only interpolation for controls [M2 FIX]
    for col in CONTROL_INDICATORS_B.values():
        if col in wdi.columns:
            wdi[col] = wdi.groupby('Country')[col].transform(
                lambda s: s.interpolate(method='linear', limit_direction='forward', limit=3))

    wdi['LNPGDP_constant2015'] = np.log(
        pd.to_numeric(wdi['GDPPC_constant2015'], errors='coerce'))

    print(f"\n  WDI controls: {wdi.shape}, countries={len(wdi.Country.unique())}")

    return solow, wdi


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: SOLOW TFP
# ══════════════════════════════════════════════════════════════════════════════

def compute_solow_tfp_B(df, alpha=ALPHA):
    """Compute Solow TFP for Panel B (same formula as Panel A)."""
    df = df.copy()
    valid = df[['GDP', 'CAPITAL', 'LABOR', 'HC_index']].notna().all(axis=1)
    eff_labor = df.loc[valid, 'LABOR'] * df.loc[valid, 'HC_index']
    df.loc[valid, 'TFP'] = (
        df.loc[valid, 'GDP'] /
        (df.loc[valid, 'CAPITAL'] ** alpha * eff_labor ** (1 - alpha))
    )
    df['TFP_Growth'] = df.groupby('Country')['TFP'].pct_change() * 100
    df['GDP_Growth'] = df.groupby('Country')['GDP'].pct_change() * 100
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: MALMQUIST DEA (CRS only for N=17 — VRS infeasibility worse with
#          heterogeneous countries spanning from NIC to BRA)
# ══════════════════════════════════════════════════════════════════════════════

def compute_malmquist_B(df):
    """Malmquist CRS for Panel B, 2-input (K, L×HC)."""
    input_cols = ['CAPITAL', 'EFFECTIVE_LABOR']
    output_col = 'GDP'
    req_cols = input_cols + [output_col]
    years = sorted(df['Year'].unique())
    results = []

    print(f"  DEA inputs: CAPITAL, EFFECTIVE_LABOR (2-input, CRS)")
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

        if t_idx % 4 == 0:
            print(f"    {yt}→{yt1} ({len(common)} ctys)", flush=True)

        for ci, cty in enumerate(common):
            d_t_t   = _solve_dea_output(Y_t[ci],  X_t[ci],  Y_t,  X_t,  vrs=False)
            d_t1_t1 = _solve_dea_output(Y_t1[ci], X_t1[ci], Y_t1, X_t1, vrs=False)
            d_t_t1  = _solve_dea_output(Y_t1[ci], X_t1[ci], Y_t,  X_t,  vrs=False)
            d_t1_t  = _solve_dea_output(Y_t[ci],  X_t[ci],  Y_t1, X_t1, vrs=False)

            if any(np.isnan(d) for d in [d_t_t, d_t1_t1, d_t_t1, d_t1_t]):
                results.append({
                    'Country': cty, 'Year_t': yt, 'Year_t1': yt1,
                    'Period': f'{yt}-{yt1}',
                    'TFP_Change': np.nan, 'Efficiency_Change': np.nan,
                    'Technical_Change': np.nan,
                })
                continue

            eff_ch = d_t1_t1 / d_t_t if d_t_t > 0 else np.nan
            if d_t1_t1 > 0 and d_t1_t > 0:
                tech_ch = np.sqrt((d_t_t1 / d_t1_t1) * (d_t_t / d_t1_t))
            else:
                tech_ch = np.nan
            tfp_ch = eff_ch * tech_ch if (np.isfinite(eff_ch) and np.isfinite(tech_ch)) else np.nan

            results.append({
                'Country': cty, 'Year_t': yt, 'Year_t1': yt1,
                'Period': f'{yt}-{yt1}',
                'TFP_Change': tfp_ch, 'Efficiency_Change': eff_ch,
                'Technical_Change': tech_ch,
            })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: OECD PUBLICATIONS
# ══════════════════════════════════════════════════════════════════════════════

def load_oecd_publications():
    """Load OECD.AI publication counts (field='All') for 17 LatAm countries."""
    pub = pd.read_csv(UPLOADS_DIR / 'publications_yearly_articles.csv')
    pub = pub[pub['field'] == 'All'].copy()
    pub = pub[pub['country'].isin(OECD_NAME_MAP)]
    pub['Country'] = pub['country'].map(OECD_NAME_MAP)
    pub = pub[(pub.year >= START_YR) & (pub.year <= END_YR)]
    pub = pub[['Country', 'year', 'num_articles']].rename(
        columns={'year': 'Year', 'num_articles': 'AI_Publications'})
    pub['AI_Publications'] = pd.to_numeric(pub['AI_Publications'], errors='coerce').fillna(0)
    return pub.sort_values(['Country', 'Year']).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: MERGE
# ══════════════════════════════════════════════════════════════════════════════

def build_panelB(publications, solow, malmquist, wdi):
    """Build Panel B merged dataset."""
    df = solow[(solow['Year'] >= START_YR) & (solow['Year'] <= END_YR)].copy()
    df = df[['Country', 'CountryName', 'Year', 'INVESTMENT', 'CAPITAL', 'GDP',
             'HC_index', 'LABOR', 'EFFECTIVE_LABOR', 'TFP', 'TFP_Growth', 'GDP_Growth']]

    # Publications
    df = df.merge(publications, on=['Country', 'Year'], how='left')
    df['AI_Publications'] = df['AI_Publications'].fillna(0)

    # Malmquist
    mq = malmquist[['Country', 'Year_t1', 'TFP_Change',
                     'Efficiency_Change', 'Technical_Change']].rename(
        columns={'Year_t1': 'Year'})
    df = df.merge(mq, on=['Country', 'Year'], how='left')

    # WDI controls
    wdi_period = wdi[(wdi['Year'] >= START_YR) & (wdi['Year'] <= END_YR)].copy()
    wdi_keep = [c for c in wdi_period.columns if c in [
        'Country', 'Year', 'LNPGDP_constant2015', 'GDPPC_constant2015',
        'FIN_credit_private', 'GOV_consumption', 'OPEN_trade',
        'FDI_inflows', 'URB_urban_pop',
        'INF_internet', 'INF_broadband', 'INF_mobile',
        'INST_rule_of_law', 'POP_total',
    ]]
    df = df.merge(wdi_period[wdi_keep], on=['Country', 'Year'], how='left')

    # Derived variables
    df['LN_AI_pub'] = np.log1p(df['AI_Publications'])
    df['LN_HC_index'] = np.log(df['HC_index'].clip(lower=0.01))

    # Lags
    df['LN_AI_pub_L1'] = df.groupby('Country')['LN_AI_pub'].shift(1)

    df = df.sort_values(['Country', 'Year']).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  TFP-AI Pipeline v5 — PANEL B                                    ║")
    print("║  17 Countries, 2016–2024, OECD.AI Publications                   ║")
    print("║  Robustness: AI measure + sample generalizability                 ║")
    print("╚════════════════════════════════════════════════════════════════════╝")

    # ── Step 1: Extract data ──────────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 1: Extract data (N=17, WB + PWT + ILOSTAT)")
    print(f"{'═'*70}")
    solow_df, wdi_df = extract_data_panelB()

    # ── Step 2: Solow TFP ─────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print(f"STEP 2: Solow TFP (α={ALPHA}, labor-augmenting HC)")
    print(f"{'═'*70}")
    solow_df = compute_solow_tfp_B(solow_df)
    # Report for analysis period only
    analysis = solow_df[(solow_df.Year >= START_YR) & (solow_df.Year <= END_YR)]
    tfp_valid = analysis['TFP'].notna().sum()
    total_target = len(COUNTRIES_B) * (END_YR - START_YR + 1)
    print(f"  TFP computed: {tfp_valid}/{total_target} obs ({START_YR}-{END_YR})")
    for c in sorted(COUNTRIES_B):
        sub = analysis[(analysis.Country == c) & analysis.TFP.notna()]
        if len(sub) > 0:
            print(f"    {c}: mean={sub.TFP.mean():.4e} [{len(sub)} obs]")
        else:
            print(f"    {c}: NO VALID TFP")

    # ── Step 3: Malmquist DEA (CRS) ──────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 3: Malmquist DEA TFP Change — CRS (2-input)")
    print(f"{'═'*70}")
    dea_df = solow_df.dropna(subset=['GDP', 'CAPITAL', 'EFFECTIVE_LABOR'])
    print(f"  DEA-ready: {len(dea_df)} obs ({dea_df.Country.nunique()} countries)")
    mq = compute_malmquist_B(dea_df)
    # Filter to analysis period
    if len(mq) == 0:
        print("  WARNING: No Malmquist results. Creating empty DataFrame.")
        mq = pd.DataFrame(columns=['Country', 'Year_t', 'Year_t1', 'Period',
                                    'TFP_Change', 'Efficiency_Change', 'Technical_Change'])
    mq_analysis = mq[(mq.Year_t1 >= START_YR) & (mq.Year_t1 <= END_YR)] if len(mq) > 0 else mq
    mq_valid = mq_analysis['TFP_Change'].notna().sum()
    print(f"\n  Results (analysis period): {mq_valid} valid / {len(mq_analysis)} total")
    for c in sorted(mq_analysis.Country.unique()):
        g = mq_analysis[(mq_analysis.Country == c) & mq_analysis.TFP_Change.notna()]['TFP_Change']
        if len(g) > 0:
            print(f"    {c}: geom_mean={np.exp(np.log(g).mean()):.4f} (n={len(g)})")

    # ── Step 4: OECD Publications ─────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 4: OECD.AI Publications (field='All')")
    print(f"{'═'*70}")
    pubs = load_oecd_publications()
    total_pubs = pubs['AI_Publications'].sum()
    print(f"  Publications: {len(pubs)} rows, Total={int(total_pubs)}")
    for c in sorted(COUNTRIES_B):
        sub = pubs[pubs.Country == c]
        print(f"    {c}: {int(sub.AI_Publications.sum())}")

    # ── Step 5: Merge ─────────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 5: Build Panel B Merged Dataset")
    print(f"{'═'*70}")
    merged = build_panelB(pubs, solow_df, mq, wdi_df)
    print(f"  Panel B: {merged.shape[0]} obs, {merged.Country.nunique()} countries, "
          f"{merged.Year.min()}-{merged.Year.max()}")
    for col in ['TFP', 'TFP_Change', 'AI_Publications', 'LN_AI_pub',
                'LNPGDP_constant2015']:
        if col in merged.columns:
            nn = merged[col].notna().sum()
            print(f"    {col:<25} {nn}/{len(merged)} ({nn/len(merged)*100:.0f}%)")
    merged.to_csv(RESULTS_DIR / 'merged_panelB_v5.csv', index=False)

    # ── Step 6: Benchmark Regressions ─────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 6: Panel B Benchmark Regressions")
    print(f"{'═'*70}")
    df = merged.copy()
    df['ln_TFP'] = np.log(df['TFP'].clip(lower=1e-15))

    ai_var = 'LN_AI_pub'

    dv_list = [('ln_TFP', 'Solow'), ('TFP_Change', 'Malmquist-CRS')]

    for y_col, label in dv_list:
        print(f"\n{'─'*70}")
        print(f"  DV = {label} ({y_col})")
        print(f"{'─'*70}")
        x_cols = [ai_var] + CONTROLS_PARS_B

        # OLS
        try:
            r = pooled_ols(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  OLS:    β(AI_pub)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  OLS: ERROR {e}")

        # Two-way FE (DK SE)
        try:
            r = fixed_effects_twoway(df, y_col, x_cols, se_type='driscoll_kraay')
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  FE-DK:  β(AI_pub)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  FE-DK: ERROR {e}")

        # RE
        try:
            r = random_effects(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  RE:     β(AI_pub)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  RE: ERROR {e}")

        # CCEP
        try:
            r = cce_pooled(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  CCEP:   β(AI_pub)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  CCEP: ERROR {e}")

        # CCEFE
        try:
            r = cce_fe(df, y_col, x_cols)
            ai_coef = r['coef'].get(ai_var, np.nan)
            ai_se = r['se'].get(ai_var, np.nan)
            ai_p = r['p'].get(ai_var, np.nan)
            print(f"  CCEFE:  β(AI_pub)={ai_coef:.4f} (SE={ai_se:.4f}){_stars(ai_p)} "
                  f"N={r['obs']} R²={r['r2']:.3f}")
        except Exception as e:
            print(f"  CCEFE: ERROR {e}")

    # ── Step 7: Pesaran CD test ───────────────────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 7: Pesaran CD Test (Panel B)")
    print(f"{'═'*70}")
    for y_col, label in dv_list:
        cd = pesaran_cd_test(df, y_col, [ai_var] + CONTROLS_PARS_B)
        if cd:
            print(f"  {label}: {cd['conclusion']}")
        else:
            print(f"  {label}: CD test failed")

    # ── Step 8: Panel A vs Panel B comparison ─────────────────────────
    print(f"\n{'═'*70}")
    print("STEP 8: Panel A vs Panel B Comparison")
    print(f"{'═'*70}")
    try:
        panel_a = pd.read_csv(RESULTS_DIR / 'merged_dissertation_v5.csv')
        panel_a['ln_TFP'] = np.log(panel_a['TFP'].clip(lower=1e-15))

        # Overlap countries (9 in both panels)
        overlap_ctys = sorted(set(panel_a.Country.unique()) & set(df.Country.unique()))
        overlap_yrs = sorted(set(panel_a.Year.unique()) & set(df.Year.unique()))
        print(f"  Overlap: {len(overlap_ctys)} countries × {len(overlap_yrs)} years")
        print(f"  Countries: {overlap_ctys}")
        print(f"  Years: {overlap_yrs}")

        # Correlate TFP levels for overlap
        a = panel_a[panel_a.Country.isin(overlap_ctys) &
                     panel_a.Year.isin(overlap_yrs)].set_index(['Country', 'Year'])
        b = df[df.Country.isin(overlap_ctys) &
               df.Year.isin(overlap_yrs)].set_index(['Country', 'Year'])
        common_idx = a.index.intersection(b.index)
        if len(common_idx) > 10:
            corr_tfp = np.corrcoef(
                a.loc[common_idx, 'ln_TFP'].values,
                b.loc[common_idx, 'ln_TFP'].values
            )[0, 1]
            print(f"  ln(TFP) correlation (overlap): r={corr_tfp:.4f}")
    except FileNotFoundError:
        print("  Panel A results not found — run main pipeline first")

    print(f"\n{'═'*70}")
    print("PANEL B PIPELINE COMPLETE")
    print(f"{'═'*70}")
    print(f"\nOutputs saved to: {RESULTS_DIR}/")
    print(f"  • merged_panelB_v5.csv")


if __name__ == '__main__':
    main()
