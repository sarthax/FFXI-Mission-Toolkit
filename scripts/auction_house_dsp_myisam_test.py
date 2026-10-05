"""One-shot local operator entry point for DSP Test MyISAM player listing.

Run only against a disposable named DSP Test profile after setting both Auction House
Test-write feature flags. This intentionally does not expose an HTTP mutation route.
"""
from __future__ import annotations

import argparse
import json

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.server_admin.auction_house.dsp_myisam_listing import (
    dsp_myisam_listing_readiness,
    execute_dsp_myisam_test_player_listing,
)
from workbench.server_admin.auction_house.factory import open_auction_house


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DSP Test-only MyISAM Auction House player listing")
    parser.add_argument("--readiness", action="store_true", help="report readiness only; do not mutate")
    parser.add_argument("--seller-id", type=int, default=0)
    parser.add_argument("--inventory-slot", type=int, default=0)
    parser.add_argument("--item-id", type=int, default=0)
    parser.add_argument("--price", type=int, default=0)
    parser.add_argument("--stack", action="store_true")
    parser.add_argument("--confirmation", default="", help="exact active DSP Test profile name")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = get_active_server_root()
    if root is None:
        raise SystemExit("No active server profile")
    environment = get_active_server_identity()
    ctx = open_auction_house(root)
    try:
        if args.readiness:
            result = dsp_myisam_listing_readiness(service=ctx.service, environment=environment)
            result["server_root"] = str(root)
        else:
            result = execute_dsp_myisam_test_player_listing(
                service=ctx.service,
                server_root=root,
                environment=environment,
                seller_id=args.seller_id,
                inventory_slot=args.inventory_slot,
                item_id=args.item_id,
                price=args.price,
                stack=args.stack,
                confirmation=args.confirmation,
            )
        print(json.dumps(result, indent=2, default=str))
        return 0
    finally:
        ctx.close()


if __name__ == "__main__":
    raise SystemExit(main())
