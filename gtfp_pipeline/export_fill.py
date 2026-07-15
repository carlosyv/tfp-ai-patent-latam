"""Export fill_data.json — every number the JCP manuscript needs, pulled
programmatically from results.json + diagnostics.json (no hand-typing)."""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import OUT_DIR  # noqa: E402

res = json.loads((OUT_DIR / 'results.json').read_text())
diag = json.loads((OUT_DIR / 'diagnostics' / 'diagnostics.json').read_text())
panel = pd.read_csv(OUT_DIR / 'merged_panel_with_indices.csv')

fill = {
    'sample': {
        'n_countries': int(panel.Country.nunique()),
        'n_obs_panel': int(len(panel)),
        'window': [int(panel.Year.min()), int(panel.Year.max())],
        'regions': {r: int(panel[panel.REGION == r].Country.nunique())
                    for r in ['LATAM', 'ASIA', 'AFRICA']},
        'gtfp_valid': int(panel.GTFP_ML.notna().sum()),
        'gtfp_possible': int(panel[panel.Year >= 2017].shape[0]),
        'malm_valid': int(panel.MALM_CRS.notna().sum()),
    },
    'descriptives': {
        r: {'GTFP_ML': round(float(g.GTFP_ML.mean()), 4),
            'MALM_CRS': round(float(g.MALM_CRS.mean()), 4),
            'LN_TFP_SOLOW': round(float(g.LN_TFP_SOLOW.mean()), 4),
            'LN_AI': round(float(g.LN_AI.mean()), 4),
            'CO2_mean_Mt': round(float(g.CO2.mean()), 1),
            'N_index': int(g.GTFP_ML.notna().sum())}
        for r, g in panel.groupby('REGION')
    },
    'cd_tests': res['cd_tests'],
    'benchmark': {d: res['benchmark'][d]['FE_DK'] for d in res['benchmark']},
    'region_year_fe': res['r1_region_year_fe'],
    'regional_interactions': {
        d: {k: v for k, v in res['regional'][d].items()
            if k.startswith(('LN_AI', 'AIx', 'sub_'))}
        for d in res['regional']},
    'moderation': res['moderation'],
    'quantile_solow': res['quantile_solow'],
    'lag_profile': res['r3_lag_profile'],
    'h3_paired': res['r2_h3_paired'],
    'robustness': res['robustness'],
    'diag': {
        'ml_infeasible_by_country': diag['d2_ml_infeasibility']['by_country'],
        'wedge_overall': diag['d3_wedge']['overall'],
        'solow_cd_within_regions': {k: v for k, v in diag['d4_solow_csd'].items()
                                    if k.startswith('cd_')},
        'drop_LATAM': {d: diag['d5_sensitivity'][d].get('drop_LATAM')
                       for d in diag['d5_sensitivity']},
        'latam_quantile': diag['d6_latam_quantile'],
        'ccemg': diag['d6_ccemg'],
    },
}

out = OUT_DIR / 'fill_data.json'
out.write_text(json.dumps(fill, indent=2, default=str))
print(f"saved {out}")
print("sections:", sorted(fill.keys()))
