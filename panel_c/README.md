# Panel C — Firm-Level Dataset (US-listed Latin American firms)

Stage 1 (DONE 2026-07-12): `build_universe.py` — firm universe via two passes:
address-country sweep of EDGAR company search (legacy + current country codes; legacy
codes dominate: AR=C1, BR=D5, CL=F3, CO=F8, MX=O5; note F4=legacy China, R1=legacy
Philippines — collisions filtered by ground-truth `stateOrCountryDescription` from
submissions JSON) + name curation incl. EDGAR English-translated registrant names
(FEMSA="MEXICAN ECONOMIC DEVELOPMENT", CSN="NATIONAL STEEL CO", Eletrobras="AXIA
Energia"/"BRAZILIAN ELECTRIC POWER CO", Procaps="Sofgen Pharma").

Outputs:
- `firm_universe.csv` — 124 firms (90 active, 33 delisted-in-window, 1 debt registrant
  [PEMEX, flagged]); BR 55, AR 22, MX 18, CL 11, CO 9, PE 7, PA 1, UY 1; 118×20-F, 6×10-K.
  Upper bound ≈ 838 firm-years FY2017–2024.
- `firm_universe_rejected.csv` — 29 rejected with reasons (name collisions, shells,
  duplicates, debt-only subsidiaries) — keep for the data appendix.
- `cache/` — raw candidates + submissions JSONs (resumable; do not commit if too large).

Next stages (per tfp-ai/edgar_data_acquisition_guide.md):
2. Filing text download (20-F/10-K primary docs) + AI-keyword exposure measure.
3. XBRL financials (us-gaap + ifrs-full), employees from filing text, panel assembly.
4. Regressions: FE, FH2 moderation, sector shift-share IV.

## Stage 2 (DONE 2026-07-12): filing texts + AI-exposure measure
- `fetch_filings.py` — manifest (847 firm-FY 20-F/10-K, FY2017–2025) + parallel download,
  HTML stripped on arrival; `filings_txt/` = 985 MB plain text, 0 failures.
- `ai_exposure.py` — Babina-style dictionary (core + applied terms; bare "AI" only as
  diagnostic), risk-factor section separated where detectable, exposure = non-risk
  mentions per 10k words. Output: `firm_ai_exposure.csv` (847 rows).
- QA: top-20 FY2022–24 ranking = CI&T, Semantix, Zenvia, Globant, Nu, MELI, dLocal,
  Inter, StoneCo, Despegar — exactly the expected tech/fintech tail. Mean exposure
  rises monotonically 2017→2025 (0.035→0.60 per 10k, ~17×), post-2021 acceleration
  consistent with the GPT-era implementation narrative. 49% of firm-years have ≥1 AI
  mention.
- Known limitation: risk-factor section detected in only 48% of filings (heading
  variants); where undetected, non-risk exposure = total exposure. Refine headings
  regex in stage 3 QA; report exposure_total as robustness.

Next: stage 3 — XBRL financials (companyfacts, us-gaap + ifrs-full), employee counts
from filing text, panel assembly.

## Stage 3 (DONE 2026-07-13): XBRL financials + employees + panel assembly
- `xbrl_financials.py` — companyfacts for 121/124 firms (404: Petrobras Argentina,
  Gafisa — pre-/non-XBRL delistings); dual-taxonomy fallback chains; concept + currency
  recorded per fact (data appendix). `firm_financials.csv`: 953 firm-FY.
- `employees.py` — regex headcounts from filing text; found in 82% of filings
  (`firm_employees.csv`; median of plausible matches, min/max kept for QA).
- `assemble_panel.py` — `firm_panel.csv`: 930 firm-FY rows / 124 firms, FY2017–2025.
  **Regression-ready (revenue+employees+AI exposure, FY2017–24): 509 rows, 99 firms.**
  Currency mix: USD 178, BRL 167, ARS 56, MXN 44, CLP 31, COP 16, PEN 14.
- Known gaps for stage-4 QA: (i) revenue coverage 77% — banks lack the generic Revenue
  concept; add bank chains (ifrs: InterestRevenueCalculatedUsingEffectiveInterestMethod,
  us-gaap: InterestAndDividendIncomeOperating) to lift coverage; (ii) ARS firm-years
  need IAS-29 hyperinflation handling (USD-reported robustness or exclusion);
  (iii) R&D disclosed for only 15% — use intangibles intensity as the primary
  absorptive-capacity moderator, R&D as secondary.

Next: stage 4 — currency conversion/deflation, moderators, FE regressions + sector
shift-share IV; case boxes.

## Stage 4 (DONE 2026-07-13): cleaning + first-pass regressions
- `revenue_fix.py` — extended revenue chains (banks: effective-interest revenue;
  telecoms/transport variants; Volaris = summed transport components): +101 firm-FY
  recovered. Final analysis panel: `firm_panel_clean.csv`, **565 firm-years / 107 firms**
  (FY2017–24) with lprod + exposure. FX = WB year-avg + US-CPI deflation (2017 base);
  ARS flagged (ias29_ars).
- `regressions.py` — two-way FE (iterated demeaning) + firm-clustered SEs + 2SLS,
  numpy-only (verify against linearmodels on full install).
- **First-pass results (report honestly):**
  FH1: no positive within-firm exposure–productivity association; contemporaneous ≈ 0;
  lagged exposure weakly NEGATIVE (non-financials: b=-0.89, t=-1.69) — consistent with
  the GPT J-curve / adjustment-cost phase and with the macro H1 null.
  FH2: intangibles/size moderation ≈ 0 in this pass — moderators are crude (intangibles
  include M&A goodwill); try pre-period digital intensity and country-level moderators.
  IV: leave-one-out sector-year exposure instrument is WEAK (first-stage F≈0.5) — do not
  use; needs external sector shocks (Babina US sector exposure or global sector AI
  patent growth × pre-period sector mix). Macro Bartik (Panels A/B) is the committed
  identification strategy (opening report §4.7) and is built separately.

## Case boxes (DONE 2026-07-21) — `CASE_BOXES.md`
Four boxed cases for §6.3 (MercadoLibre, Globant, Nu Holdings, StoneCo), built from
verbatim quotations in the firms' own filings (filings_txt/) plus this study's exposure
series and percentiles. Purpose: validate the exposure measure, supply the
industry-level "how is AI used" evidence the committee asked for, and explain what the
FH1 null contains (intangible-intensive mechanisms invisible to revenue-per-employee).
Data-quality caveat carried in the doc: CI&T/StoneCo financial ratios are irregular, so
boxes rely on text + exposure, not those firms' accounting ratios.
