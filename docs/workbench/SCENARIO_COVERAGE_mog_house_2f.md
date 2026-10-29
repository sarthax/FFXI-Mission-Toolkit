# Mog House 2F — domain scenarios and coverage

Draft: `data/testing/domain_drafts/mog_house_2f.json` (design-only, `execution_enabled: false`). Source: DSP `feature/mog-house-2f-patio` @ `2fb0d6120002965e8c60b5bba7df81a892163191`; deployed binary UNKNOWN.

Related domains: [gardening](SCENARIO_COVERAGE_gardening.md), [moghancement](SCENARIO_COVERAGE_moghancement.md). There was no Mog House 2F domain page before this one.

## Cases
| Case | mhflag | Result (manual, 2026-10-22) |
|---|---|---|
| MH2F-01 fresh character | 0 | pass |
| MH2F-02 single nation bit | 2 | pass |
| MH2F-03 home vs non-home | 3 | pass |
| MH2F-04 | 5 | pass |
| MH2F-05 | 6 | pass |
| MH2F-06 unlock + floor travel | 7 | pass |
| MH2F-07 2F with exit bits unset | 0x60 | not re-run in this matrix |
| MH2F-08 locked request leaves flags | 3 | pass (observed behaviour) |
| MH2F-09 relog persistence | 0x27 | not run |
| MH2F-10 grey floor option in locked home house | 3 | OPEN evidence gap |

## What blocks automation
- No runner action to set `char_stats.mhflag` with servers stopped between cases.
- Greyed menu entries are not machine-readable; only screenshots exist.
- `0x00A` readback of +0xA8/+0xAA/+0xAE is capturable but no assertion operation is bound.

Procedure notes: stop the map server before DB edits (it overwrites `mhflag` on save). Retail evidence: two captures named in the draft's `evidence_refs`.
