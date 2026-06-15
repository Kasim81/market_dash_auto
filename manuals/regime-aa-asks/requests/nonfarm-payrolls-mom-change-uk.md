# Pipeline data request: Nonfarm Payrolls (MoM change) (UK)

**Pillar:** Growth / Coincident Real-Time (Tier 3-4)
**Cycle-timing prior:** Lagging
**Regional analogue requested:** ONS payrolled employees
**Requested source / frequency:** BLS / monthly  (lag: 1st Friday)

## Status
`Missing-Sourceable` — not currently in the pipeline, but a free/public source exists.

## Candidate free source
ONS PAYE RTI (CMD datasets API, not classic timeseries)

## Notes
PAYE RTI payrolls are not in the classic ONS timeseries (Zebedee) API the fetcher uses — they live in the newer CMD datasets API. Needs a CMD-fetch path, or use LFS employment level as a proxy. Deferred.

---
*Auto-templated by `scripts/phase_0_coverage_check.py` from the regime-aa
indicator coverage map. Regenerate after updating the map.*
