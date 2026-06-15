# Pipeline data request: Yield Curve (10y minus 2y) (China)

**Pillar:** Growth / Forward-Looking (Tier 1-2)
**Cycle-timing prior:** Leading
**Regional analogue requested:** CGBs 10y-2y
**Requested source / frequency:** FRED / daily  (lag: Real-time)

## Status
`Missing-Sourceable` — not currently in the pipeline, but a free/public source exists.

## Candidate free source
Monthly CN 10y free via OECD/FRED IRLTLT01CNM156N; 2y CGB leg and daily frequency remain hard

## Notes
DISCREPANCY vs spec: spec flags CN 10y as the canonical accepted gap, but a monthly CN 10y IS free (OECD MEI via FRED). The genuine gaps are the 2y CGB leg (no clean free source) and daily frequency. The slope is partially buildable at monthly frequency.

---
*Auto-templated by `scripts/phase_0_coverage_check.py` from the regime-aa
indicator coverage map. Regenerate after updating the map.*
