#!/usr/bin/env python3
"""
build_gairi_panel.py
====================

Merge the *Global Ranking* sheets of the Oxford Insights / IDRC
**Government AI Readiness Index (GAIRI)**, editions 2019-2025, into a single
tidy country-year panel.

Motivation
----------
GAIRI is used in this project as a candidate proxy for *complementary
capabilities* (state capacity, data & infrastructure, technology sector) that
condition whether AI-related innovation translates into measured TFP gains.
The published workbooks are not analysis-ready: sheet names, header offsets,
column layouts, country nomenclature and the score scale all change across
editions. This script normalises them once, deterministically.

Source heterogeneity handled
----------------------------
edition  sheet                    header row  rank/country/score cols  layout
2019     'Rankings'                       2   0, 1, 2                  wide, regional blocks
2020     'Global ranking'                 1   0, 1, 2                  long
2021     'Global ranking'                 1   0, 1, 2                  long
2022     'Global rankings'                1   0, 1, 2                  long
2023     'Global rankings'                1   0, 1, 2                  long
2024     'Ranking'                        1   0, 1, 2                  long
2025     'Global Rankings'                2   1, 2, 3                  long, leading blank col/row

Score scale
-----------
The 2019 edition publishes scores on a 0-10 scale; 2020-2025 use 0-100.
Both are retained:
  * ``score_raw``  - exactly as published (do not compare across 2019/2020).
  * ``score_100``  - common 0-100 basis (2019 multiplied by 10).
Note that the underlying indicator set, pillar weights and country coverage
also change between editions, so ``score_100`` is *comparable in units only*.
Levels are NOT a consistent time series; ``rank_pct`` (see below) is the safer
cross-edition object, and even that is sensitive to coverage changes.

Outputs (written to data/gov-ai-readiness/merged/)
-------------------------------------------------
gairi_global_rankings_2019_2025.csv   tidy long panel, one row per country-year
gairi_country_crosswalk.csv           every source label -> ISO3, with editions
README.md                             provenance and caveats

Usage
-----
    python build_gairi_panel.py

Author: Carlos Yalta Vargas
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "data" / "gov-ai-readiness" / "raw"
OUT_DIR = REPO_ROOT / "data" / "gov-ai-readiness" / "merged"

PANEL_CSV = OUT_DIR / "gairi_global_rankings_2019_2025.csv"
CROSSWALK_CSV = OUT_DIR / "gairi_country_crosswalk.csv"

# --------------------------------------------------------------------------- #
# Source specification
# --------------------------------------------------------------------------- #
# (year, filename, sheet, n_header_rows_to_skip, [rank_col, country_col, score_col])

SOURCES: list[tuple[int, str, str, int, list[int]]] = [
    (2019, "SHARED_-2019-Index-data-for-report.xlsx", "Rankings", 2, [0, 1, 2]),
    (2020, "2020-Government-AI-Readiness-Index-public-dataset.xlsx", "Global ranking", 1, [0, 1, 2]),
    (2021, "2021-Government-AI-Readiness-Index-public-dataset.xlsx", "Global ranking", 1, [0, 1, 2]),
    (2022, "2022-Government-AI-Readiness-Index-public-data.xlsx", "Global rankings", 1, [0, 1, 2]),
    (2023, "2023-Government-AI-Readiness-Index-Public-Indicator-Data.xlsx", "Global rankings", 1, [0, 1, 2]),
    (2024, "2024-GAIRI-data.xlsx", "Ranking", 1, [0, 1, 2]),
    (2025, "2025-Government-AI-Readiness-Index-data-1.xlsx", "Global Rankings", 2, [1, 2, 3]),
]

# Editions published on a 0-10 rather than 0-100 scale.
SCALE_10_YEARS = {2019}

# Rows in the source sheets that are not countries.
NON_COUNTRY_LABELS = {"AVERAGE", "AVERAGE SCORE", "MEAN", "TOTAL", "COUNTRY"}

# --------------------------------------------------------------------------- #
# Country name -> ISO 3166-1 alpha-3 crosswalk
# --------------------------------------------------------------------------- #
# Every distinct label appearing in any of the seven editions is listed
# explicitly. Fuzzy matching is deliberately avoided: a silent mis-map here
# would propagate into the regression sample. Keys are normalised by
# ``_norm_key`` (casefold, strip accents/punctuation) before lookup, so
# "Cote D'Ivoire" and "Côte d'Ivoire" collapse to one entry.

ISO3_BY_NAME: dict[str, str] = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "DZA", "Andorra": "AND",
    "Angola": "AGO", "Antigua and Barbuda": "ATG", "Argentina": "ARG",
    "Armenia": "ARM", "Australia": "AUS", "Austria": "AUT", "Azerbaijan": "AZE",
    "Bahamas": "BHS", "Bahrain": "BHR", "Bangladesh": "BGD", "Barbados": "BRB",
    "Belarus": "BLR", "Belgium": "BEL", "Belize": "BLZ", "Benin": "BEN",
    "Bhutan": "BTN",
    "Bolivia": "BOL", "Bolivia (Plurinational State of)": "BOL",
    "Bosnia and Herzegovina": "BIH", "Botswana": "BWA", "Brazil": "BRA",
    "Brunei Darussalam": "BRN", "Bulgaria": "BGR", "Burkina Faso": "BFA",
    "Burundi": "BDI",
    "Cabo Verde": "CPV", "Cape Verde": "CPV",
    "Cambodia": "KHM", "Cameroon": "CMR", "Canada": "CAN",
    "Central African Republic": "CAF", "Chad": "TCD", "Chile": "CHL",
    "China": "CHN", "Colombia": "COL", "Comoros": "COM", "Congo": "COG",
    "Costa Rica": "CRI", "Croatia": "HRV", "Cuba": "CUB", "Cyprus": "CYP",
    "Czech Republic": "CZE", "Czechia": "CZE",
    "Cote d'Ivoire": "CIV",
    "Democratic People's Republic of Korea": "PRK", "North Korea": "PRK",
    "Democratic Republic of the Congo": "COD",
    "Denmark": "DNK", "Djibouti": "DJI", "Dominica": "DMA",
    "Dominican Republic": "DOM", "Ecuador": "ECU", "Egypt": "EGY",
    "El Salvador": "SLV", "Equatorial Guinea": "GNQ", "Eritrea": "ERI",
    "Estonia": "EST", "Eswatini": "SWZ", "Ethiopia": "ETH", "Fiji": "FJI",
    "Finland": "FIN", "France": "FRA", "Gabon": "GAB",
    "Gambia": "GMB", "Gambia (Republic of The)": "GMB",
    "Georgia": "GEO", "Germany": "DEU", "Ghana": "GHA", "Greece": "GRC",
    "Grenada": "GRD", "Guatemala": "GTM", "Guinea": "GIN",
    "Guinea Bissau": "GNB", "Guinea-Bissau": "GNB",
    "Guyana": "GUY", "Haiti": "HTI", "Honduras": "HND", "Hungary": "HUN",
    "Iceland": "ISL", "India": "IND", "Indonesia": "IDN",
    "Iran": "IRN", "Iran (Islamic Republic of)": "IRN",
    "Iraq": "IRQ", "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA",
    "Jamaica": "JAM", "Japan": "JPN", "Jordan": "JOR", "Kazakhstan": "KAZ",
    "Kenya": "KEN", "Kiribati": "KIR", "Kuwait": "KWT", "Kyrgyzstan": "KGZ",
    "Lao People's Democratic Republic": "LAO", "Laos": "LAO",
    "Latvia": "LVA", "Lebanon": "LBN", "Lesotho": "LSO", "Liberia": "LBR",
    "Libya": "LBY", "Liechtenstein": "LIE", "Lithuania": "LTU",
    "Luxembourg": "LUX", "Madagascar": "MDG", "Malawi": "MWI",
    "Malaysia": "MYS", "Maldives": "MDV", "Mali": "MLI", "Malta": "MLT",
    "Marshall Islands": "MHL", "Mauritania": "MRT", "Mauritius": "MUS",
    "Mexico": "MEX",
    "Micronesia": "FSM", "Micronesia (Federated States of)": "FSM",
    "Moldova": "MDA", "Republic of Moldova": "MDA",
    "Monaco": "MCO", "Mongolia": "MNG", "Montenegro": "MNE",
    "Morocco": "MAR", "Mozambique": "MOZ", "Myanmar": "MMR",
    "Namibia": "NAM", "Nauru": "NRU", "Nepal": "NPL", "Netherlands": "NLD",
    "New Zealand": "NZL", "Nicaragua": "NIC", "Niger": "NER",
    "Nigeria": "NGA",
    "North Macedonia": "MKD", "Republic of North Macedonia": "MKD",
    "Norway": "NOR", "Oman": "OMN", "Pakistan": "PAK", "Palau": "PLW",
    "Panama": "PAN", "Papua New Guinea": "PNG", "Paraguay": "PRY",
    "Peru": "PER", "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT",
    "Qatar": "QAT",
    "Republic of Korea": "KOR", "South Korea": "KOR",
    "Romania": "ROU",
    "Russia": "RUS", "Russian Federation": "RUS",
    "Rwanda": "RWA", "Saint Kitts and Nevis": "KNA", "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT", "Samoa": "WSM",
    "San Marino": "SMR", "Sao Tome and Principe": "STP",
    "Saudi Arabia": "SAU", "Senegal": "SEN", "Serbia": "SRB",
    "Seychelles": "SYC", "Sierra Leone": "SLE", "Singapore": "SGP",
    "Slovakia": "SVK", "Slovenia": "SVN", "Solomon Islands": "SLB",
    "Somalia": "SOM", "South Africa": "ZAF", "South Sudan": "SSD",
    "Spain": "ESP", "Sri Lanka": "LKA", "State of Palestine": "PSE",
    "Sudan": "SDN", "Suriname": "SUR", "Sweden": "SWE", "Switzerland": "CHE",
    "Syria": "SYR", "Syrian Arab Republic": "SYR",
    "Taiwan": "TWN", "Tajikistan": "TJK",
    "Tanzania": "TZA", "United Republic of Tanzania": "TZA",
    "Thailand": "THA", "Timor-Leste": "TLS", "Togo": "TGO", "Tonga": "TON",
    "Trinidad and Tobago": "TTO", "Tunisia": "TUN",
    "Turkey": "TUR", "Turkiye": "TUR",
    "Turkmenistan": "TKM", "Tuvalu": "TUV", "Uganda": "UGA",
    "Ukraine": "UKR", "United Arab Emirates": "ARE",
    "United Kingdom": "GBR",
    "United Kingdom of Great Britain and Northern Ireland": "GBR",
    "United States of America": "USA", "Uruguay": "URY", "Uzbekistan": "UZB",
    "Vanuatu": "VUT",
    "Venezuela": "VEN", "Venezuela, Bolivarian Republic of": "VEN",
    "Viet Nam": "VNM", "Vietnam": "VNM",
    "Yemen": "YEM", "Zambia": "ZMB", "Zimbabwe": "ZWE",
}

# Canonical (short, English) display name per ISO3, so the merged panel does
# not inherit whichever label the last edition happened to use.
CANONICAL_NAME: dict[str, str] = {}
for _name, _iso in ISO3_BY_NAME.items():
    # First listed label for each ISO3 wins; the dict above is ordered so that
    # the short conventional form appears first.
    CANONICAL_NAME.setdefault(_iso, _name)

# --------------------------------------------------------------------------- #
# Study panels (see README.md of the replication package)
# --------------------------------------------------------------------------- #

PANEL_A = {"ARG", "BRA", "CHL", "COL", "CRI", "DOM", "MEX", "PER", "URY"}
PANEL_B = PANEL_A | {"BOL", "ECU", "SLV", "GTM", "HND", "NIC", "PAN", "PRY"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _norm_key(label: str) -> str:
    """Normalise a country label for crosswalk lookup.

    Strips accents, collapses whitespace, removes apostrophes/periods and
    casefolds, so that e.g. "Côte D'Ivoire", "Cote d'Ivoire" and
    "COTE DIVOIRE" all map to the same key.
    """
    s = unicodedata.normalize("NFKD", str(label))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'").replace("'", "").replace(".", "")
    s = " ".join(s.split())
    return s.casefold()


ISO3_BY_KEY = {_norm_key(k): v for k, v in ISO3_BY_NAME.items()}


def load_edition(year: int, filename: str, sheet: str, skip: int,
                 cols: list[int]) -> pd.DataFrame:
    """Read one GAIRI workbook and return a tidy rank/country/score frame."""
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing source workbook: {path}")

    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    df = raw.iloc[skip:, cols].copy()
    df.columns = ["rank", "country_source", "score_raw"]

    # Drop layout artefacts: blank spacer rows, regional sub-tables, averages.
    df = df.dropna(subset=["country_source"])
    df["country_source"] = df["country_source"].astype(str).str.strip()
    df = df[~df["country_source"].str.upper().isin(NON_COUNTRY_LABELS)]
    df = df[df["country_source"] != ""]

    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["score_raw"] = pd.to_numeric(df["score_raw"], errors="coerce")
    df = df.dropna(subset=["rank", "score_raw"])

    df["year"] = year
    df["source_file"] = filename
    df["source_sheet"] = sheet
    return df.reset_index(drop=True)


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assemble the merged panel and the country-label crosswalk."""
    frames = [load_edition(*spec) for spec in SOURCES]
    panel = pd.concat(frames, ignore_index=True)

    # --- ISO3 mapping ------------------------------------------------------ #
    panel["iso3"] = panel["country_source"].map(lambda s: ISO3_BY_KEY.get(_norm_key(s)))
    unmapped = sorted(panel.loc[panel["iso3"].isna(), "country_source"].unique())
    if unmapped:
        raise ValueError(
            "Country labels absent from ISO3_BY_NAME - add them explicitly "
            f"rather than guessing:\n  " + "\n  ".join(unmapped)
        )

    panel["country"] = panel["iso3"].map(CANONICAL_NAME)

    # --- score harmonisation ---------------------------------------------- #
    panel["score_100"] = panel["score_raw"].where(
        ~panel["year"].isin(SCALE_10_YEARS), panel["score_raw"] * 10.0
    )
    panel["score_scale"] = panel["year"].map(
        lambda y: "0-10" if y in SCALE_10_YEARS else "0-100"
    )

    # --- coverage-normalised rank ----------------------------------------- #
    # Country coverage varies from 161 (2021) to 197 (2025); a raw rank is not
    # comparable across editions. rank_pct expresses position as a percentile
    # of that edition's ranked set (0 = top, 1 = bottom).
    panel["n_ranked"] = panel.groupby("year")["iso3"].transform("size")
    panel["rank_pct"] = (panel["rank"] - 1) / (panel["n_ranked"] - 1)

    # --- study-panel flags ------------------------------------------------- #
    panel["panel_a"] = panel["iso3"].isin(PANEL_A).astype(int)
    panel["panel_b"] = panel["iso3"].isin(PANEL_B).astype(int)
    panel["latam_panel"] = panel["panel_b"]  # Panel B is the wider LatAm set

    # --- duplicate guard --------------------------------------------------- #
    dupes = panel[panel.duplicated(["iso3", "year"], keep=False)]
    if not dupes.empty:
        raise ValueError(
            "Duplicate iso3-year observations after merge:\n"
            f"{dupes[['year', 'country_source', 'iso3', 'rank']].to_string()}"
        )

    panel = panel.sort_values(["iso3", "year"]).reset_index(drop=True)

    out_cols = [
        "iso3", "country", "year", "rank", "n_ranked", "rank_pct",
        "score_raw", "score_100", "score_scale",
        "panel_a", "panel_b", "latam_panel",
        "country_source", "source_file", "source_sheet",
    ]
    panel = panel[out_cols]

    # --- crosswalk --------------------------------------------------------- #
    crosswalk = (
        panel.groupby(["country_source", "iso3", "country"], as_index=False)
        .agg(editions=("year", lambda s: ", ".join(map(str, sorted(s.unique())))),
             n_editions=("year", "nunique"))
        .sort_values(["country", "country_source"])
        .reset_index(drop=True)
    )

    return panel, crosswalk


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, crosswalk = build_panel()

    panel.to_csv(PANEL_CSV, index=False)
    crosswalk.to_csv(CROSSWALK_CSV, index=False)

    # ---------------- console summary ---------------- #
    print(f"Merged GAIRI panel written to: {PANEL_CSV}")
    print(f"  observations : {len(panel):,}")
    print(f"  countries    : {panel['iso3'].nunique()}")
    print(f"  years        : {panel['year'].min()}-{panel['year'].max()}")
    print()
    print("Observations per edition:")
    per_year = panel.groupby("year").agg(
        n=("iso3", "size"),
        latam=("panel_b", "sum"),
        score_min=("score_100", "min"),
        score_max=("score_100", "max"),
    )
    print(per_year.to_string())
    print()
    print(f"Crosswalk written to: {CROSSWALK_CSV} ({len(crosswalk)} source labels)")

    missing_latam = sorted(PANEL_B - set(panel.loc[panel["panel_b"] == 1, "iso3"]))
    if missing_latam:
        print(f"WARNING: LatAm panel countries never matched: {missing_latam}")
    else:
        print("All 17 LatAm study countries matched.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
