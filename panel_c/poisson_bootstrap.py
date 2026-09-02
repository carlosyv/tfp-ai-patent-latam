#!/usr/bin/env python3
"""Stage 6: correct treatment of a count regressor, and small-cluster inference.

CORRECTION TO ADDENDUM 1
------------------------
Addendum 1 said to "re-estimate as Poisson FE with words as offset (the correct
estimator, of which ln(1+mentions) is an approximation)." That conflated two
different models. AI mentions are the REGRESSOR in the productivity equation,
not the outcome, so a Poisson model of mentions is not a re-estimation of the
productivity regression at all. Poisson enters this project in two legitimate
but distinct places, and neither is what that sentence claimed:

  Part A -- Poisson FE with a words offset, mention COUNT as the outcome.
            This is a MEASURE-VALIDATION model: it describes AI-disclosure
            propensity net of document length. It also yields a fitted
            log-intensity that is free of the arbitrary "+1" and of the
            length artefact, usable as an alternative regressor.
  Part D -- PPML with the productivity LEVEL as the outcome. This is an
            outcome-side robustness check that avoids logging the dependent
            variable. Unrelated to the count regressor question.

The genuine problem with ln(1+mentions) as a regressor is different again and
is treated in Parts B and C:

  Part B -- Chen & Roth (2024): with 56% zeros, the coefficient on log(1+x) is
            not unit-invariant. Rescaling the count changes the estimate. Any
            log-like transform of a zero-inflated regressor inherits this, and
            a referee at a productivity journal will know it. Part B measures
            how badly it bites here.
  Part C -- Two-part decomposition into an extensive margin (does the firm
            disclose AI at all) and an intensive margin (how much, given
            disclosure). This is the principled specification when a majority
            of observations sit at zero, and it is the one recommended for the
            manuscript. It has no units problem and each margin is separately
            interpretable.

Part E applies the WILD CLUSTER BOOTSTRAP (restricted, Webb six-point weights,
grid-inverted confidence intervals) to every sector split. With 17 financial-
sector clusters, cluster-robust asymptotics are unreliable and the t = 2.07
reported in Addendum 1 cannot be taken at face value.

Outputs
-------
poisson_bootstrap_results.csv   -- all specifications, with bootstrap p and CI

numpy/pandas only, matching regressions.py. Cross-validate against
pyfixest.fepois / ppmlhdfe and boottest before anything is published.
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIN_SIC2 = [60, 61, 62, 63, 64, 65, 67]
B_REPS = 9999          # bootstrap replications for p-values
B_GRID = 1999          # replications per grid point when inverting for CIs
SEED = 20260728


# ------------------------------------------------------------ linear FE core --
def demean_two_way(df, cols, firm="cik", year="fy", iters=200, tol=1e-12):
    X = df[cols].astype(float).copy()
    for _ in range(iters):
        X = X - X.groupby(df[firm]).transform("mean")
        X = X - X.groupby(df[year]).transform("mean")
        if X.groupby(df[firm]).transform("mean").abs().to_numpy().max() < tol:
            break
    return X


def ols_cluster(y, X, cl):
    """OLS with cluster-robust SEs. Returns b, se, u."""
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    k = X.shape[1]
    meat = np.zeros((k, k))
    for g in np.unique(cl):
        m = cl == g
        s = X[m].T @ u[m]
        meat += np.outer(s, s)
    G = len(np.unique(cl))
    n = len(y)
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - k))
    return b, np.sqrt(np.diag(V)), u


# --------------------------------------------------- wild cluster bootstrap --
def _webb(rng, size):
    """Webb (2014) six-point weights -- preferred over Rademacher when G < 30."""
    pts = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5),
                    np.sqrt(0.5), 1.0, np.sqrt(1.5)])
    return pts[rng.integers(0, 6, size=size)]


def wcr_bootstrap(y, X, cl, j=0, b0=0.0, reps=B_REPS, seed=SEED):
    """Wild cluster bootstrap, null imposed on coefficient j at value b0 (WCR).

    Returns (t_obs, p_boot). Model must already be residualised on the fixed
    effects (FWL), which is how boottest handles absorbed effects.
    """
    n, k = X.shape
    b, se, _ = ols_cluster(y, X, cl)
    t_obs = (b[j] - b0) / se[j]

    # restricted fit: impose b_j = b0
    y_r = y - b0 * X[:, j]
    keep = [c for c in range(k) if c != j]
    if keep:
        Xr = X[:, keep]
        br = np.linalg.pinv(Xr.T @ Xr) @ Xr.T @ y_r
        fit_r = Xr @ br
    else:
        fit_r = np.zeros(n)
    u_r = y_r - fit_r

    groups, gidx = np.unique(cl, return_inverse=True)
    G = len(groups)
    rng = np.random.default_rng(seed)
    Wg = _webb(rng, (G, reps))                       # (G, reps)
    Ystar = (fit_r + b0 * X[:, j])[:, None] + u_r[:, None] * Wg[gidx, :]

    XtXi = np.linalg.pinv(X.T @ X)
    Bstar = XtXi @ (X.T @ Ystar)                     # (k, reps)
    Ustar = Ystar - X @ Bstar

    # clustered variance of coefficient j for every replication
    meat = np.zeros((k, k, reps))
    for gi in range(G):
        m = gidx == gi
        S = X[m].T @ Ustar[m]                        # (k, reps)
        meat += S[:, None, :] * S[None, :, :]
    scale = (G / (G - 1)) * ((n - 1) / (n - k))
    Vj = np.einsum("a,abr,b->r", XtXi[j], meat, XtXi[j]) * scale
    se_star = np.sqrt(np.maximum(Vj, 1e-300))
    t_star = (Bstar[j] - b0) / se_star

    p = (np.sum(np.abs(t_star) >= np.abs(t_obs)) + 1) / (reps + 1)
    return t_obs, p


def wcr_ci(y, X, cl, j=0, level=0.05, reps=B_GRID, seed=SEED, n_grid=41):
    """Grid-inverted wild-cluster-bootstrap CI: the set of b0 not rejected."""
    b, se, _ = ols_cluster(y, X, cl)
    grid = np.linspace(b[j] - 5 * se[j], b[j] + 5 * se[j], n_grid)
    keep = [g for g in grid
            if wcr_bootstrap(y, X, cl, j, b0=g, reps=reps, seed=seed)[1] > level]
    if not keep:
        return np.nan, np.nan
    return min(keep), max(keep)


# ------------------------------------------------------------- Poisson FE ----
def poisson_fe(y, X, firm, year, offset=None, iters=200, tol=1e-10):
    """Poisson with two-way multiplicative fixed effects and optional offset.

    E[y|.] = exp(offset + a_i + t_t + X'b). Fixed effects are concentrated out
    by iterative proportional fitting (the ppmlhdfe approach); b is updated by
    Newton-Raphson on the concentrated score.
    """
    n = len(y)
    off = np.zeros(n) if offset is None else np.asarray(offset, float)
    fi = pd.factorize(firm)[0]
    ti = pd.factorize(year)[0]
    b = np.zeros(X.shape[1])
    a = np.zeros(fi.max() + 1)
    t = np.zeros(ti.max() + 1)
    ysum_f = np.bincount(fi, weights=y)
    ysum_t = np.bincount(ti, weights=y)

    for _ in range(iters):
        eta = off + a[fi] + t[ti] + X @ b
        # IPF updates for the fixed effects (closed form given b)
        for _ in range(50):
            mu = np.exp(eta)
            den_f = np.bincount(fi, weights=mu)
            step_f = np.log(np.maximum(ysum_f, 1e-12) / np.maximum(den_f, 1e-12))
            a += step_f
            eta += step_f[fi]
            mu = np.exp(eta)
            den_t = np.bincount(ti, weights=mu)
            step_t = np.log(np.maximum(ysum_t, 1e-12) / np.maximum(den_t, 1e-12))
            t += step_t
            eta += step_t[ti]
            if max(np.abs(step_f).max(), np.abs(step_t).max()) < tol:
                break
        mu = np.exp(eta)
        score = X.T @ (y - mu)
        H = (X * mu[:, None]).T @ X
        step = np.linalg.pinv(H) @ score
        b = b + step
        if np.abs(step).max() < tol:
            break

    eta = off + a[fi] + t[ti] + X @ b
    mu = np.exp(eta)
    Xt = _mu_demean(X, mu, fi, ti)
    return b, mu, a[fi] + t[ti], Xt


def _mu_demean(X, mu, fi, ti, iters=200, tol=1e-12):
    """mu-weighted two-way within transformation.

    The fixed effects are ESTIMATED, not known. Treating them as known (using
    raw X in the sandwich) understates the variance by an order of magnitude --
    that bug produced t = 293 in an earlier run of this script. ppmlhdfe
    partials the FE out of the regressors with weights mu; this reproduces it.
    """
    Xt = np.asarray(X, float).copy()
    for _ in range(iters):
        wf = np.bincount(fi, weights=mu)
        wt = np.bincount(ti, weights=mu)
        step = 0.0
        for j in range(Xt.shape[1]):
            mf = np.bincount(fi, weights=mu * Xt[:, j]) / np.maximum(wf, 1e-300)
            Xt[:, j] -= mf[fi]
            mt = np.bincount(ti, weights=mu * Xt[:, j]) / np.maximum(wt, 1e-300)
            Xt[:, j] -= mt[ti]
            step = max(step, abs(mt).max())
        if step < tol:
            break
    return Xt


def poisson_cluster_se(y, mu, Xt, cl):
    """Cluster-robust sandwich for PPML. Xt must be mu-demeaned on the FE."""
    k = Xt.shape[1]
    Hi = np.linalg.pinv((Xt * mu[:, None]).T @ Xt)
    u = y - mu
    meat = np.zeros((k, k))
    for g in np.unique(cl):
        m = cl == g
        s = Xt[m].T @ u[m]
        meat += np.outer(s, s)
    G = len(np.unique(cl))
    V = Hi @ meat @ Hi * (G / (G - 1))
    return np.sqrt(np.diag(V))


# ------------------------------------------------------------------ data -----
def build():
    d = pd.read_csv(os.path.join(HERE, "firm_panel_clean.csv"))
    d = d.dropna(subset=["lprod", "exp", "filing_words", "ai_total_mentions"]).copy()
    d["mentions"] = d["ai_total_mentions"].astype(float)
    d["lwords"] = np.log(d["filing_words"])
    d["lment"] = np.log1p(d["mentions"])
    d["anyai"] = (d["mentions"] > 0).astype(float)
    # intensive margin: log mentions where positive, zero elsewhere (paired with anyai)
    d["lment_pos"] = np.where(d["mentions"] > 0, np.log(d["mentions"].clip(lower=1)), 0.0)
    d = d.sort_values(["cik", "fy"])
    for v in ("lment", "anyai", "lment_pos"):
        d[v + "_l1"] = d.groupby("cik")[v].shift(1)
    d["financial"] = d["sic2"].isin(FIN_SIC2)
    return d


SAMPLES = [
    ("full",           lambda d: d),
    ("non-financials", lambda d: d[~d.financial]),
    ("financials",     lambda d: d[d.financial]),
]


def run():
    d = build()
    rows = []

    # ---- Part A: measure validation -- Poisson FE, mentions as outcome -------
    dA = d.dropna(subset=["lment"]).copy()
    XA = dA[["lprod"]].to_numpy()
    bA, muA, feA, XtA = poisson_fe(dA["mentions"].to_numpy(), XA,
                                   dA["cik"], dA["fy"], offset=dA["lwords"].to_numpy())
    seA = poisson_cluster_se(dA["mentions"].to_numpy(), muA, XtA, dA["cik"].to_numpy())
    rows.append({"part": "A validation", "spec": "PoissonFE mentions ~ lprod, offset ln(words)",
                 "sample": "full", "coef": bA[0], "se": seA[0], "t": bA[0] / seA[0],
                 "n": len(dA), "clusters": dA.cik.nunique(), "boot_p": np.nan,
                 "ci_lo": np.nan, "ci_hi": np.nan})
    # fitted log-intensity, free of the "+1" and of the length artefact
    dA["ai_hat"] = np.log(np.maximum(muA, 1e-12)) - dA["lwords"] - feA
    d = d.merge(dA[["cik", "fy", "ai_hat"]], on=["cik", "fy"], how="left")
    d = d.sort_values(["cik", "fy"])
    d["ai_hat_l1"] = d.groupby("cik")["ai_hat"].shift(1)

    # ---- Parts B/C/E: productivity regressions with bootstrap inference ------
    specs = [
        ("B log1p, t-1  [addendum 1]",   ["lment_l1", "lwords"]),
        ("C two-part, t-1",              ["anyai_l1", "lment_pos_l1", "lwords"]),
        ("C extensive only, t-1",        ["anyai_l1", "lwords"]),
    ]
    for slab, sel in SAMPLES:
        s0 = sel(d)
        for plab, xcols in specs:
            s = s0.dropna(subset=["lprod"] + xcols).copy()
            if len(s) < 50 or s.cik.nunique() < 8:
                continue
            D = demean_two_way(s, ["lprod"] + xcols)
            y = D["lprod"].to_numpy()
            X = D[xcols].to_numpy()
            cl = s["cik"].to_numpy()
            b, se, _ = ols_cluster(y, X, cl)
            t_obs, p_b = wcr_bootstrap(y, X, cl, j=0)
            lo, hi = wcr_ci(y, X, cl, j=0)
            rows.append({"part": plab.split()[0], "spec": plab, "sample": slab,
                         "regressor": xcols[0], "coef": b[0], "se": se[0], "t": t_obs,
                         "p_asymptotic_normal": 2 * (1 - _ncdf(abs(t_obs))),
                         "boot_p": p_b, "ci_lo": lo, "ci_hi": hi,
                         "n": len(s), "clusters": len(np.unique(cl))})

    # ---- Part B: Chen & Roth units sensitivity ------------------------------
    s = d.dropna(subset=["lprod", "lment_l1", "lwords"]).copy()
    for k in (0.01, 0.1, 1.0, 10.0, 100.0):
        s["_x"] = np.log1p(k * np.exp(s["lment_l1"]) - k + 1e-15) if False else \
                  np.log1p(k * (np.expm1(s["lment_l1"])))
        D = demean_two_way(s, ["lprod", "_x", "lwords"])
        b, se, _ = ols_cluster(D["lprod"].to_numpy(),
                               D[["_x", "lwords"]].to_numpy(), s["cik"].to_numpy())
        rows.append({"part": "B units", "spec": f"log1p(k*mentions), k={k:g}",
                     "sample": "full", "regressor": "_x", "coef": b[0], "se": se[0],
                     "t": b[0] / se[0], "n": len(s), "clusters": s.cik.nunique(),
                     "boot_p": np.nan, "ci_lo": np.nan, "ci_hi": np.nan})

    # ---- Part D: PPML, productivity LEVEL as outcome ------------------------
    for slab, sel in SAMPLES:
        s = sel(d).dropna(subset=["lprod", "lment_l1", "lwords"]).copy()
        if len(s) < 50 or s.cik.nunique() < 8:
            continue
        lev = np.exp(s["lprod"].to_numpy())
        Xd = s[["lment_l1", "lwords"]].to_numpy()
        bD, muD, _, XtD = poisson_fe(lev, Xd, s["cik"], s["fy"])
        seD = poisson_cluster_se(lev, muD, XtD, s["cik"].to_numpy())
        rows.append({"part": "D PPML", "spec": "PPML productivity level, t-1",
                     "sample": slab, "regressor": "lment_l1", "coef": bD[0],
                     "se": seD[0], "t": bD[0] / seD[0], "n": len(s),
                     "clusters": s.cik.nunique(), "boot_p": np.nan,
                     "ci_lo": np.nan, "ci_hi": np.nan})

    out = pd.DataFrame(rows)
    dest = os.path.join(HERE, "poisson_bootstrap_results.csv")
    out.to_csv(dest, index=False)
    pd.set_option("display.width", 220)
    cols = ["part", "spec", "sample", "coef", "se", "t", "boot_p",
            "ci_lo", "ci_hi", "n", "clusters"]
    print(out[cols].to_string(index=False, float_format=lambda v: f"{v: .4f}"))
    print(f"\nwritten -> {dest}")
    return out


def _ncdf(x):
    """Standard normal CDF via erf, without scipy."""
    return 0.5 * (1.0 + np.vectorize(_erf)(x / np.sqrt(2.0)))


def _erf(x):
    """Abramowitz & Stegun 7.1.26."""
    sign = np.sign(x)
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return sign * y


if __name__ == "__main__":
    run()
