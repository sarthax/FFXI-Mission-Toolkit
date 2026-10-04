"""Construct a read-only Auction House context for the active server environment."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .service import AuctionHouseService


@dataclass
class AuctionHouseContext:
    profile: Any
    service: AuctionHouseService

    def public_status(self) -> dict[str, Any]:
        return {"database": self.profile.public_dict(), "auction_house": self.service.status(), "read_only": True}

    def close(self) -> None:
        try:
            self.service.connection.close()
        except Exception:
            pass


def open_auction_house(server_root: Path | str, **connect_kwargs) -> AuctionHouseContext:
    # Reuse the already-audited DSP/Topaz/LSB database-profile parser, but import it lazily so the
    # standalone AH router can be imported and tested without creating a Character Editor package
    # initialization cycle. No Character Editor service or mutation code is used here.
    from workbench.editors.character.connection import connect, discover_database_profile

    profile = discover_database_profile(server_root)
    connection = connect(profile, **connect_kwargs)
    try:
        return AuctionHouseContext(profile=profile, service=AuctionHouseService(connection))
    except Exception:
        connection.close()
        raise
