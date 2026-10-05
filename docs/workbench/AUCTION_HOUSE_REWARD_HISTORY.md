# Auction House Reward Campaign History

The reward delivery module records each completed execution attempt in toolkit-local SQLite at `data/auction_house_reward_campaigns.db`.

Each campaign stores the environment snapshot, optional reward template identity, normalized item bundle, recipient mode/count, preview/replay identifiers, overall result, and one recipient row per attempted character with committed/failed status, error text, and delivery-row count.

`Server -> AH Reward History` provides read-only campaign listing/detail views with status/template filters. A failed campaign or partial campaign can produce a **retry preview** containing only recipients whose original result was `failed`.

Retry is never automatic. The history page only creates a new live preview from the original bundle plus failed character IDs. It produces a new preview/replay identity and the operator must execute it through the normal Rewards path with the existing DSP/Topaz Test-only write gate, feature flag, exact profile confirmation, live item/recipient resolution, transactional delivery-box checks, and replay protection.

Successful recipients from an earlier campaign are never included automatically in retry targeting.
