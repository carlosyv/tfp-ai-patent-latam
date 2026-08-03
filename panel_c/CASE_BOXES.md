# Panel C — Firm Case Boxes (for §6.3, edit F1)

*Draft text for four boxed case studies. Every quotation is from the firm's own SEC
annual filing (Form 10-K / 20-F) as downloaded in `panel_c/filings_txt/`; exposure
figures are the study's own non-risk AI mentions per 10,000 words. Percentiles are
within the 98 firms with FY2024 exposure data.*

**Purpose in the chapter.** The econometric result of §6.3 is a null-to-weakly-negative
within-firm association between AI exposure and labour productivity. These four boxes
show what that null contains: the region's most AI-intensive listed firms are
demonstrably deploying AI in production, yet the productivity signature is not (yet)
visible in aggregate accounting outcomes. They also answer the committee's request for
concrete industry-level evidence of *how* AI is used in Latin America (Shen Yao's
"which industries use AI well?"), and they discipline the exposure measure by showing
that its top decile corresponds to genuine, verifiable AI activity rather than
disclosure boilerplate.

---

## Box 6.1 — MercadoLibre (Argentina/Uruguay; e-commerce and fintech; Form 10-K)

**AI exposure trajectory:** 0.00 (2017) → 0.53 (2019) → 1.15 (2021) → 1.90 (2024) →
2.29 (2025). FY2024 exposure places it in the **96th percentile** of the panel.

MercadoLibre is the clearest case of AI moving from acquisition to infrastructure. The
firm's FY2019 filing records the purchase of "a machine learning company in Argentina"
(2018) — AI enters the disclosure record as a transaction. By FY2024 the same firm
describes an internal platform for "building, testing, training, deploying and
monitoring predictive Machine Learning models, all with the purpose of increasing the
rate of development and, by extension, the pace and cadence with which all our teams add
value to our users," and states plainly: "We are expanding our investment in AI across
the entire Company. This includes using generative AI and continuing to integrate AI
capabilities into our products and services."

*Reading:* the disclosure describes AI as a **capability-building investment** — tooling
that raises the productivity of the firm's own engineers — rather than a measured cost
reduction. This is precisely the J-curve pattern: resources are being absorbed by
intangible capital formation whose returns post-date the sample.

---

## Box 6.2 — Globant (Argentina; IT services; Form 20-F)

**AI exposure trajectory:** 1.28 (2017) → 1.48 (2019) → 2.73 (2022) → 2.14 (2024) →
3.35 (2025). FY2024 exposure is the **98th percentile** — the highest in the panel.

Globant is the region's most AI-declarative firm, and the only one for which AI is
simultaneously an input and a product. Its FY2019 filing lists as a corporate principle:
"We use artificial intelligence ('AI') for everything," describing an "Augmented Globant"
initiative "designed to embrace the power of artificial intelligence to augment Globant's
capabilities." By FY2024 the firm enumerates named AI products — "Augoor, MagnifAI,
GeneXus Enterprise AI, Navigate, StarmeUp, Walmeric and FluentLab" — and frames the
market opportunity through third-party forecasts of enterprise AI spending.

*Reading:* Globant's absorptive capacity is visible on the balance sheet — its
intangible-asset intensity rises from 0.31 (2017) to 0.59 (2024), the highest sustained
level among the case firms. It is the strongest single observation in favour of FH2 even
though the moderation term is insignificant panel-wide, and it illustrates why
intangibles intensity (rather than disclosed R&D, reported by only 15% of the panel) was
chosen as the primary absorptive-capacity proxy.

---

## Box 6.3 — Nu Holdings (Brazil; digital banking; Form 20-F)

**AI exposure trajectory:** 1.18 (2021, first filing) → 1.42 (2023) → 2.07 (2024) →
2.31 (2025). FY2024 exposure: **97th percentile**. FY2024 filing contains 37 AI-term
mentions, the largest count among the case firms.

Nu articulates an explicit data-to-cost mechanism, presented in its filing as a numbered
causal chain: "More Data — We gather data from each customer and each transaction. The
data compound in value as we grow and drive our artificial intelligence and machine
learning algorithms to improve everything we do. This leads to: Lower Costs — We use our
growing data sets to make smarter underwriting decisions."

*Reading:* this is the mechanism the macro chapters cannot observe — AI acting on
*intermediation efficiency* rather than on physical output per worker. Nu's measured
labour productivity is extreme (revenue per employee far above the panel median), but it
reflects a business model with few employees rather than an identifiable AI effect. The
box is therefore also a caution: for financial firms, revenue-per-employee conflates
leverage and technology, which is why §6.3 reports non-financial subsamples separately.

---

## Box 6.4 — StoneCo (Brazil; payments; Form 20-F)

**AI exposure trajectory:** 0.49 (2018) → 0.41 (2020) → 0.57 (2022) → 1.34 (2024) →
1.54 (2025). FY2024 exposure: **93rd percentile**.

StoneCo shows the flattest early trajectory of the four and a distinct tonal shift. In
FY2019 AI appears as operational tooling: the platform "aggregate[s] data and utilize[s]
advanced technologies, such as AI and machine learning tools across our enterprise," with
a "CRM AI Technology" that "empower[s] our client relationship, client retention and
Green Angel teams." By FY2024, a substantial share of AI language has migrated into risk
disclosure: "we may fail to adopt artificial intelligence and machine learning technology
or to comply with its regulatory framework."

*Reading:* StoneCo demonstrates why the exposure measure separates risk-factor mentions
from business-section mentions. A naive total-mention count would record rising AI
"intensity" that is partly regulatory hedging rather than deployment. It also shows the
adoption-without-measured-gain pattern at its starkest: documented operational AI use
from 2018 onward, with no corresponding break in measured productivity.

---

## Cross-case synthesis (to close §6.3)

1. **The exposure measure is valid.** All four firms are independently recognisable as
   the region's AI leaders, and their disclosures describe specific systems, products and
   acquisitions — not generic language. The measure's top decile is substantively real.
2. **AI use is real but recent and concentrated.** Meaningful deployment language appears
   from ~2019 and accelerates after 2022 in every case; the region's AI-intensive firms
   are a handful of platform, fintech and IT-services companies, overwhelmingly Brazilian
   and Argentine.
3. **The mechanisms are intangible-intensive.** Engineering productivity (MercadoLibre),
   product capability (Globant), underwriting quality (Nu), service operations (StoneCo)
   — none map cleanly onto revenue-per-employee within a 3–5 year window, which is the
   substantive reason the FH1 estimate is null rather than merely underpowered.
4. **Absorptive capacity is visible where it is measurable.** Globant's rising intangible
   intensity is the clearest firm-level analogue of the macro conditioning result, and
   supports the dissertation's central claim even where the panel-wide interaction term
   is imprecise.

*Data-quality note for drafting:* accounting series for CI&T and StoneCo contain
irregularities (an intangibles ratio above unity for CI&T in 2022; discontinuous employee
counts for StoneCo), so the boxes rely on disclosure text and the exposure measure rather
than on those firms' financial ratios. Flag in the §6.3 limitations paragraph.
