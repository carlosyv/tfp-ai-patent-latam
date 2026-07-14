"""
GTFP cross-region pipeline — configuration (Paper 2, JCP target).
Locked design decisions; see README.md for rationale.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# Sample: N = 40, 2016-2023. Nigeria dropped (constant-price NA unavailable).
# ---------------------------------------------------------------------------
REGIONS = {
    "LATAM": ['ARG', 'BOL', 'BRA', 'CHL', 'COL', 'CRI', 'DOM', 'ECU', 'SLV',
              'GTM', 'HND', 'MEX', 'NIC', 'PAN', 'PRY', 'PER', 'URY'],
    "ASIA":  ['CHN', 'IND', 'IDN', 'MYS', 'THA', 'PHL', 'VNM', 'PAK', 'BGD',
              'LKA', 'KAZ'],
    "AFRICA": ['ZAF', 'EGY', 'KEN', 'MAR', 'TUN', 'GHA', 'SEN', 'ETH', 'TZA',
               'UGA', 'DZA', 'CIV'],
}
COUNTRIES = sorted(c for lst in REGIONS.values() for c in lst)
assert len(COUNTRIES) == 40, f"expected 40 countries, got {len(COUNTRIES)}"

START_YR, END_YR = 2016, 2023          # bounded by OECD.AI (2016-) and CO2 lag (-2023)
PIM_INIT_YR = 2008                     # 8 pre-sample years for capital accumulation

# ---------------------------------------------------------------------------
# Parameters (aligned with pipeline_v5 where the constructs overlap)
# ---------------------------------------------------------------------------
ALPHA = 0.35            # capital share, Solow residual (Gollin 2002; Luo et al. 2024)
DELTA_K = 0.05          # capital depreciation, PIM
# ML directional distance: direction g = (y, -b) — expand GDP, contract CO2 equally

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
WB_CSV = DATA_DIR / "wb" / "wb_data_export.csv"
PWT_CSV = DATA_DIR / "pwt" / "pwt-data-human-capital-026-03-22T15-56_export.csv"
ILOSTAT_EMP = DATA_DIR / "ilostat" / "EMP_TEMP_SEX_AGE_NB_A-20260714T0915.csv.gz"  # July pull
OECD_PUBS = DATA_DIR / "cat-ai-patents-country-data" / "publications_yearly_articles.csv"
OECD_FIELD = "All"
OECD_LAST_COMPLETE = 2024

# ---------------------------------------------------------------------------
# WDI indicator map. Tuples = coalesce order (first non-missing wins).
# ---------------------------------------------------------------------------
WDI_INDICATORS = {
    "GDP":          "NY.GDP.MKTP.KD",
    "GFCF":         ("NE.GDI.FTOT.KD", "NE.GDI.TOTL.KD"),  # CHN: GCF fallback (data note)
    "POP":          "SP.POP.TOTL",
    "GDP_PC":       "NY.GDP.PCAP.KD",
    "TRADE":        "NE.TRD.GNFS.ZS",
    "FDI":          "BX.KLT.DINV.WD.GD.ZS",
    "GOV_CONS":     "NE.CON.GOVT.ZS",
    "URBAN":        "SP.URB.TOTL.IN.ZS",
    "RULE_OF_LAW":  ("RL.EST", "GOV_WGI_RL.EST"),          # LatAm pull + Asia/Africa pull
    "BROADBAND":    "IT.NET.BBND.P2",
    "MOBILE":       "IT.CEL.SETS.P2",
    "INTERNET":     "IT.NET.USER.ZS",
    "CO2":          "EN.GHG.CO2.MT.CE.AR5",                # Mt CO2e (AR5), through 2023
    "RENEWABLES":   "EG.FEC.RNEW.ZS",                      # ends 2022 — lag or truncate
    "ENERGY_USE":   "EG.USE.PCAP.KG.OE",
    "PM25":         "EN.ATM.PM25.MC.M3",
    "SERVICES_VA":  "NV.SRV.TOTL.ZS",
    "INDUSTRY_VA":  "NV.IND.TOTL.ZS",
}

# Known data caveats to assert/log at build time
DATA_NOTES = {
    "CHN": "GFCF from NE.GDI.TOTL.KD (gross capital formation) — GFCF unavailable.",
    "NGA": "EXCLUDED — constant-2015-USD national accounts unavailable post-rebase.",
    "RENEWABLES": "coverage ends 2022; moderator specs use lag or 2016-2022 window.",
    "PWT_HC": "trend-extended after 2019 (same rule as pipeline_v5).",
}
