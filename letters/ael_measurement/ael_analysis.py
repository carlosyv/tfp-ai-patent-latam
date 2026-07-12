"""
AEL letter analysis — Do patents and publications measure the same AI innovation?

Computes all statistics reported in the Applied Economics Letters draft:
  - Between-country correlation of ln AI patent stock vs ln AI publications
  - Pooled within-country (country-demeaned) correlation
  - Two-way demeaned (country + year) correlation  <- the FE-relevant statistic
  - Growth-rate (first-difference) correlation
  - Per-country time-series correlations
  - Between/within variance decomposition of each measure
  - Year-by-year cross-sectional Spearman rank correlations
Outputs: ael_results.json + ael_figure1.png (two-panel scatter).

Data inputs (all in ../../data/, shared with pipeline_v5):
  - ai-search-wipo-results-spanish-v2.xlsx      (WIPO keyword search, ES)
  - ai-search-wipo-results-br-portuguese-v2.xlsx (WIPO keyword search, PT/BRA)
  - cat-ai-patents-country-data/publications_yearly_articles.csv (OECD.AI)

Run:  python3 ael_analysis.py     (from this folder; no arguments)
Deps: pandas, numpy, scipy, matplotlib, openpyxl
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

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
DELTA = 0.36          # patent-stock depreciation (Yan, Chen & Zhang 2020) — matches pipeline_v5
LAST_COMPLETE = 2024  # 2025+ flagged incomplete in the OECD source


def parse_wipo(path):
    """Parse the WIPO pivot-table export (same logic as pipeline_v5)."""
    raw = pd.read_excel(path, header=None)
    header_row = 0
    for i, row in raw.iterrows():
        if str(row.iloc[0]).strip().lower() == 'year':
            header_row = i
            break
    df = raw.iloc[header_row:].reset_index(drop=True)
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    df = df.rename(columns={df.columns[0]: 'year'})
    long = df.melt(id_vars=['year'], var_name='cc', value_name='pat')
    long['year'] = pd.to_numeric(long['year'], errors='coerce')
    long['pat'] = pd.to_numeric(long['pat'], errors='coerce').fillna(0)
    return long.dropna(subset=['year']).astype({'year': int})


def main():
    # --- patents -> stock (PIM, delta=0.36) ---
    sp = parse_wipo(DATA / 'ai-search-wipo-results-spanish-v2.xlsx')
    sp['country'] = sp['cc'].astype(str).str.upper().map(ISO2TO3)
    pt = parse_wipo(DATA / 'ai-search-wipo-results-br-portuguese-v2.xlsx')
    pt['country'] = 'BRA'
    pat = (pd.concat([sp, pt])
             .query("country in @COUNTRIES")
             .groupby(['country', 'year'], as_index=False)['pat'].sum())

    stocks = []
    for c, g in pat.sort_values('year').groupby('country'):
        s = 0.0
        for _, r in g.iterrows():
            s = r['pat'] + (1 - DELTA) * s
            stocks.append({'country': c, 'year': int(r['year']), 'pat_stock': s})
    stk = pd.DataFrame(stocks)

    # --- publications (field='All') ---
    pub_raw = pd.read_csv(DATA / 'cat-ai-patents-country-data/publications_yearly_articles.csv')
    pub = pub_raw[pub_raw['field'] == 'All'].copy()
    pub['country'] = pub['country'].map(NAME2ISO)
    pub = pub.dropna(subset=['country'])[['country', 'year', 'num_articles']]

    # --- merge, transform ---
    m = (stk.merge(pub, on=['country', 'year'], how='inner')
            .query("year <= @LAST_COMPLETE"))
    m['ln_stock'] = np.log(m.pat_stock + 1)
    m['ln_pub'] = np.log(m.num_articles + 1)
    for v in ['ln_stock', 'ln_pub']:
        m[f'w_{v}'] = m[v] - m.groupby('country')[v].transform('mean')
        m[f'w2_{v}'] = m[f'w_{v}'] - m.groupby('year')[f'w_{v}'].transform('mean')

    res = {"window": [int(m.year.min()), int(m.year.max())],
           "n_countries": int(m.country.nunique()), "n_obs": len(m)}

    # 1) between-country (country means)
    cs = m.groupby('country')[['ln_stock', 'ln_pub']].mean()
    r_cs, p_cs = stats.pearsonr(cs.ln_stock, cs.ln_pub)
    rho, p_rho = stats.spearmanr(cs.ln_stock, cs.ln_pub)
    res["cross_section"] = {"pearson_r": round(r_cs, 3), "p": round(p_cs, 4),
                            "spearman_rho": round(rho, 3), "p_rho": round(p_rho, 4)}

    # 2) within-country pooled and two-way demeaned
    r_w, p_w = stats.pearsonr(m.w_ln_stock, m.w_ln_pub)
    r_w2, p_w2 = stats.pearsonr(m.w2_ln_stock, m.w2_ln_pub)
    res["within_pooled"] = {"pearson_r": round(r_w, 3), "p": round(p_w, 4)}
    res["within_twoway"] = {"pearson_r": round(r_w2, 3), "p": round(p_w2, 4)}

    # 3) per-country
    pc = {}
    for c, g in m.groupby('country'):
        if len(g) >= 5:
            r, p = stats.pearsonr(g.ln_stock, g.ln_pub)
            pc[c] = {"r": round(r, 3), "p": round(p, 4), "T": len(g)}
    res["per_country"] = pc
    res["per_country_summary"] = {
        "n": len(pc),
        "sig_pos_5pct": sum(1 for v in pc.values() if v["r"] > 0 and v["p"] < 0.05),
        "sig_neg_5pct": sum(1 for v in pc.values() if v["r"] < 0 and v["p"] < 0.05),
        "median_r": round(float(np.median([v["r"] for v in pc.values()])), 3)}

    # 4) growth rates
    m = m.sort_values(['country', 'year'])
    m['d_ln_stock'] = m.groupby('country')['ln_stock'].diff()
    m['d_ln_pub'] = m.groupby('country')['ln_pub'].diff()
    dd = m.dropna(subset=['d_ln_stock', 'd_ln_pub'])
    r_d, p_d = stats.pearsonr(dd.d_ln_stock, dd.d_ln_pub)
    res["growth_rates"] = {"pearson_r": round(r_d, 3), "p": round(p_d, 4), "n": len(dd)}

    # 5) variance decomposition
    def decomp(v):
        grand = m[v].mean()
        between = (m.groupby('country')[v].mean().sub(grand).pow(2)
                     .mul(m.groupby('country').size()).sum())
        within = (m[v] - m.groupby('country')[v].transform('mean')).pow(2).sum()
        return round(between / (between + within), 3)
    res["between_share"] = {"ln_stock": decomp('ln_stock'), "ln_pub": decomp('ln_pub')}

    # 6) year-by-year rank correlation
    res["rank_corr_by_year"] = {
        int(y): round(stats.spearmanr(g.ln_stock, g.ln_pub)[0], 3)
        for y, g in m.groupby('year') if g.country.nunique() >= 8}

    with open(OUTD / "ael_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))

    # --- figure ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    ax = axes[0]
    ax.scatter(cs.ln_stock, cs.ln_pub, s=45, color="#1F4E78")
    for c, row in cs.iterrows():
        ax.annotate(c, (row.ln_stock, row.ln_pub), fontsize=8,
                    xytext=(4, 3), textcoords="offset points")
    b, a = np.polyfit(cs.ln_stock, cs.ln_pub, 1)
    xs = np.linspace(cs.ln_stock.min(), cs.ln_stock.max(), 10)
    ax.plot(xs, a + b * xs, color="#C0504D", lw=1.4)
    ax.set_xlabel("ln AI patent stock (country mean, 2016–2024)")
    ax.set_ylabel("ln AI publications (country mean)")
    ax.set_title(f"(a) Between countries: r = {r_cs:.2f}", fontsize=11)

    ax = axes[1]
    ax.scatter(m.w2_ln_stock, m.w2_ln_pub, s=18, alpha=0.55, color="#1F4E78")
    b2, a2 = np.polyfit(m.w2_ln_stock, m.w2_ln_pub, 1)
    xs2 = np.linspace(m.w2_ln_stock.min(), m.w2_ln_stock.max(), 10)
    ax.plot(xs2, a2 + b2 * xs2, color="#C0504D", lw=1.4)
    ax.axhline(0, color="gray", lw=0.5)
    ax.axvline(0, color="gray", lw=0.5)
    ax.set_xlabel("ln AI patent stock (two-way demeaned)")
    ax.set_ylabel("ln AI publications (two-way demeaned)")
    ax.set_title(f"(b) Within countries, net of year effects: "
                 f"r = {r_w2:.2f} (p = {p_w2:.2f})", fontsize=11)
    plt.tight_layout()
    plt.savefig(OUTD / "ael_figure1.png", dpi=300, bbox_inches="tight")
    print(f"\nSaved: {OUTD/'ael_results.json'} and {OUTD/'ael_figure1.png'}")


if __name__ == "__main__":
    main()
