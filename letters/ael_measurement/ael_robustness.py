"""
AEL letter — robustness checks for the headline within-country agreement result.

For each variant we recompute the FE-relevant statistic: the two-way (country +
year) demeaned correlation between ln AI patent stock and ln AI publications, plus
the between-country correlation for reference. Variants:
  R1 baseline (delta=0.36, per-capita implicit via stock, 2016-2024)
  R2 alternative patent-stock depreciation delta=0.22
  R3 per-GDP normalisation of the patent stock (stock / real GDP)
  R4 drop Brazil (dominant patent filer)
  R5 pre-period 2016-2020 vs post-period 2021-2024 (two-way within)
  R6 Spearman (rank) two-way within correlation
Outputs: output/ael_robustness.json
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def _norm_sf(x):
    """Upper-tail standard-normal probability via erf (no scipy)."""
    return 0.5 * math.erfc(x / math.sqrt(2))


def pearsonr(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    r = float(np.corrcoef(a, b)[0, 1])
    n = len(a)
    # Fisher z-transform p-value (two-sided)
    if abs(r) >= 1 or n < 4:
        return round(r, 3), 0.0
    z = math.atanh(r) * math.sqrt(n - 3)
    p = 2 * _norm_sf(abs(z))
    return round(r, 3), round(p, 4)


def spearmanr(a, b):
    ra = pd.Series(a).rank().values
    rb = pd.Series(b).rank().values
    return pearsonr(ra, rb)

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data"
OUTD = HERE / "output"
OUTD.mkdir(exist_ok=True)

COUNTRIES = ['ARG', 'BRA', 'CHL', 'COL', 'CRI', 'DOM', 'MEX', 'PER', 'URY']
ISO2TO3 = {'AR': 'ARG', 'CL': 'CHL', 'CO': 'COL', 'CR': 'CRI', 'MX': 'MEX',
           'PE': 'PER', 'DO': 'DOM', 'EC': 'ECU', 'UY': 'URY', 'HN': 'HND',
           'NI': 'NIC', 'PA': 'PAN', 'SV': 'SLV', 'CU': 'CUB', 'GT': 'GTM'}
NAME2ISO = {'Argentina': 'ARG', 'Brazil': 'BRA', 'Chile': 'CHL', 'Colombia': 'COL',
            'Costa Rica': 'CRI', 'Dominican Republic': 'DOM', 'Mexico': 'MEX',
            'Peru': 'PER', 'Uruguay': 'URY'}
LAST_COMPLETE = 2024


def parse_wipo(path):
    raw = pd.read_excel(path, header=None)
    hr = 0
    for i, row in raw.iterrows():
        if str(row.iloc[0]).strip().lower() == 'year':
            hr = i
            break
    df = raw.iloc[hr:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: 'year'})
    long = df.melt(id_vars=['year'], var_name='cc', value_name='pat')
    long['year'] = pd.to_numeric(long['year'], errors='coerce')
    long['pat'] = pd.to_numeric(long['pat'], errors='coerce').fillna(0)
    return long.dropna(subset=['year']).astype({'year': int})


def patent_flows():
    sp = parse_wipo(DATA / 'wipo' / 'ai-search-wipo-results-spanish-v2.xlsx')
    sp['country'] = sp['cc'].astype(str).str.upper().map(ISO2TO3)
    pt = parse_wipo(DATA / 'wipo' / 'ai-search-wipo-results-br-portuguese-v2.xlsx')
    pt['country'] = 'BRA'
    return (pd.concat([sp, pt]).query("country in @COUNTRIES")
              .groupby(['country', 'year'], as_index=False)['pat'].sum())


def build_stock(flows, delta):
    rows = []
    for c, g in flows.sort_values('year').groupby('country'):
        s = 0.0
        for _, r in g.iterrows():
            s = r['pat'] + (1 - delta) * s
            rows.append({'country': c, 'year': int(r['year']), 'pat_stock': s})
    return pd.DataFrame(rows)


def load_pubs():
    pub = pd.read_csv(DATA / 'cat-ai-patents-country-data/publications_yearly_articles.csv')
    pub = pub[pub['field'] == 'All'].copy()
    pub['country'] = pub['country'].map(NAME2ISO)
    return pub.dropna(subset=['country'])[['country', 'year', 'num_articles']]


def load_gdp():
    wb = pd.read_csv(DATA / 'wb' / 'wb_data_export.csv')
    gdp = wb[(wb.indicator_code == 'NY.GDP.MKTP.KD') & wb.country_code.isin(COUNTRIES)]
    return gdp.rename(columns={'country_code': 'country', 'value': 'GDP'})[['country', 'year', 'GDP']]


def two_way_within_corr(m, xcol, ycol, method='pearson'):
    d = m.copy()
    for v in [xcol, ycol]:
        d[f'w_{v}'] = d[v] - d.groupby('country')[v].transform('mean')
        d[f'w2_{v}'] = d[f'w_{v}'] - d.groupby('year')[f'w_{v}'].transform('mean')
    a, b = d[f'w2_{xcol}'], d[f'w2_{ycol}']
    if method == 'spearman':
        r, p = spearmanr(a, b)
    else:
        r, p = pearsonr(a, b)
    return round(float(r), 3), round(float(p), 4), len(d)


def between_corr(m, xcol, ycol):
    cs = m.groupby('country')[[xcol, ycol]].mean()
    r, p = pearsonr(cs[xcol], cs[ycol])
    return round(float(r), 3), round(float(p), 4)


def assemble(stock, pub, gdp=None):
    m = stock.merge(pub, on=['country', 'year']).query("year <= @LAST_COMPLETE").copy()
    if gdp is not None:
        m = m.merge(gdp, on=['country', 'year'], how='left')
    m['ln_stock'] = np.log(m.pat_stock + 1)
    m['ln_pub'] = np.log(m.num_articles + 1)
    if gdp is not None:
        m['ln_stock_pergdp'] = np.log(m.pat_stock / (m.GDP / 1e9) + 1)
    return m


def main():
    flows = patent_flows()
    pub = load_pubs()
    gdp = load_gdp()
    out = {}

    # R1 baseline
    m = assemble(build_stock(flows, 0.36), pub)
    r, p, n = two_way_within_corr(m, 'ln_stock', 'ln_pub')
    br, bp = between_corr(m, 'ln_stock', 'ln_pub')
    out['R1_baseline'] = {'within2way_r': r, 'within2way_p': p, 'between_r': br, 'N': n}

    # R2 delta = 0.22
    m2 = assemble(build_stock(flows, 0.22), pub)
    r, p, n = two_way_within_corr(m2, 'ln_stock', 'ln_pub')
    br, bp = between_corr(m2, 'ln_stock', 'ln_pub')
    out['R2_delta_022'] = {'within2way_r': r, 'within2way_p': p, 'between_r': br, 'N': n}

    # R3 per-GDP normalisation
    m3 = assemble(build_stock(flows, 0.36), pub, gdp=gdp).dropna(subset=['ln_stock_pergdp'])
    r, p, n = two_way_within_corr(m3, 'ln_stock_pergdp', 'ln_pub')
    br, bp = between_corr(m3, 'ln_stock_pergdp', 'ln_pub')
    out['R3_per_gdp'] = {'within2way_r': r, 'within2way_p': p, 'between_r': br, 'N': n}

    # R4 drop Brazil
    m4 = m[m.country != 'BRA']
    r, p, n = two_way_within_corr(m4, 'ln_stock', 'ln_pub')
    br, bp = between_corr(m4, 'ln_stock', 'ln_pub')
    out['R4_drop_BRA'] = {'within2way_r': r, 'within2way_p': p, 'between_r': br, 'N': n}

    # R5 sub-periods
    for lab, lo, hi in [('R5a_2016_2020', 2016, 2020), ('R5b_2021_2024', 2021, 2024)]:
        sub = m[(m.year >= lo) & (m.year <= hi)]
        r, p, n = two_way_within_corr(sub, 'ln_stock', 'ln_pub')
        out[lab] = {'within2way_r': r, 'within2way_p': p, 'N': n}

    # R6 Spearman two-way within
    r, p, n = two_way_within_corr(m, 'ln_stock', 'ln_pub', method='spearman')
    out['R6_spearman_within'] = {'within2way_rho': r, 'within2way_p': p, 'N': n}

    with open(OUTD / 'ael_robustness.json', 'w') as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
