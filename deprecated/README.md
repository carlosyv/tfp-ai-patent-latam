# Deprecated Pipeline Scripts

This directory contains prior versions of the TFP-AI pipeline that were superseded by the v4 (no-imputation) specification. They are retained for methodological transparency and to document the evolution of the model across dissertation versions.

**These scripts are not part of the canonical replication package. For replication of the results reported in the paper, use the main pipeline at the repository root.**

---

## Files

### `run_dissertation_v3_noimput_pipeline.py`

Version 3 of the pipeline — **no imputation** variant. Key differences from the published v4 specification:

- **H3 moderator**: Financial development (private credit % GDP, bank deposits % GDP). These variables were dropped in v4 after failing to reach statistical significance in the LAC context.
- **H4 moderator**: Internet users per 100 (IT.NET.USER.ZS). Replaced in v4 by mobile cellular penetration (IT.CEL.SETS.P2), which better captures AI tool adoption patterns in Latin America (mobile-first, cloud/SaaS).
- **Controls**: Narrower set — trade openness, log GDPpc, internet users, private credit, human capital. FDI net inflows, government consumption, and urban population were added in v4.

### `run_dissertation_v3_pipeline.py`

Version 3 of the pipeline — **with imputation** variant. Applies linear interpolation (`interpolate(limit_direction='both')`) to ILOSTAT labor and WDI control variables, and fills unobserved AI patent country-years with zero. Same H3/H4 specification as v3_noimput above.

---

## Methodological Evolution Summary

| Dimension | v3 | v4 (Published) |
|---|---|---|
| H3 moderator | Financial development (private credit, deposits) | Institutional quality — Rule of Law (RL.EST) |
| H4 primary moderator | Internet users per 100 | Mobile cellular per 100 (IT.CEL.SETS.P2) |
| H4r robustness | Fixed broadband | Fixed broadband (retained) |
| Additional controls | — | FDI inflows, govt consumption, urban population |
| Imputation | Two variants (with/without) | No-imputation as canonical specification |

The transition from v3 to v4 was motivated by (i) the empirical failure of financial development moderators to reach significance in any specification, (ii) the theoretical and empirical case for mobile penetration as the primary digital infrastructure channel in LAC, and (iii) the adoption of a stricter no-imputation approach to preserve the information structure of the raw data.
