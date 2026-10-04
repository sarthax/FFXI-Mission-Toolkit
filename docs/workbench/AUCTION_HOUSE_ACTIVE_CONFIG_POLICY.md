# Auction House active configuration policy

The DSP/Topaz Auction House validation pipeline now reads the fee and listing policy from the selected server environment instead of relying on built-in historical defaults.

## Active sources

- Topaz: `conf/map.conf`
- DSP: `conf/map_darkstar.conf`; `conf/map.conf` is also recognized for DSP-derived forks.
- Topaz `conf/default/map.conf` is recognized only as a source-tree template. It is never promoted to active policy automatically.

The required settings are:

- `ah_base_fee_single`
- `ah_base_fee_stacks`
- `ah_tax_rate_single`
- `ah_tax_rate_stacks`
- `ah_max_fee`
- `ah_list_limit`

Both `key: value` and `key = value` legacy syntax are accepted, including trailing `#` or `;` comments.

## Fail-closed behavior

Policy loading is blocked when:

- the lineage is not explicitly DSP or Topaz;
- the active map configuration is missing;
- only a default/template configuration is present;
- any required AH setting is missing;
- any numeric setting is invalid or negative;
- multiple DSP active-looking config files contain conflicting AH values.

When policy loading is blocked, the database-backed read-only reread may still run so the administrator can inspect current server state, but invariant validation does not substitute guessed defaults.

## Provenance

A successful policy load records the active config path and a SHA-256 fingerprint over only the six normalized AH settings. Comments and unrelated server settings do not change that fingerprint.

Historical Topaz source confirms the retail-like defaults (`1`, `4`, `1.0`, `0.5`, `10000`, `7`) in `conf/default/map.conf`; those values remain documentation/reference evidence only when an active environment does not explicitly supply them.

## Safety

This layer is read-only. It performs no database mutation, exposes no commit/apply endpoint, and cannot enable the Auction House executor. A future mutation phase must bind the validated policy fingerprint to the operation preview and re-check the active configuration immediately before execution.
