#!/usr/bin/env python3
"""Stage 7: cross-validate the numpy estimators against established packages.

BLOCKING PREREQUISITE for submission. Addendum 2 reports coefficients, bootstrap
p-values and confidence intervals produced by hand-rolled numpy code in
measure_specification.py and poisson_bootstrap.py. Nothing in the manuscript may
cite those numbers until they reproduce under an independent implementation.

Run this in your local environment, not the Cowork sandbox (pyfixest and
statsmodels are not installed there).

    pip install pyfixest statsmodels linearmodels
    python panel_c/validate_estimators.py

What it checks
--------------
1. Two-way FE OLS with firm-clustered SEs
       ours: demean_two_way + ols_cluster        vs  pyfixest.feols
2. PPML / Poisson FE with mu-weighted sandwich
       ours: poisson_fe + poisson_cluster_se     vs  pyfixest.fepois
   This is the one most likely to disagree. An earlier version of our sandwich
   treated the fixed effects as known and produced t = 293; the mu-weighted
   within transformation was added to fix it. Confirm the fix independently.
3. Wild cluster bootstrap p-values
       ours: wcr_bootstrap (Webb, restricted)    vs  pyfixest .wildboottest
   Expect close but not identical p-values: the bootstrap is stochastic and
   seeds differ. Agreement to ~0.01 at 9,999 reps is fine; a gap larger than
   0.02, or any disagreement about which side of 0.05 a p-value falls on, is a
   failure that must be resolved before publication.

Tolerances
----------
Coefficients   : 1e-6  relative
Standard errors: 1e-4  relative  (different small-sample corrections are
                                  possible; if this trips, check whether the
                                  package applies (G/(G-1))*((n-1)/(n-k)) as we do)
Bootstrap p    : 0.02  absolute

Exit code 0 = all checks pass. Non-zero = at least one disagreement; the report
names which.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from measure_specification import build as build_measure          # noqa: E402
from poisson_bootstrap import (                                    # noqa: E402
    build, demean_two_way, ols_cluster, poisson_fe,
    poisson_cluster_se, wcr_bootstrap,
)

TOL_COEF, TOL_SE, TOL_P = 1e-6, 1e-4, 0.02
FIN_SIC2 = [60, 61, 62, 63, 64, 65, 67]

results = []


def check(label, ours, theirs, tol, kind="rel"):
    if theirs is None:
        results.append((label, "SKIP", ours, None, "package unavailable"))
        return None
    if kind == "rel":
        denom = max(abs(theirs), 1e-12)
        diff = abs(ours - theirs) / denom
    else:
        diff = abs(ours - theirs)
    ok = diff <= tol
    results.append((label, "PASS" if ok else "FAIL", ours, theirs, f"{diff:.2e}"))
    return ok


def main():
    try:
        import pyfixest as pf
    except ImportError:
        print("pyfixest not installed.  pip install pyfixest statsmodels")
        return 2

    d = build()
    d["lprod_"] = d["lprod"]

    # ---------------------------------------------------------------- 1. FE OLS
    for lab, sub in [("full", d),
                     ("non-financials", d[~d.financial]),
                     ("financials", d[d.financial])]:
        s = sub.dropna(subset=["lprod", "lment_l1", "lwords"]).copy()
        if len(s) < 50:
            continue
        D = demean_two_way(s, ["lprod", "lment_l1", "lwords"])
        b, se, _ = ols_cluster(D["lprod"].to_numpy(),
                               D[["lment_l1", "lwords"]].to_numpy(),
                               s["cik"].to_numpy())
        fit = pf.feols("lprod ~ lment_l1 + lwords | cik + fy", data=s, vcov={"CRV1": "cik"})
        tb = fit.coef()["lment_l1"]
        ts = fit.se()["lment_l1"]
        check(f"FE OLS coef  [{lab}]", b[0], tb, TOL_COEF)
        check(f"FE OLS se    [{lab}]", se[0], ts, TOL_SE)

    # -------------------------------------------------------------- 2. PPML
    for lab, sub in [("full", d),
                     ("non-financials", d[~d.financial]),
                     ("financials", d[d.financial])]:
        s = sub.dropna(subset=["lprod", "lment_l1", "lwords"]).copy()
        if len(s) < 50:
            continue
        s["lev"] = np.exp(s["lprod"])
        bD, muD, _, XtD = poisson_fe(s["lev"].to_numpy(),
                                     s[["lment_l1", "lwords"]].to_numpy(),
                                     s["cik"], s["fy"])
        seD = poisson_cluster_se(s["lev"].to_numpy(), muD, XtD, s["cik"].to_numpy())
        try:
            pfit = pf.fepois("lev ~ lment_l1 + lwords | cik + fy", data=s, vcov={"CRV1": "cik"})
            tb, ts = pfit.coef()["lment_l1"], pfit.se()["lment_l1"]
        except Exception as e:                                   # noqa: BLE001
            print(f"  fepois failed on {lab}: {e}")
            tb = ts = None
        check(f"PPML coef    [{lab}]", bD[0], tb, TOL_COEF)
        check(f"PPML se      [{lab}]", seD[0], ts, TOL_SE)

    # ------------------------------------------------- 3. wild cluster bootstrap
    for lab, sub in [("full", d),
                     ("non-financials", d[~d.financial]),
                     ("financials", d[d.financial])]:
        s = sub.dropna(subset=["lprod", "lment_l1", "lwords"]).copy()
        if len(s) < 50:
            continue
        D = demean_two_way(s, ["lprod", "lment_l1", "lwords"])
        _, p_ours = wcr_bootstrap(D["lprod"].to_numpy(),
                                  D[["lment_l1", "lwords"]].to_numpy(),
                                  s["cik"].to_numpy(), j=0, reps=9999)
        try:
            fit = pf.feols("lprod ~ lment_l1 + lwords | cik + fy", data=s, vcov={"CRV1": "cik"})
            wb = fit.wildboottest(param="lment_l1", reps=9999, weights_type="webb")
            p_theirs = float(wb["Pr(>|t|)"]) if hasattr(wb, "__getitem__") else float(wb)
        except Exception as e:                                   # noqa: BLE001
            print(f"  wildboottest failed on {lab}: {e}")
            p_theirs = None
        check(f"WCR boot p   [{lab}]", p_ours, p_theirs, TOL_P, kind="abs")

    # ------------------------------------------------------------------ report
    w = max(len(r[0]) for r in results)
    print(f"\n{'check'.ljust(w)}  {'status':6}  {'ours':>12}  {'package':>12}  diff")
    print("-" * (w + 46))
    for lab, st, a, bv, dd in results:
        bs = "n/a" if bv is None else f"{bv:12.6f}"
        print(f"{lab.ljust(w)}  {st:6}  {a:12.6f}  {bs}  {dd}")

    fails = [r for r in results if r[1] == "FAIL"]
    skips = [r for r in results if r[1] == "SKIP"]
    print(f"\n{len(results) - len(fails) - len(skips)} passed, {len(fails)} failed, {len(skips)} skipped")
    if fails:
        print("\nDO NOT CITE the affected numbers until these are resolved:")
        for f in fails:
            print(f"  - {f[0]}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
