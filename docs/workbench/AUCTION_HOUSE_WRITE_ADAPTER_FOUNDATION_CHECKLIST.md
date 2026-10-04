# Auction House Write Foundation Review Checklist

- [x] No executor or Apply endpoint added.
- [x] Snapshot fingerprint is deterministic and changes with target state.
- [x] Named active environment is required.
- [x] LIVE requires exact profile-name confirmation.
- [x] Legacy fallback environments remain write-blocked.
- [x] LSB listing requires `auction_house_list`.
- [x] LSB purchase/cleanup requires `auction_house_buy` and `delivery_box_insert`.
- [x] Purchase/cleanup requires `delivery_box` table presence.
- [x] Normal purchase requires an exact buyer snapshot.
- [x] Audit intent captures before/expected-after/environment/adapter metadata.
- [x] Plans contain descriptive semantic steps, not executable mutation SQL.
- [x] Tests assert `executor_enabled == false` and `executable == false`.
