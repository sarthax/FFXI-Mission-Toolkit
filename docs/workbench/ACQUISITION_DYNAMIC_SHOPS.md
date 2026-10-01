# Special / Dynamic Shop Acquisition Profiles

## Curio Vendor Moogle — profiled

The Curio Vendor Moogle is intentionally **not** treated as an ordinary static `SOLD_BY` shop.

Audited LandSandBoat source shape:

- NPC scripts select `xi.shop.curioVendorMoogleStock[option]` and pass the chosen category to `xi.shop.curioVendorMoogle(...)`.
- The canonical stock table lives in `scripts/globals/shop.lua` as `xi.shop.curioVendorMoogleStock`.
- Category keys use `xi.shop.curio.<category>`.
- Explicit stock rows have the form `{ item, price, requiredKeyItem, optionalZone }`.
- `xi.shop.curioVendorMoogle` checks the required key item and optional current-zone restriction before adding the item to the shop.

Workbench profile behavior:

- `parse_curio_vendor_stock()` accepts only explicit literal item/price/key-item/optional-zone rows.
- Unsupported/dynamic row expressions are reported rather than interpreted.
- The acquisition catalog emits `CURIO_VENDOR`, not `SOLD_BY`.
- Each path preserves category, price, required key-item literal, optional zone literal, source path, and a `conditional` marker.
- Item and key-item literals remain source identities; this profile does not perform the separate canonical item/key-item identity-reconciliation milestone.

## Remaining dynamic-shop work

`SPECIAL_DYNAMIC_SHOP` remains unprofiled by design. Add future shop families only after their source shape and gating semantics are independently audited; do not generalize from Curio naming or NPC location alone.
