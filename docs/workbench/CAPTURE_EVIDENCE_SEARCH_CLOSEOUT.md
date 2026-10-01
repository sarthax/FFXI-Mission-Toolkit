# Capture Evidence Search closeout

Status: **foundation complete**

Authoritative completion point: main after PR #196 (`d60a0bf202335931d3ae78a6bfdad88386cdb2f6`).

The Capture Data Explorer / Evidence Search redesign now has the deterministic relationship families that are justified by the current normalized schemas:

- exact physical-source provenance (shared hashed byte/line spans and identical SQLite source rows),
- unique non-temporal packet correlation,
- captured numeric entity identity with zone and uniqueness guards,
- ordinary item identity across structured item/vendor/crafting observations with key-item namespace isolation,
- deterministic CapLog canonical/legacy chat projection from one parser-owned source observation.

Related Evidence also now exposes compact family counts, human-readable dataset/family labels, record-type context, and direct handoffs to Source Locator, Data Explorer, Packet Viewer, Entity Profile, Item Profile, and relevant Evidence Search modules.

No further deterministic relationship family should be added without a source-owned stable key or another explicit canonical mapping. In particular, timestamp proximity, text/name similarity, price proximity, record order, and numeric collisions across unrelated namespaces remain excluded from VERIFIED relationships.

## Remaining follow-up

- Real-user UX tuning for which capture panels default open/closed and which high-frequency actions should be promoted.
- New relationship families only when future capture adapters or canonical mappings provide an explicit stable identity key.

The older `[~]` Evidence Search / related-evidence lines in `ROADMAP.md` are therefore stale status text; they should be reconciled in a future roadmap-maintenance pass when the large file can be edited safely without connector truncation risk.
