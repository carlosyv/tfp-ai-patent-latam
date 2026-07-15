"""
GTFP pipeline — productivity index module.

Two indices, both solved with scipy.optimize.linprog (HiGHS):

1. Conventional CRS Malmquist (Färe et al. 1994), output-oriented:
       max θ  s.t.  Yλ ≥ θ y0,  Xλ ≤ x0,  λ ≥ 0
   Shephard distance D = 1/θ*;  M = sqrt[(Dt(t1)/Dt(t)) × (Dt1(t1)/Dt1(t))]

2. Malmquist–Luenberger (Chung, Färe & Grosskopf 1997), directional distance
   with CO2 as undesirable output, direction g = (y0, −b0):
       max β  s.t.  Yλ ≥ (1+β) y0
                    Bλ  = (1−β) b0        (weak disposability)
                    Xλ ≤ x0,  λ ≥ 0,  β ∈ [−0.999, 0.999]
   ML = sqrt[ (1+D^t(t)) / (1+D^t(t+1)) × (1+D^{t+1}(t)) / (1+D^{t+1}(t+1)) ]
   ML > 1 ⇒ green-productivity improvement.
   Decomposition: MLEFF = (1+D^t(t)) / (1+D^{t+1}(t+1));  MLTECH = ML / MLEFF.

Cross-period DDFs can be infeasible; incidence is logged and returned.
"""
import numpy as np
import pandas as pd
from scipy.optimize import linprog


# ----------------------------------------------------------------------------
# LP solvers
# ----------------------------------------------------------------------------

def shephard_distance_crs(y0, x0, Y, X):
    """Output-oriented CRS DEA distance. Returns D ∈ (0, 1] (or >1 cross-period),
    np.nan if infeasible."""
    N = len(Y)
    # variables: [λ_1..λ_N, θ];  maximize θ  →  minimize −θ
    c = np.zeros(N + 1)
    c[-1] = -1.0
    # −Yλ + θ y0 ≤ 0 ;  Xλ ≤ x0
    A_ub = np.zeros((1 + X.shape[1], N + 1))
    b_ub = np.zeros(1 + X.shape[1])
    A_ub[0, :N] = -Y
    A_ub[0, -1] = y0
    for j in range(X.shape[1]):
        A_ub[1 + j, :N] = X[:, j]
        b_ub[1 + j] = x0[j]
    res = linprog(c, A_ub=A_ub, b_ub=b_ub,
                  bounds=[(0, None)] * N + [(0, None)], method='highs')
    if not res.success or res.x[-1] <= 1e-12:
        return np.nan
    return 1.0 / res.x[-1]


def directional_distance(y0, b0, x0, Y, B, X):
    """Directional distance function with one good output y, one bad output b,
    direction g = (y0, −b0). Returns β (0 = on frontier), np.nan if infeasible."""
    N = len(Y)
    # variables: [λ_1..λ_N, β]; maximize β → minimize −β
    c = np.zeros(N + 1)
    c[-1] = -1.0
    # good output: Yλ ≥ (1+β) y0  →  −Yλ + β y0 ≤ −y0
    A_ub = np.zeros((1 + X.shape[1], N + 1))
    b_ub = np.zeros(1 + X.shape[1])
    A_ub[0, :N] = -Y
    A_ub[0, -1] = y0
    b_ub[0] = -y0
    # inputs: Xλ ≤ x0
    for j in range(X.shape[1]):
        A_ub[1 + j, :N] = X[:, j]
        b_ub[1 + j] = x0[j]
    # bad output (weak disposability, equality): Bλ + β b0 = b0
    A_eq = np.zeros((1, N + 1))
    A_eq[0, :N] = B
    A_eq[0, -1] = b0
    b_eq = np.array([b0])
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=[(0, None)] * N + [(-0.999, 0.999)], method='highs')
    if not res.success:
        return np.nan
    return float(res.x[-1])


# ----------------------------------------------------------------------------
# Index computation over the panel
# ----------------------------------------------------------------------------

def _period_arrays(df, year, cols):
    d = (df[df.Year == year].dropna(subset=cols)
         .sort_values('Country').set_index('Country'))
    return d


def compute_malmquist_crs(df, input_cols=('CAPITAL', 'EFFECTIVE_LABOR'),
                          output_col='GDP'):
    """Conventional CRS Malmquist index for adjacent years."""
    input_cols = list(input_cols)
    req = input_cols + [output_col]
    years = sorted(df.Year.unique())
    rows, infeas = [], 0
    for yt, yt1 in zip(years[:-1], years[1:]):
        dt, dt1 = _period_arrays(df, yt, req), _period_arrays(df, yt1, req)
        common = sorted(set(dt.index) & set(dt1.index))
        if len(common) < 3:
            continue
        dt, dt1 = dt.loc[common], dt1.loc[common]
        Yt, Xt = dt[output_col].values, dt[input_cols].values
        Yt1, Xt1 = dt1[output_col].values, dt1[input_cols].values
        for i, cty in enumerate(common):
            d_t_t = shephard_distance_crs(Yt[i], Xt[i], Yt, Xt)
            d_t_t1 = shephard_distance_crs(Yt1[i], Xt1[i], Yt, Xt)
            d_t1_t = shephard_distance_crs(Yt[i], Xt[i], Yt1, Xt1)
            d_t1_t1 = shephard_distance_crs(Yt1[i], Xt1[i], Yt1, Xt1)
            if any(np.isnan(v) for v in (d_t_t, d_t_t1, d_t1_t, d_t1_t1)):
                infeas += 1
                m = ec = tc = np.nan
            else:
                ec = d_t1_t1 / d_t_t
                tc = np.sqrt((d_t_t1 / d_t1_t1) * (d_t_t / d_t1_t))
                m = ec * tc
            rows.append({'Country': cty, 'Year': yt1, 'MALM_CRS': m,
                         'MALM_EC': ec, 'MALM_TC': tc})
    out = pd.DataFrame(rows)
    print(f"    Malmquist CRS: {out.MALM_CRS.notna().sum()}/{len(out)} valid "
          f"({infeas} infeasible)")
    return out


def compute_ml_index(df, input_cols=('CAPITAL', 'EFFECTIVE_LABOR'),
                     good_col='GDP', bad_col='CO2'):
    """Malmquist–Luenberger green-TFP index for adjacent years."""
    input_cols = list(input_cols)
    req = input_cols + [good_col, bad_col]
    years = sorted(df.Year.unique())
    rows, infeas = [], 0
    for yt, yt1 in zip(years[:-1], years[1:]):
        dt, dt1 = _period_arrays(df, yt, req), _period_arrays(df, yt1, req)
        common = sorted(set(dt.index) & set(dt1.index))
        if len(common) < 3:
            continue
        dt, dt1 = dt.loc[common], dt1.loc[common]
        Yt, Bt, Xt = dt[good_col].values, dt[bad_col].values, dt[input_cols].values
        Yt1, Bt1, Xt1 = dt1[good_col].values, dt1[bad_col].values, dt1[input_cols].values
        for i, cty in enumerate(common):
            d_t_t = directional_distance(Yt[i], Bt[i], Xt[i], Yt, Bt, Xt)
            d_t_t1 = directional_distance(Yt1[i], Bt1[i], Xt1[i], Yt, Bt, Xt)
            d_t1_t = directional_distance(Yt[i], Bt[i], Xt[i], Yt1, Bt1, Xt1)
            d_t1_t1 = directional_distance(Yt1[i], Bt1[i], Xt1[i], Yt1, Bt1, Xt1)
            if any(np.isnan(v) for v in (d_t_t, d_t_t1, d_t1_t, d_t1_t1)):
                infeas += 1
                ml = mleff = mltech = np.nan
            else:
                num = (1 + d_t_t) * (1 + d_t1_t)
                den = (1 + d_t_t1) * (1 + d_t1_t1)
                ml = np.sqrt(num / den) if den > 0 else np.nan
                mleff = (1 + d_t_t) / (1 + d_t1_t1) if (1 + d_t1_t1) > 0 else np.nan
                mltech = ml / mleff if (mleff and np.isfinite(mleff)
                                        and mleff > 0) else np.nan
            rows.append({'Country': cty, 'Year': yt1, 'GTFP_ML': ml,
                         'ML_EFF': mleff, 'ML_TECH': mltech})
    out = pd.DataFrame(rows)
    print(f"    Malmquist–Luenberger: {out.GTFP_ML.notna().sum()}/{len(out)} valid "
          f"({infeas} infeasible)")
    return out


def add_productivity_indices(panel):
    """Compute both indices on the panel and merge them in."""
    print("  Computing productivity indices …")
    # rescale inputs/outputs to comparable magnitudes for LP conditioning
    work = panel.copy()
    for col, scale in [('GDP', 1e9), ('CAPITAL', 1e9),
                       ('EFFECTIVE_LABOR', 1e6), ('CO2', 1.0)]:
        work[col] = work[col] / scale
    malm = compute_malmquist_crs(work)
    ml = compute_ml_index(work)
    out = (panel.merge(malm, on=['Country', 'Year'], how='left')
                .merge(ml, on=['Country', 'Year'], how='left'))
    return out
