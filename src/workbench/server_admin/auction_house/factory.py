"""Construct a read-only Auction House context for the active server environment."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Reuse the already-audited native DSP/Topaz/LSB database-profile parser. The AH workspace does
# not depend on Character Editor services or mutation code; this small connection primitive can
# move to a shared runtime module later without changing the AH contract.
from workbench.editors.character.connection import DatabaseProfile, connect, discover_database_profile

from .service import AuctionHouseService


@dataclass
class AuctionHouseContext:
    profile: DatabaseProfile
    service: AuctionHouseService

    def public_status(self) -> dict[str, Any]:
        return {"database": self.profile.public_dict(), "auction_house": self.service.status(), "read_only": True}

    def close(self) -> None:
        try:
            self.service.connection.close()
        except Exception:
            pass


def open_auction_house(server_root: Path | str, **connect_kwargs) -> AuctionHouseContext:
    profile = discover_database_profile(server_root)
    connection = connect(profile, **connect_kwargs)
    try:
        return AuctionHouseContext(profile=profile, service=AuctionHouseService(connection))
    except Exception:
        connection.close()
        raise
