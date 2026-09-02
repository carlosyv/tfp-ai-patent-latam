"""
EAP (Paper 1) — stage 1 of 2: compute every statistic the manuscript reports.

    pipeline v5 outputs  ──▶  compute_eap_results.py  ──▶  eap_results_v5.json
                                                                   │
                                             build_eap_tables.py ◀─┘

WHY THIS FILE EXISTS
--------------------
`run_pipeline_v5.py` estimates every specification the manuscript reports, but
`run_mediation()`, `run_heterogeneity()` and `run_quantile_canay()` return None —
they print to stdout and nothing else.  Only the benchmark regressions are
persisted (`output/results/benchmark_dissertation_v5/`).  Tables 4, 5, 6 and 7
therefore had no machine-readable source, and were keyed in by hand.  That is
how Table 6 panel B came to contain values that were never estimated.

This script closes the gap: it re-runs those specifications using the pipeline's
own estimators, imported unchanged, and writes everything to a single JSON with
provenance.  The estimators are imported rather than reimplemented, so the
numbers reproduce the pipeline exactly.

DESIGN RULES
------------
1. Every statistic lands in `eap_results_v5.json` keyed by a stable dotted path.
2. Nothing is computed here that the pipeline does not compute.  This file
   assembles and serialises; it does not define new estimators.
3. The JSON records the SHA-256 of every input file and the git commit, so a
   table can always be traced back to the data that produced it.
4. If an input is missing the script fails.  It never substitutes a default.

USAGE
    python3 eap_tables/compute_eap_results.py
    python3 eap_tables/compute_eap_results.py --dk-dof-correction   # see NOTE

NOTE ON DRISCOLL-KRAAY STANDARD ERRORS
--------------------------------------
`run_pipeline_v5.py:801` passes raw residuals to `_driscoll_kraay_se`, with no
finite-sample correction for the absorbed fixed effects.  `gtfp_pipeline`'s
`fe_dk` scales residuals by sqrt(n/dof) first.  For Panel A that is a factor of
sqrt(225/185) = 1.1028, so v5's DK standard errors are ~10% smaller than the
corrected ones (Solow baseline: 0.0118 vs 0.0130 on the same beta of -0.0157).

The corrected version is the defensible one — Hoechle's `xtscc` applies a
small-sample adjustment, and without it DK errors are downward-biased in short
panels.  The default here is the *uncorrected* convention, because that is what
the dissertation and the submitted manuscript report and the first job of this
script is to reproduce them.  Pass --dk-dof-correction to switch.  Both runs are
tagged in the JSON under `meta.dk_dof_correction`, so a table always states
which convention produced it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PIPELINE = REPO / "pipeline_v5"
RESULTS = REPO / "output" / "results"
BENCH = RESULTS / "benchmark_dissertation_v5"

sys.path.insert(0, str(PIPELINE))

# Estimators imported unchanged from the paper's own pipeline.  Do not
# reimplement any of these here — that is what this file exists to prevent.
from run_pipeline_v5 import (  # noqa: E402
    pooled_ols,
    fixed_effects_twoway,
    cce_pooled,
    cce_fe,
    pesaran_cd_test,
    compute_descriptives,
    _driscoll_kraay_se,
    _ols_coef,
    _t_and_p,
)

# ── Specification constants (mirror run_pipeline_v5.py) ──────────────────────

AI_VAR = "LN_AI"
AI_VAR_B = "LN_AI_pub"

CONTROLS_PARS = [
    "LNPGDP_constant2015",
    "OPEN_trade",
    "LN_HC_index",
    "FDI_inflows",
    "GOV_consumption",
    "URB_urban_pop",
]

MODERATORS = [
    ("INST_rule_of_law", "AI_x_RL", "rule_of_law"),
    ("INF_mobile", "AI_x_MOBILE", "mobile"),
    ("INF_broadband", "AI_x_BROADBAND", "broadband"),
]

DVS_A = [("ln_TFP", "solow"), ("TFP_Change_CRS", "malmquist_crs")]

QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]


class MissingInput(RuntimeError):
    """Raised when a required pipeline output is absent. Never swallowed."""


# ── Provenance ───────────────────────────────────────────────────────────────


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return None


def require(path: Path) -> Path:
    if not path.exists():
        raise MissingInput(
            f"required pipeline output not found: {path}\n"
            f"  run the pipeline first:  python3 pipeline_v5/run_pipeline_v5.py"
        )
    return path


# ── Serialisation helper ─────────────────────────────────────────────────────


def coef(r: dict, var: str, extra: dict | None = None) -> dict:
    """Extract one coefficient from a pipeline estimator result dict."""
    out = {
        "b": float(r["coef"][var]),
        "se": float(r["se"][var]),
        "t": float(r["t"][var]),
        "p": float(r["p"][var]),
        "N": int(r["obs"]),
    }
    if "r2" in r and r["r2"] is not None:
        out["r2"] = float(r["r2"])
    if extra:
        out.update(extra)
    return out


# ── Optional DK dof correction ───────────────────────────────────────────────


def _fe_dk_dof_corrected(df, y_col, x_cols, ent="Country", tcol="Year"):
    """
    Two-way FE with Driscoll-Kraay SEs, applying the finite-sample correction
    the v5 pipeline omits.  Demeaning and kernel are v5's; only the residual
    scaling differs, so beta is bit-identical to fixed_effects_twoway().
    """
    sub = df[[y_col] + x_cols + [ent, tcol]].dropna().copy().reset_index(drop=True)
    for c in [y_col] + x_cols:
        sub[c + "_dm"] = sub[c] - sub.groupby(ent)[c].transform("mean")
    for c in [y_col] + x_cols:
        sub[c + "_dm"] = sub[c + "_dm"] - sub.groupby(tcol)[c + "_dm"].transform("mean")

    y = sub[y_col + "_dm"].values
    X = np.column_stack([sub[c + "_dm"].values for c in x_cols])
    beta = _ols_coef(X, y)
    resid = y - X @ beta
    n, k = X.shape
    Ne, Nt = sub[ent].nunique(), sub[tcol].nunique()
    dof = n - Ne - Nt - k + 1
    se = _driscoll_kraay_se(X, resid * np.sqrt(n / max(dof, 1)), sub[tcol].values)
    t, p = _t_and_p(beta, se, dof)
    r2 = 1 - resid.var() / y.var() if y.var() > 0 else np.nan
    return dict(
        estimator="FE-DK-dofadj",
        y=y_col,
        obs=n,
        se_type="driscoll_kraay_dofadj",
        coef=dict(zip(x_cols, beta)),
        se=dict(zip(x_cols, se)),
        t=dict(zip(x_cols, t)),
        p=dict(zip(x_cols, p)),
        r2=float(r2),
    )


# ── Table blocks ─────────────────────────────────────────────────────────────


# Table 1 rows, as (display label, column in merged_dissertation_v5.csv).
# The pipeline's compute_descriptives() covers a different, shorter variable
# list (and reports Solow TFP in levels), so it cannot produce the manuscript's
# Table 1.  The mapping is therefore explicit here rather than implied.
TABLE1_VARS = [
    ("ln(TFP) — Solow", "ln_TFP"),
    ("Malmquist TFP Change (VRS)", "TFP_Change"),
    ("Malmquist TFP Change (CRS)", "TFP_Change_CRS"),
    ("ln(AI patent stock per capita)", "LN_AI"),
    ("AI Patents (raw count)", "AI_Patents"),
    ("ln(GDP per capita)", "LNPGDP_constant2015"),
    ("Trade openness (% GDP)", "OPEN_trade"),
    ("ln(HC index)", "LN_HC_index"),
    ("FDI inflows (% GDP)", "FDI_inflows"),
    ("Government consumption (% GDP)", "GOV_consumption"),
    ("Urban population (%)", "URB_urban_pop"),
    ("Financial dev. (credit % GDP)", "FIN_credit_private"),
    ("Internet users (%)", "INF_internet"),
    ("Broadband subs. (per 100)", "INF_broadband"),
    ("Mobile subs. (per 100)", "INF_mobile"),
    ("Rule of Law", "INST_rule_of_law"),
    ("IS ratio (services/industry VA)", "IS_ratio"),
]


def block_descriptives(df) -> dict:
    """
    Table 1.  Computed directly from the merged panel over the explicit variable
    list above.  `compute_descriptives()` from the pipeline is also called, and
    kept alongside for cross-reference, but it is not what the table renders.
    """
    rows = []
    for label, col in TABLE1_VARS:
        if col not in df.columns:
            raise MissingInput(
                f"Table 1 variable '{col}' not in merged_dissertation_v5.csv"
            )
        s = df[col].dropna()
        rows.append({
            "label": label,
            "column": col,
            "N": int(s.size),
            "mean": float(s.mean()),
            "sd": float(s.std(ddof=1)),
            "min": float(s.min()),
            "max": float(s.max()),
        })
    return {
        "rows": rows,
        "_pipeline_compute_descriptives": json.loads(
            compute_descriptives(df).to_json(orient="records")
        ),
        "_source": "merged_dissertation_v5.csv, columns per TABLE1_VARS",
    }


def block_cd_tests(df) -> dict:
    """Table 2. Pesaran (2004) CD on parsimonious two-way FE residuals."""
    out = {}
    for dv, key in [
        ("ln_TFP", "solow"),
        ("TFP_Change", "malmquist_vrs"),
        ("TFP_Change_CRS", "malmquist_crs"),
    ]:
        r = pesaran_cd_test(df, dv, [AI_VAR] + CONTROLS_PARS)
        if r is None:
            raise MissingInput(f"pesaran_cd_test returned None for {dv}")
        out[key] = {k: (float(v) if isinstance(v, (int, float)) else v)
                    for k, v in r.items()}
    return out


def block_benchmark(df, fe_dk) -> dict:
    """
    Table 3. FE-DK and CCEP for the three TFP measures, plus the pooled-OLS
    figure quoted in the table note.
    """
    out = {}
    for dv, key in [
        ("ln_TFP", "solow"),
        ("TFP_Change", "malmquist_vrs"),
        ("TFP_Change_CRS", "malmquist_crs"),
    ]:
        x = [AI_VAR] + CONTROLS_PARS
        out[key] = {
            "ols": coef(pooled_ols(df, dv, x), AI_VAR),
            "fe_dk": coef(fe_dk(df, dv, x), AI_VAR),
            "ccep": coef(cce_pooled(df, dv, x), AI_VAR),
            "ccefe": coef(cce_fe(df, dv, x), AI_VAR),
        }
    return out


def block_heterogeneity(df, fe_dk) -> dict:
    """
    Table 4 + Appendix D.  Mirrors run_heterogeneity() call-for-call: interaction
    models on the full sample, then median splits on each moderator.

    Note the interaction models estimate their own main effect on lnAI, which is
    conditional on MOD = 0 and therefore differs from the baseline coefficient.
    Both are stored; the table must not print the baseline in the main-effect row.
    """
    out = {}
    for dv, dv_key in DVS_A:
        out[dv_key] = {}
        for mod_var, interact_var, mod_key in MODERATORS:
            x = [AI_VAR, mod_var, interact_var] + CONTROLS_PARS
            r = fe_dk(df, dv, x)
            entry = {
                "interaction": {
                    "ai_main_effect": coef(r, AI_VAR),
                    "moderator": coef(r, mod_var),
                    "interaction": coef(r, interact_var),
                }
            }
            med = df[mod_var].median()
            x_base = [AI_VAR] + CONTROLS_PARS
            r_lo = fe_dk(df[df[mod_var] <= med], dv, x_base)
            r_hi = fe_dk(df[df[mod_var] > med], dv, x_base)
            lo, hi = coef(r_lo, AI_VAR), coef(r_hi, AI_VAR)
            se_diff = sqrt(hi["se"] ** 2 + lo["se"] ** 2)
            z = (hi["b"] - lo["b"]) / se_diff if se_diff > 0 else float("nan")
            entry["subsample"] = {
                "median": float(med),
                "below": lo,
                "above": hi,
                "difference": {
                    "delta": hi["b"] - lo["b"],
                    "se": se_diff,
                    "z": z,
                    "p": 2 * (1 - _norm_cdf(abs(z))),
                },
            }
            out[dv_key][mod_key] = entry
    return out


def _norm_cdf(x: float) -> float:
    from math import erf

    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def block_quantile(df) -> dict:
    """
    Table 5.  Canay (2011) two-step panel quantile regression.

    Mirrors run_pipeline_v5.run_quantile_canay() step for step: one-way entity FE
    to recover mu_hat_i, y* = y - mu_hat, an additional time-demeaning of y* and
    X, then a Koenker-Bassett LP at each tau, with a paired observation-level
    bootstrap (B = 200, RandomState(42)) for the standard errors.

    Do not "improve" this.  A block bootstrap clustered by country would be
    defensible on its merits, but changing it here would silently move every
    standard error the dissertation reports.  Change the pipeline first, rerun
    both, and document the move.
    """
    from scipy.optimize import linprog
    from scipy.stats import t as t_dist

    y_col = "ln_TFP"
    x_cols = [AI_VAR] + CONTROLS_PARS
    sub = df[[y_col] + x_cols + ["Country", "Year"]].dropna().copy()

    # Step 1 — one-way (entity) FE; mu_hat_i = ybar_i - xbar_i' beta_fe
    cm_y = sub.groupby("Country")[y_col].mean()
    cm_x = sub.groupby("Country")[x_cols].mean()
    y_dm = sub[y_col] - sub["Country"].map(cm_y)
    X_dm = sub[x_cols].copy()
    for c in x_cols:
        X_dm[c] = X_dm[c] - sub["Country"].map(cm_x[c])
    beta_fe = np.linalg.lstsq(X_dm.values, y_dm.values, rcond=None)[0]
    fe_hat = {c: cm_y[c] - cm_x.loc[c].values @ beta_fe
              for c in sub["Country"].unique()}

    # Step 2 — y* = y - mu_hat, then absorb year effects by time-demeaning
    sub["y_star"] = sub[y_col] - sub["Country"].map(fe_hat)
    tm_y = sub.groupby("Year")["y_star"].mean()
    tm_x = sub.groupby("Year")[x_cols].mean()
    sub["y_star_2w"] = sub["y_star"] - sub["Year"].map(tm_y)
    X_qr = sub[x_cols].copy()
    for c in x_cols:
        X_qr[c] = X_qr[c] - sub["Year"].map(tm_x[c])

    X_mat = np.column_stack([np.ones(len(sub)), X_qr.values])
    y_vec = sub["y_star_2w"].values
    n, k = X_mat.shape
    AI_IDX = 1  # column 0 is the constant

    def qr(Xm, yv, tau):
        c_lp = np.concatenate(
            [np.zeros(k), np.zeros(k), tau * np.ones(n), (1 - tau) * np.ones(n)]
        )
        A_eq = np.hstack([Xm, -Xm, np.eye(n), -np.eye(n)])
        res = linprog(c_lp, A_eq=A_eq, b_eq=yv,
                      bounds=[(0, None)] * (2 * k + 2 * n),
                      method="highs", options={"maxiter": 10000})
        if not res.success:
            raise RuntimeError(f"quantile LP failed at tau={tau}: {res.message}")
        return res.x[:k] - res.x[k: 2 * k]

    out = {}
    for tau in QUANTILES:
        beta_qr = qr(X_mat, y_vec, tau)
        rng = np.random.RandomState(42)   # reseeded per tau, as in the pipeline
        boot = np.zeros((200, k))
        for i in range(200):
            idx = rng.choice(n, n, replace=True)
            try:
                boot[i] = qr(X_mat[idx], y_vec[idx], tau)
            except RuntimeError:
                boot[i] = beta_qr         # pipeline's fallback on non-convergence
        se = boot.std(axis=0)             # ddof = 0, as in the pipeline
        b_ai, se_ai = float(beta_qr[AI_IDX]), float(se[AI_IDX])
        t_ai = b_ai / se_ai if se_ai > 0 else 0.0
        # key must not contain '.' — Results.get() addresses by dotted path
        out[f"tau_{int(round(tau * 100)):03d}"] = {
            "b": b_ai,
            "se": se_ai,
            "t": float(t_ai),
            "p": float(2 * (1 - t_dist.cdf(abs(t_ai), df=n - k))),
            "N": int(n),
            "bootstrap_reps": 200,
        }
    return out


def block_mediation(df, fe_dk) -> dict:
    """
    Table 6 panel A.  Baron-Kenny with a Sobel test, for the two channels in
    Luo, Lei and Hou (2024): industrial structure (IS) and human capital (HC).

      Step 1  TFP = b1*AI + X
      Step 2  M   = a1*AI + X
      Step 3  TFP = d1*AI + d2*M + X
      Sobel   z = a1*d2 / sqrt(a1^2*se_d2^2 + d2^2*se_a1^2)
      % mediated = (a1*d2) / b1 * 100

    Mirrors run_pipeline_v5.run_mediation().  Two details matter and are easy to
    get wrong:

    1. The mediation control set has FIVE controls — it drops LN_HC_index, which
       is itself a mediator.  So Step 1 here is NOT the Table 3 baseline: it
       gives b1 = -0.0123, not -0.0157.  The dissertation reports it as the
       "Step 1 beta_1 (ref.)" row.
    2. The estimation sample is fixed per mediator by dropping missing values
       across all of y, AI, M and the controls, and the same sample is used for
       all three steps.
    3. % mediated is the indirect effect over b1, not (b1 - d1)/b1.  The
       dissertation's table note describes the latter; the code computes the
       former, and the code is what produced the published figures.
    """
    controls_med = [
        "LNPGDP_constant2015",
        "OPEN_trade",
        "FDI_inflows",
        "GOV_consumption",
        "URB_urban_pop",
    ]
    out = {"_controls": controls_med}
    for med_var, key in [("LN_IS", "industrial_structure"),
                         ("LN_HC_index", "human_capital")]:
        med_df = df.dropna(subset=["ln_TFP", AI_VAR, med_var] + controls_med)
        if len(med_df) < 30:
            raise MissingInput(
                f"mediation sample for {med_var} has only {len(med_df)} obs"
            )
        s1 = fe_dk(med_df, "ln_TFP", [AI_VAR] + controls_med)
        s2 = fe_dk(med_df, med_var, [AI_VAR] + controls_med)
        s3 = fe_dk(med_df, "ln_TFP", [AI_VAR, med_var] + controls_med)

        b1 = s1["coef"][AI_VAR]
        a1, se_a1 = s2["coef"][AI_VAR], s2["se"][AI_VAR]
        d2, se_d2 = s3["coef"][med_var], s3["se"][med_var]
        indirect = a1 * d2
        sobel_se = sqrt(a1 ** 2 * se_d2 ** 2 + d2 ** 2 * se_a1 ** 2)
        zval = indirect / sobel_se if sobel_se > 0 else float("nan")

        out[key] = {
            "step1_total": coef(s1, AI_VAR),
            "step2": coef(s2, AI_VAR),
            "step3_ai": coef(s3, AI_VAR),
            "step3_mediator": coef(s3, med_var),
            "indirect_effect": float(indirect),
            "sobel": {"z": float(zval),
                      "p": float(2 * (1 - _norm_cdf(abs(zval))))},
            "pct_mediated": float(indirect / b1 * 100) if abs(b1) > 1e-10
            else float("nan"),
        }
    return out


def block_robustness() -> dict:
    """
    Table 6 panel B.  Read straight from the verification script's output — this
    is the panel that was fabricated, so it is deliberately NOT recomputed here.
    Run `pipeline_v5/robustness_verification.py` to regenerate it.
    """
    path = require(RESULTS / "robustness_verification_v5.json")
    raw = json.loads(path.read_text())

    # Keys are re-slugged because Results.get() addresses by dotted path, and
    # the verification script's own key "delta_p=0.22" contains a literal dot.
    slug = {
        "Baseline": "baseline",
        "Raw count": "raw_count",
        "delta_p=0.22": "delta_p_022",
        "Per-GDP": "per_gdp",
        "Lag 1": "lag1",
        "Lag 2": "lag2",
        "2SLS lagged AI": "iv_2sls_lag1",
    }
    missing = set(slug) - set(raw)
    if missing:
        raise MissingInput(
            f"{path.name} is missing specification(s): {sorted(missing)}. "
            f"Rerun pipeline_v5/robustness_verification.py."
        )
    return {
        "specifications": {slug[k]: v for k, v in raw.items() if k in slug},
        "_key_map": slug,
        "_source": str(path.relative_to(REPO)),
        "_sha256": sha256(path),
    }


def block_panel_b(df_b, fe_dk) -> dict:
    """Table 7.  OECD publications panel, N = 17, 2016-2024."""
    out = {}
    for dv, key in [("ln_TFP", "solow"), ("TFP_Change", "malmquist_crs")]:
        x = [AI_VAR_B] + CONTROLS_PARS
        out[key] = {
            "ols": coef(pooled_ols(df_b, dv, x), AI_VAR_B),
            "fe_dk": coef(fe_dk(df_b, dv, x), AI_VAR_B),
            "ccep": coef(cce_pooled(df_b, dv, x), AI_VAR_B),
        }
        r = pesaran_cd_test(df_b, dv, x)
        out[key]["cd_test"] = {k: (float(v) if isinstance(v, (int, float)) else v)
                               for k, v in r.items()} if r else None
    return out


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dk-dof-correction",
        action="store_true",
        help="apply the sqrt(n/dof) finite-sample correction to DK residuals",
    )
    ap.add_argument("--out", default=str(RESULTS / "eap_results_v5.json"))
    args = ap.parse_args()

    merged_a = require(RESULTS / "merged_dissertation_v5.csv")
    merged_b = require(RESULTS / "merged_panelB_v5.csv")

    df = pd.read_csv(merged_a)
    df["ln_TFP"] = np.log(df["TFP"].clip(lower=1e-15))  # as run_pipeline_v5.py:1609
    df_b = pd.read_csv(merged_b)
    df_b["ln_TFP"] = np.log(df_b["TFP"].clip(lower=1e-15))

    fe_dk = (
        _fe_dk_dof_corrected
        if args.dk_dof_correction
        else (lambda d, y, x: fixed_effects_twoway(d, y, x, se_type="driscoll_kraay"))
    )

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "generator": "eap_tables/compute_eap_results.py",
            "git_commit": git_commit(),
            "dk_dof_correction": bool(args.dk_dof_correction),
            "alpha": 0.35,
            "delta_k": 0.05,
            "delta_p": 0.36,
            "inputs": {
                str(p.relative_to(REPO)): sha256(p) for p in (merged_a, merged_b)
            },
        },
        "table1_descriptives": block_descriptives(df),
        "table2_cd_tests": block_cd_tests(df),
        "table3_benchmark": block_benchmark(df, fe_dk),
        "table4_heterogeneity": block_heterogeneity(df, fe_dk),
        "table5_quantile": block_quantile(df),
        "table6a_mediation": block_mediation(df, fe_dk),
        "table6b_robustness": block_robustness(),
        "table7_panel_b": block_panel_b(df_b, fe_dk),
    }

    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2, default=float))
    print(f"wrote {out}")
    print(f"  dk_dof_correction = {args.dk_dof_correction}")
    print(f"  git_commit        = {payload['meta']['git_commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
