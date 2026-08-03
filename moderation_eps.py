"""
H4 — environmental-policy-stringency moderation of the AI–GTFP association.

Estimates  y_it = b1*lnAI_{i,t-1} + b2*(lnAI_{i,t-1} x EPS~_it) + b3*EPS_it
                  + X_it'g + a_i + t_t (+ region x year) + e_it

with Driscoll-Kraay standard errors, matching the existing moderation design in
Section 4.5 (demeaned moderator, moderator main effect included, median-split
corroboration).

NOTHING here writes prose. Run it, then write Section 4.5 from the output.

Requires: pandas, numpy, linearmodels, statsmodels
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

DV_LIST = ["gtfp_ml", "malmquist", "solow"]
AI_VAR = "ln_ai_pc_l1"                     # one-year-lagged ln AI per million
CONTROLS = [
    "ln_gdp_pc",
    "trade_openness",
    "fdi",
    "gov_consumption",
    "urbanisation",
]
# Two stringency moderators: headline EPI and its climate-and-energy component.
# Keep the existing absorptive-capacity moderators in the same table for contrast.
MODERATORS = {
    "epi": "EPI headline score",
    "epi_climate": "EPI climate & energy component",
    "rule_of_law": "Rule of Law (WGI)",
    "mobile": "Mobile subscriptions per 100",
}
DK_LAGS = 2                                # Bartlett bandwidth; see note below


# --------------------------------------------------------------------------
# Estimation
# --------------------------------------------------------------------------

def demean_within(df: pd.DataFrame, col: str) -> pd.Series:
    """Demean a moderator by country, so the AI main effect is read at the
    country-specific mean of the moderator rather than at zero."""
    return df[col] - df.groupby(level=0)[col].transform("mean")


def estimate_moderation(
    df: pd.DataFrame,
    dv: str,
    moderator: str,
    region_by_year: bool = False,
) -> dict:
    """One moderation regression. Returns a dict of the numbers needed for the
    results table; does not format or interpret them."""
    d = df.copy()
    d["_mod_c"] = demean_within(d, moderator)
    d["_inter"] = d[AI_VAR] * d["_mod_c"]

    rhs = [AI_VAR, "_inter", "_mod_c"] + CONTROLS
    d = d[[dv] + rhs].dropna()

    if region_by_year:
        # region x year absorbed via explicit dummies (region must be a column)
        raise NotImplementedError(
            "Add region-by-year dummies here if you report the RxY variant; "
            "the baseline in Section 4.5 is country + year FE."
        )

    mod = PanelOLS(
        d[dv],
        d[rhs],
        entity_effects=True,
        time_effects=True,
        drop_absorbed=True,
    )
    res = mod.fit(cov_type="kernel", kernel="bartlett", bandwidth=DK_LAGS)

    ci = res.conf_int()
    return {
        "dv": dv,
        "moderator": moderator,
        "n": int(res.nobs),
        "beta_ai": float(res.params[AI_VAR]),
        "se_ai": float(res.std_errors[AI_VAR]),
        "p_ai": float(res.pvalues[AI_VAR]),
        "beta_inter": float(res.params["_inter"]),
        "se_inter": float(res.std_errors["_inter"]),
        "p_inter": float(res.pvalues["_inter"]),
        "ci_inter_lo": float(ci.loc["_inter", "lower"]),
        "ci_inter_hi": float(ci.loc["_inter", "upper"]),
        "beta_mod": float(res.params["_mod_c"]),
        "p_mod": float(res.pvalues["_mod_c"]),
        "r2_within": float(res.rsquared_within),
    }


def median_split(df: pd.DataFrame, dv: str, moderator: str) -> dict:
    """Corroborating subsample estimates above/below the pooled median of the
    moderator. Reported alongside the interaction, per the existing design."""
    out = {}
    cut = df[moderator].median()
    for label, sub in (
        ("above", df[df[moderator] > cut]),
        ("below", df[df[moderator] <= cut]),
    ):
        d = sub[[dv, AI_VAR] + CONTROLS].dropna()
        if d.index.get_level_values(0).nunique() < 5:
            out[label] = {"n": int(len(d)), "beta": np.nan, "p": np.nan,
                          "note": "too few countries to estimate"}
            continue
        res = PanelOLS(
            d[dv], d[[AI_VAR] + CONTROLS],
            entity_effects=True, time_effects=True, drop_absorbed=True,
        ).fit(cov_type="kernel", kernel="bartlett", bandwidth=DK_LAGS)
        out[label] = {
            "n": int(res.nobs),
            "beta": float(res.params[AI_VAR]),
            "se": float(res.std_errors[AI_VAR]),
            "p": float(res.pvalues[AI_VAR]),
        }
    return out


def run_all(df: pd.DataFrame) -> pd.DataFrame:
    """Full H4 moderation grid: every DV x every moderator."""
    rows = []
    for dv in DV_LIST:
        for mod_col in MODERATORS:
            if mod_col not in df.columns:
                print(f"  [skip] {mod_col} not in dataframe")
                continue
            try:
                r = estimate_moderation(df, dv, mod_col)
                r["splits"] = median_split(df, dv, mod_col)
                rows.append(r)
            except Exception as exc:                      # noqa: BLE001
                print(f"  [fail] {dv} x {mod_col}: {exc}")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Pre-flight checks — run these BEFORE trusting any coefficient
# --------------------------------------------------------------------------

def preflight(df: pd.DataFrame) -> None:
    """Diagnostics that determine whether H4 is estimable at all.

    The binding risk is that EPI has too little *within-country* variation over
    an eight-year window. A moderator that barely moves within countries cannot
    identify an interaction under country fixed effects, and the estimate will
    be driven by a handful of countries that reformed policy during the sample.
    Check this before interpreting anything.
    """
    print("\n=== PREFLIGHT ===")
    for col in MODERATORS:
        if col not in df.columns:
            print(f"{col:16s}  MISSING")
            continue
        overall = df[col].std()
        within = df.groupby(level=0)[col].transform(lambda s: s - s.mean()).std()
        between = df.groupby(level=0)[col].mean().std()
        share = (within ** 2) / (overall ** 2) if overall else np.nan
        n_missing = int(df[col].isna().sum())
        n_countries = int(df[col].notna().groupby(level=0).any().sum())
        print(
            f"{col:16s}  sd={overall:7.3f}  within={within:7.3f}  "
            f"between={between:7.3f}  within-share={share:5.1%}  "
            f"countries={n_countries:3d}  missing={n_missing:4d}"
        )
    print(
        "\nIf within-share is below roughly 10 percent, the interaction is "
        "identified off very little movement. Report the between-country "
        "median split as the primary evidence in that case, and say so."
    )


if __name__ == "__main__":
    # panel indexed (country, year)
    df = pd.read_parquet("data/panel_v5.parquet").set_index(["country", "year"])
    preflight(df)
    results = run_all(df)
    results.to_csv("output/moderation_eps.csv", index=False)
    print("\n", results[[
        "dv", "moderator", "n", "beta_inter", "se_inter", "p_inter",
        "ci_inter_lo", "ci_inter_hi",
    ]].to_string(index=False))
