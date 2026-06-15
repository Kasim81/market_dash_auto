# Pipeline data request: Senior Loan Officer Survey (SLOOS) (Eurozone)

**Pillar:** Growth / Forward-Looking (Tier 1-2)
**Cycle-timing prior:** Leading
**Regional analogue requested:** ECB Bank Lending Survey
**Requested source / frequency:** Federal Reserve / quarterly  (lag: Quarterly)

## Status
`Missing-Sourceable` — not currently in the pipeline, but a free/public source exists.

## Candidate free source
ECB BLS dataset (free); exact net-% key pending

## Notes
Free via ECB Data Portal, dataflow BLS (10 dims). Net-% series use BLS_ITEM=APP + agg WFNET (e.g. BLS/Q.U2.ALL.APP.E.O.B6.ST.S.WFNET backward / .F6. forward); BLS_ITEM=LEV gives only count aggregations. Canonical 'net % tightening, enterprises, 3m' not yet pinned — deferred to avoid a wrong series.

---
*Auto-templated by `scripts/phase_0_coverage_check.py` from the regime-aa
indicator coverage map. Regenerate after updating the map.*
