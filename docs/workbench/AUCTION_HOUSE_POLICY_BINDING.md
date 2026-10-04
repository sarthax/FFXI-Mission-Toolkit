# Auction House preview policy binding

DSP/Topaz Auction House previews are bound to the exact active AH configuration that was present when the preview was generated.

## Preview provenance

Each legacy preview response carries a `policy_binding` block containing:

- explicit lineage family;
- active configuration source path;
- source kind;
- SHA-256 policy fingerprint;
- policy-readiness status and issues;
- hard-disabled executor/executable flags.

The fingerprint covers only the six normalized AH policy values (`ah_base_fee_single`, `ah_base_fee_stacks`, `ah_tax_rate_single`, `ah_tax_rate_stacks`, `ah_max_fee`, and `ah_list_limit`). Unrelated comments/settings do not invalidate a preview.

## Validation-time reread

`prepare_validate_from_active_config` reloads the active server policy and compares it with the preview binding before invariant validation is allowed to continue. Validation fails closed when:

- the preview contains no policy binding;
- active AH policy can no longer be loaded safely;
- the policy fingerprint changed;
- the active config source path changed;
- the declared DSP/Topaz family changed.

Database reread evidence is still returned for diagnostics, but invariant validation returns `None` when the policy binding is stale or unverifiable. The administrator must regenerate the preview under the new active policy.

## Non-legacy lineages

The GUI does not invent a DSP/Topaz policy for other lineages. Their preview payload records that legacy policy binding is not applicable; lineage-specific policy binding must be implemented separately before any future executor work.

## Safety

This feature is read-only. It adds no mutation SQL, commit primitive, Apply endpoint, or executor enablement. Its purpose is to make a future write phase unable to reuse a preview after AH configuration drift.
