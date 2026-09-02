#!/usr/bin/env python3
"""Stage 5: AI-exposure measure specification diagnostic.

Motivation
----------
The stage-4 first pass regressed log productivity on ln(1 + AI mentions per 10k
words). That regressor is dominated by zeros (56.3% of firm-years) and, after
two-way demeaning, retains a within firm-and-year standard deviation of only
0.091 against outcome noise of 0.464. The resulting 95% confidence interval on
the FH1 baseline is roughly [-0.58, +0.57], which excludes no economically
meaningful effect. The stage-4 null is therefore imprecise, not informative.

This script asks whether that is a property of the data or of the transform.
It compares candidate transforms of the same underlying AI-mention counts on
the same estimation sample, reporting the within-variation each retains and the
precision it implies, then re-estimates FH1 under the preferred specifications.

Preferred specification, chosen on measurement grounds before inspecting any
coefficient: AI mentions are a count, and normalising by document length inside
a log transform discards information and manufactures zeros. The count-data
convention is ln(1 + mentions) with ln(document length) entering as a separate
control (equivalently, a Poisson FE model with words as offset -- see NOTE).

NOTE / CAVEAT
-------------
The transform comparison below is a specification search conducted after the
original specification was found to be underpowered. The measurement rationale
is independent of the coefficients, but the coefficients were inspected
afterwards. Treat every result here as EXPLORATORY. In particular the
financial-sector estimate rests on 19 clusters, where cluster-robust inference
is unreliable; it requires a wild cluster bootstrap before it is reported
anywhere. A Poisson FE / PPML estimator with a words offset is the
econometrically correct version of the preferred spec and should supersede the
ln(1+mentions) approximation in the manuscript.

Outputs
-------
measure_specification_results.csv  -- one row per (specification, sample)

Two-way FE by iterated demeaning; firm-clustered SEs. numpy/pandas only, to
match regressions.py. Cross-validate against linearmodels PanelOLS before any
table is built from this.
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIN_SIC2 = [60, 61, 62, 63, 64, 65, 67]  # Division H: Finance, Insurance, Real Estate


# ---------------------------------------------------------------- estimation --
def demean_two_way(df, cols, firm="cik", year="fy", iters=120):
    """Iterated within transformation on firm and year."""
    X = df[cols].astype(float).copy()
    for _ in range(iters):
        X = X - X.groupby(df[firm]).transform("mean")
        X = X - X.groupby(df[year]).transform("mean")
        if X.groupby(df[firm]).transform("mean").abs().to_numpy().max() < 1e-12:
            break
    return X


def fe_cluster(df, ycol, xcols, firm="cik"):
    """Two-way FE with firm-clustered SEs. Returns dict for the first regressor."""
    s = df.dropna(subset=[ycol] + xcols).copy()
    if len(s) < 50:
        return None
    D = demean_two_way(s, [ycol] + xcols)
    y = D[ycol].to_numpy()
    X = D[xcols].to_numpy()
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    cl = s[firm].to_numpy()
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(cl):
        m = cl == g
        sg = X[m].T @ u[m]
        meat += np.outer(sg, sg)
    G = len(np.unique(cl))
    n, k = X.shape
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))
    se = np.sqrt(np.diag(V))
    return {
        "coef": b[0], "se": se[0], "t": b[0] / se[0],
        "ci_lo": b[0] - 1.96 * se[0], "ci_hi": b[0] + 1.96 * se[0],
        "mde_80": 2.802 * se[0], "n": n, "firms": G, "clusters": G,
        "sd_within_x": D[xcols[0]].std(), "sd_within_y": D[ycol].std(),
    }


# ------------------------------------------------------------------- pipeline --
def build(path=None):
    d = pd.read_csv(path or os.path.join(HERE, "firm_panel_clean.csv"))
    d = d.dropna(subset=["lprod", "exp", "filing_words"]).copy()
    d["lwords"] = np.log(d["filing_words"])
    d["lexp"] = np.log1p(d["exp"])                    # stage-4 specification
    d["lexp_tot"] = np.log1p(d["exp_tot"])
    d["lment"] = np.log1p(d["ai_total_mentions"])     # preferred: count + offset
    d["anyai"] = (d["exp"] > 0).astype(float)         # extensive margin
    d["rank_yr"] = d.groupby("fy")["exp"].rank(pct=True)
    d = d.sort_values(["cik", "fy"])
    for v in ("lexp", "lment", "anyai"):
        d[v + "_l1"] = d.groupby("cik")[v].shift(1)
    d["financial"] = d["sic2"].isin(FIN_SIC2)
    return d


SPECS = [
    # label,                                regressors (first = AI measure)
    ("ln(1+exp per 10k) [stage-4]",         ["lexp"]),
    ("ln(1+exp_tot per 10k)",               ["lexp_tot"]),
    ("1[any AI mention]",                   ["anyai"]),
    ("within-year percentile rank",         ["rank_yr"]),
    ("ln(1+mentions) + ln(words)",          ["lment", "lwords"]),
]
SPECS_LAG = [
    ("ln(1+exp per 10k) [stage-4], t-1",    ["lexp_l1"]),
    ("1[any AI mention], t-1",              ["anyai_l1"]),
    ("ln(1+mentions) + ln(words), t-1",     ["lment_l1", "lwords"]),
]


def run():
    d = build()
    rows = []

    def add(label, xcols, sample, sample_lab):
        r = fe_cluster(sample, "lprod", xcols)
        if r:
            rows.append({"spec": label, "sample": sample_lab, "regressor": xcols[0], **r})

    for lab, xs in SPECS:
        add(lab, xs, d, "full")
    for lab, xs in SPECS_LAG:
        add(lab, xs, d, "full")
    # sector split under the preferred lagged specification (EXPLORATORY -- see NOTE)
    add("ln(1+mentions) + ln(words), t-1", ["lment_l1", "lwords"],
        d[~d.financial], "non-financials")
    add("ln(1+mentions) + ln(words), t-1", ["lment_l1", "lwords"],
        d[d.financial], "financials")

    out = pd.DataFrame(rows)
    dest = os.path.join(HERE, "measure_specification_results.csv")
    out.to_csv(dest, index=False)

    pd.set_option("display.width", 200)
    show = out[["spec", "sample", "sd_within_x", "coef", "se", "t",
                "ci_lo", "ci_hi", "n", "clusters"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v: .4f}"))
    print(f"\nwritten -> {dest}")
    print("Corr(ln mentions, ln filing words) = "
          f"{d[['lment', 'lwords']].corr().iloc[0, 1]:.3f}")
    print("\nEXPLORATORY. Financial-sector row has 19 clusters -- wild cluster "
          "bootstrap required before reporting. Replace ln(1+mentions) with "
          "Poisson FE (words offset) for the manuscript.")
    return out


if __name__ == "__main__":
    run()
