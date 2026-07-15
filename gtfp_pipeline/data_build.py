"""
GTFP pipeline — data build module.

Builds the 40-country × 2016-2023 panel:
  - WDI long → wide with coalesce for GFCF (CHN fallback) and RULE_OF_LAW (two pulls)
  - PIM capital stock from 2008 (K0 = I0/(g+delta))
  - ILOSTAT employment (2026-07 pull; coded or labelled columns handled)
  - PWT 10.01 human capital (trend-extended to END_YR where missing)
  - OECD.AI publications (field='All'), per-million normalisation
Output: output/merged_panel.csv + a build log dict.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (ALPHA, COUNTRIES, DATA_NOTES, DELTA_K, END_YR, ILOSTAT_EMP,
                    OECD_FIELD, OECD_PUBS, OUT_DIR, PIM_INIT_YR, PWT_CSV,
                    REGIONS, START_YR, WB_CSV, WDI_INDICATORS)

# OECD.AI country-name → ISO3 for the 40-country sample
OECD_NAME2ISO = {
    'Argentina': 'ARG', 'Bolivia': 'BOL', 'Brazil': 'BRA', 'Chile': 'CHL',
    'Colombia': 'COL', 'Costa Rica': 'CRI', 'Dominican Republic': 'DOM',
    'Ecuador': 'ECU', 'El Salvador': 'SLV', 'Guatemala': 'GTM',
    'Honduras': 'HND', 'Mexico': 'MEX', 'Nicaragua': 'NIC', 'Panama': 'PAN',
    'Paraguay': 'PRY', 'Peru': 'PER', 'Uruguay': 'URY',
    'China (mainland)': 'CHN', 'India': 'IND', 'Indonesia': 'IDN',
    'Malaysia': 'MYS', 'Thailand': 'THA', 'Philippines': 'PHL',
    'Vietnam': 'VNM', 'Viet Nam': 'VNM', 'Pakistan': 'PAK',
    'Bangladesh': 'BGD', 'Sri Lanka': 'LKA', 'Kazakhstan': 'KAZ',
    'South Africa': 'ZAF', 'Egypt': 'EGY', 'Kenya': 'KEN', 'Morocco': 'MAR',
    'Tunisia': 'TUN', 'Ghana': 'GHA', 'Senegal': 'SEN', 'Ethiopia': 'ETH',
    'Tanzania': 'TZA', 'United Republic of Tanzania': 'TZA', 'Uganda': 'UGA',
    'Algeria': 'DZA', "Cote d'Ivoire": 'CIV', "Côte d'Ivoire": 'CIV',
}

REGION_OF = {c: r for r, lst in REGIONS.items() for c in lst}


def load_wdi():
    """WDI long → wide panel with coalesce logic for tuple-valued indicators."""
    print("  Loading WDI …")
    raw = pd.read_csv(WB_CSV)
    raw = raw[raw.country_code.isin(COUNTRIES)
              & (raw.year >= PIM_INIT_YR) & (raw.year <= END_YR)]
    wide = raw.pivot_table(index=['country_code', 'year'], columns='indicator_code',
                           values='value', aggfunc='first')

    out = pd.DataFrame(index=wide.index)
    for var, code in WDI_INDICATORS.items():
        if isinstance(code, tuple):
            s = pd.Series(np.nan, index=wide.index)
            for c in code:
                if c in wide.columns:
                    s = s.fillna(wide[c])
            out[var] = s
        else:
            out[var] = wide[code] if code in wide.columns else np.nan
    out = out.reset_index().rename(columns={'country_code': 'Country', 'year': 'Year'})
    print(f"    WDI: {out.Country.nunique()} countries × years "
          f"{out.Year.min()}–{out.Year.max()}, {len(out)} rows")
    return out


def build_capital(wdi):
    """PIM capital stock. K0 = I0/(g+delta); K_t = I_t + (1-delta) K_{t-1}."""
    print("  Building PIM capital stock …")
    recs = []
    for c, g in wdi.sort_values('Year').groupby('Country'):
        g = g.dropna(subset=['GFCF'])
        if g.empty:
            print(f"    WARNING {c}: no investment data at all")
            continue
        inv = g.set_index('Year')['GFCF']
        first_years = inv.iloc[:6]
        growth = (first_years.pct_change().dropna().mean()
                  if len(first_years) > 2 else 0.03)
        growth = max(growth, 0.005)          # floor to avoid degenerate K0
        k = inv.iloc[0] / (growth + DELTA_K)
        prev_year = None
        for y, i_t in inv.items():
            if prev_year is not None and y > prev_year + 1:
                # gap: decay capital without investment for skipped years
                for _ in range(y - prev_year - 1):
                    k = (1 - DELTA_K) * k
            k = i_t + (1 - DELTA_K) * k
            recs.append({'Country': c, 'Year': y, 'CAPITAL': k})
            prev_year = y
    cap = pd.DataFrame(recs)
    print(f"    capital: {cap.Country.nunique()} countries, {len(cap)} rows")
    return cap


def load_ilostat():
    """ILOSTAT total employment 15+, coded or labelled column variants."""
    print("  Loading ILOSTAT employment …")
    ilo = pd.read_csv(ILOSTAT_EMP)
    if 'sex.label' in ilo.columns:                      # labelled export
        emp = ilo[(ilo['sex.label'] == 'Total')
                  & (ilo['classif1.label'] == 'Age (Youth, adults): 15+')].copy()
        area_col = 'ref_area.label'
        # labels are country names → need name map; but coded exports preferred
        raise SystemExit("Labelled ILOSTAT export not supported for the 40-country "
                         "sample — use the coded (ref_area=ISO3) bulk file.")
    else:                                               # coded export
        emp = ilo[(ilo['sex'] == 'SEX_T')
                  & (ilo['classif1'].astype(str).str.contains('YGE15'))].copy()
        area_col = 'ref_area'
    val_col = 'obs_value' if 'obs_value' in emp.columns else 'value'
    emp = emp[emp[area_col].isin(COUNTRIES)]
    emp = emp.rename(columns={area_col: 'Country', 'time': 'Year',
                              val_col: 'EMP_thousands'})
    emp['Year'] = pd.to_numeric(emp['Year'], errors='coerce').astype('Int64')
    emp['EMP_thousands'] = pd.to_numeric(emp['EMP_thousands'], errors='coerce')
    emp = emp[(emp.Year >= PIM_INIT_YR) & (emp.Year <= END_YR)]
    emp = (emp.groupby(['Country', 'Year'], as_index=False)['EMP_thousands'].first())
    emp['LABOR'] = emp['EMP_thousands'] * 1000.0

    frame = pd.DataFrame([(c, y) for c in COUNTRIES
                          for y in range(PIM_INIT_YR, END_YR + 1)],
                         columns=['Country', 'Year'])
    m = frame.merge(emp[['Country', 'Year', 'LABOR']], on=['Country', 'Year'],
                    how='left').sort_values(['Country', 'Year'])
    m['LABOR'] = m.groupby('Country')['LABOR'].transform(
        lambda s: s.interpolate(limit_direction='both'))
    gaps = m[m.LABOR.isna()].Country.unique().tolist()
    print(f"    ILOSTAT: {m.LABOR.notna().sum()}/{len(m)} obs"
          + (f"; still missing: {gaps}" if gaps else ""))
    return m


def load_pwt_hc():
    """PWT 10.01 human capital, trend-extended to END_YR where missing."""
    print("  Loading PWT human capital …")
    raw = pd.read_csv(PWT_CSV)
    raw = raw[raw['ISO code'].isin(COUNTRIES)]
    recs = []
    year_cols = [c for c in raw.columns if c.isdigit()]
    for _, row in raw.iterrows():
        for yc in year_cols:
            y = int(yc)
            if PIM_INIT_YR <= y <= END_YR:
                v = row[yc]
                recs.append({'Country': row['ISO code'], 'Year': y,
                             'HC_index': float(v) if pd.notna(v) else np.nan})
    df = pd.DataFrame(recs).sort_values(['Country', 'Year'])
    # extend forward using last observed 1-year growth rate
    out = []
    for c, g in df.groupby('Country'):
        g = g.set_index('Year')['HC_index']
        obs = g.dropna()
        if len(obs) >= 2:
            growth = obs.iloc[-1] / obs.iloc[-2]
            last_y, last_v = obs.index[-1], obs.iloc[-1]
            for y in range(last_y + 1, END_YR + 1):
                last_v = last_v * growth
                g.loc[y] = last_v
        for y, v in g.items():
            out.append({'Country': c, 'Year': int(y), 'HC_index': v})
    hc = pd.DataFrame(out)
    print(f"    PWT HC: {hc.HC_index.notna().sum()}/{len(hc)} obs, "
          f"{hc.Country.nunique()} countries")
    return hc


def load_oecd_pubs():
    """OECD.AI publications (field='All') for the 40 countries."""
    print("  Loading OECD.AI publications …")
    pub = pd.read_csv(OECD_PUBS)
    pub = pub[pub['field'] == OECD_FIELD].copy()
    pub['Country'] = pub['country'].map(OECD_NAME2ISO)
    pub = pub.dropna(subset=['Country'])
    pub = pub[pub.Country.isin(COUNTRIES)]
    pub = (pub.groupby(['Country', 'year'], as_index=False)['num_articles'].sum()
              .rename(columns={'year': 'Year', 'num_articles': 'AI_PUBS'}))
    missing = sorted(set(COUNTRIES) - set(pub.Country.unique()))
    assert not missing, f"OECD publications missing for: {missing}"
    print(f"    OECD.AI: {pub.Country.nunique()}/40 countries, "
          f"years {pub.Year.min()}–{pub.Year.max()}")
    return pub


def build_panel(save=True):
    """Assemble the merged panel; return (panel_2016_2023, full_frame_2008on)."""
    print("═" * 66)
    print("GTFP DATA BUILD (N=40, 2016–2023; PIM from 2008)")
    print("═" * 66)
    wdi = load_wdi()
    cap = build_capital(wdi)
    ilo = load_ilostat()
    hc = load_pwt_hc()
    pub = load_oecd_pubs()

    df = (wdi.merge(cap, on=['Country', 'Year'], how='left')
             .merge(ilo, on=['Country', 'Year'], how='left')
             .merge(hc, on=['Country', 'Year'], how='left')
             .merge(pub, on=['Country', 'Year'], how='left'))

    df['EFFECTIVE_LABOR'] = df['LABOR'] * df['HC_index']
    df['REGION'] = df['Country'].map(REGION_OF)

    # Solow residual (level TFP): lnA = lnY − α lnK − (1−α) ln(h·L)
    ok = df[['GDP', 'CAPITAL', 'EFFECTIVE_LABOR']].notna().all(axis=1) & \
         (df[['GDP', 'CAPITAL', 'EFFECTIVE_LABOR']] > 0).all(axis=1)
    df.loc[ok, 'LN_TFP_SOLOW'] = (np.log(df.loc[ok, 'GDP'])
                                  - ALPHA * np.log(df.loc[ok, 'CAPITAL'])
                                  - (1 - ALPHA) * np.log(df.loc[ok, 'EFFECTIVE_LABOR']))

    # AI regressor: ln(1 + publications per million population)
    df['AI_PUBS_PM'] = df['AI_PUBS'] / (df['POP'] / 1e6)
    df['LN_AI'] = np.log1p(df['AI_PUBS_PM'])

    panel = df[(df.Year >= START_YR) & (df.Year <= END_YR)].copy()

    print("\n  Estimation-window completeness (2016–2023):")
    key = ['GDP', 'CAPITAL', 'EFFECTIVE_LABOR', 'CO2', 'LN_AI', 'RULE_OF_LAW']
    for v in key:
        nn = panel[v].notna().sum()
        print(f"    {v:16s}: {nn}/{len(panel)}")
    thin = [c for c, g in panel.groupby('Country')
            if g[['GDP', 'CAPITAL', 'EFFECTIVE_LABOR', 'CO2']].notna().all(axis=1).sum() < 6]
    if thin:
        print(f"    countries with <6 complete DEA years: {thin}")

    if save:
        OUT_DIR.mkdir(exist_ok=True)
        panel.to_csv(OUT_DIR / 'merged_panel.csv', index=False)
        df.to_csv(OUT_DIR / 'merged_full_2008on.csv', index=False)
        print(f"\n  saved → {OUT_DIR/'merged_panel.csv'}")
    for k, v in DATA_NOTES.items():
        print(f"  NOTE [{k}]: {v}")
    return panel, df


if __name__ == '__main__':
    build_panel()
