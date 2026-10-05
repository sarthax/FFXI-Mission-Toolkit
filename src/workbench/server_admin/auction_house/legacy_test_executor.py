"""Guarded DSP/Topaz Auction House executor for TEST environments only.

Supported mutations are intentionally narrow and admin-oriented so the toolkit can prove real
write safety without duplicating the legacy map-server player transaction machinery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
import time
from typing import Any

LEGACY_TEST_WRITE_ENV = "FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES"
_SUPPORTED_FAMILIES = {"dsp", "topaz"}
_EXPECTED_SCHEMA = "legacy-dsp-topaz-compatible"


class LegacyTestExecutionBlocked(RuntimeError):
    """Raised when the guarded legacy TEST executor fails closed."""


@dataclass(frozen=True)
class LegacyTestWriteIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class LegacyTestWriteGate:
    environment: dict[str, Any]
    schema_family_hint: str
    issues: list[LegacyTestWriteIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "environment": dict(self.environment),
            "schema_family_hint": self.schema_family_hint,
            "ready": self.ready,
            "issues": [asdict(issue) for issue in self.issues],
            "test_only": True,
            "live_permitted": False,
            "supported_families": sorted(_SUPPORTED_FAMILIES),
            "supported_operations": ["price_change", "synthetic_listing"],
            "feature_flag": LEGACY_TEST_WRITE_ENV,
        }


def legacy_test_write_feature_enabled() -> bool:
    return str(os.getenv(LEGACY_TEST_WRITE_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


def evaluate_legacy_test_write_gate(
    *,
    environment: dict[str, Any],
    schema_family_hint: str,
    confirmation: str | None,
    feature_enabled: bool | None = None,
) -> LegacyTestWriteGate:
    issues: list[LegacyTestWriteIssue] = []
    family = str(environment.get("family") or "").strip().lower()
    env_kind = str(environment.get("environment") or "").strip().lower()
    schema = str(schema_family_hint or "").strip().lower()
    enabled = legacy_test_write_feature_enabled() if feature_enabled is None else bool(feature_enabled)

    if not environment.get("is_active"):
        issues.append(LegacyTestWriteIssue("environment_not_active", "The selected server environment is not active."))
    if not environment.get("enabled", True):
        issues.append(LegacyTestWriteIssue("environment_disabled", "The selected server environment is disabled."))
    if family not in _SUPPORTED_FAMILIES:
        issues.append(LegacyTestWriteIssue("lineage_not_legacy_supported", "TEST execution is limited to DSP and Topaz environments."))
    if schema != _EXPECTED_SCHEMA:
        issues.append(LegacyTestWriteIssue("schema_not_legacy_compatible", "The live Auction House schema is not DSP/Topaz-compatible."))
    if env_kind != "test":
        issues.append(LegacyTestWriteIssue("environment_not_test", "Auction House execution is permitted only for named Test environments."))
    if not enabled:
        issues.append(LegacyTestWriteIssue("legacy_test_write_feature_disabled", f"Set {LEGACY_TEST_WRITE_ENV}=1 to enable guarded DSP/Topaz Test writes."))

    expected = str(environment.get("name") or "").strip()
    if not expected or str(confirmation or "").strip() != expected:
        issues.append(LegacyTestWriteIssue("test_confirmation_required", f"Type the active Test profile name exactly to execute: {expected or 'Test profile name'}"))

    return LegacyTestWriteGate(dict(environment), schema, issues)


def _require_gate(*, service, environment: dict[str, Any], confirmation: str, feature_enabled: bool | None) -> None:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")


def execute_legacy_test_price_change(
    *,
    service,
    environment: dict[str, Any],
    auction_id: int,
    expected_price: int,
    new_price: int,
    confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Change one active DSP/Topaz Auction House asking price in one transaction."""
    _require_gate(service=service, environment=environment, confirmation=confirmation, feature_enabled=feature_enabled)

    auction_id = int(auction_id)
    expected_price = int(expected_price)
    new_price = int(new_price)
    if auction_id <= 0:
        raise LegacyTestExecutionBlocked("auction_id must be positive")
    if expected_price <= 0 or new_price <= 0:
        raise LegacyTestExecutionBlocked("Auction House prices must be positive")
    if expected_price == new_price:
        raise LegacyTestExecutionBlocked("new_price must differ from expected_price")

    columns = service.schema.auction_columns
    id_col = columns.get("id")
    price_col = columns.get("asking_price")
    sale_col = columns.get("sale_price")
    if not id_col or not price_col or not sale_col:
        raise LegacyTestExecutionBlocked("The live legacy Auction House schema is missing required price-change columns")

    connection = service.connection
    cursor = connection.cursor()
    before: dict[str, int] | None = None
    after: dict[str, int] | None = None
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            f"SELECT `{id_col}`,`{price_col}`,`{sale_col}` FROM `auction_house` WHERE `{id_col}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("The target auction row does not exist")
        current_id, current_price, sale_price = int(row[0]), int(row[1]), int(row[2] or 0)
        before = {"auction_id": current_id, "asking_price": current_price, "sale_price": sale_price}
        if sale_price != 0:
            raise LegacyTestExecutionBlocked("The target auction row is no longer active")
        if current_price != expected_price:
            raise LegacyTestExecutionBlocked("The target auction price changed after preview; refresh before executing")

        cursor.execute(
            f"UPDATE `auction_house` SET `{price_col}`=%s WHERE `{id_col}`=%s AND `{price_col}`=%s AND `{sale_col}`=0",
            (new_price, auction_id, expected_price),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Price update did not affect exactly one active auction row")

        cursor.execute(
            f"SELECT `{id_col}`,`{price_col}`,`{sale_col}` FROM `auction_house` WHERE `{id_col}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("Target auction disappeared during post-state verification")
        after = {"auction_id": int(row[0]), "asking_price": int(row[1]), "sale_price": int(row[2] or 0)}
        if after["asking_price"] != new_price or after["sale_price"] != 0:
            raise LegacyTestExecutionBlocked("Auction House post-state verification failed")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    return {
        "status": "committed",
        "operation": "price_change",
        "test_only": True,
        "family": str(environment.get("family") or "").strip().lower(),
        "environment": dict(environment),
        "before": before,
        "after": after,
        "write_feature": LEGACY_TEST_WRITE_ENV,
    }


def execute_legacy_test_synthetic_listing(
    *,
    service,
    environment: dict[str, Any],
    item_id: int,
    seller_id: int,
    price: int,
    stack: bool,
    confirmation: str,
    feature_enabled: bool | None = None,
    listed_at: int | None = None,
) -> dict[str, Any]:
    """Insert one explicit admin-created DSP/Topaz active listing.

    This is not a simulated player listing: no inventory is removed and no listing fee is charged.
    It intentionally injects supply for administration/testing and reports that economic effect.
    """
    _require_gate(service=service, environment=environment, confirmation=confirmation, feature_enabled=feature_enabled)

    item_id = int(item_id)
    seller_id = int(seller_id)
    price = int(price)
    stack = bool(stack)
    if item_id <= 0 or seller_id <= 0 or price <= 0:
        raise LegacyTestExecutionBlocked("item_id, seller_id, and price must be positive")

    item = service.item_snapshot(item_id)
    seller = service.character_snapshot(seller_id)
    if not item:
        raise LegacyTestExecutionBlocked("The requested item does not exist")
    if int(item.get("category_id") or 0) <= 0:
        raise LegacyTestExecutionBlocked("The requested item is not assigned to an Auction House category")
    stack_size = max(1, int(item.get("stack_size") or 1))
    if stack and stack_size <= 1:
        raise LegacyTestExecutionBlocked("The requested item cannot be listed as a stack")
    if not seller:
        raise LegacyTestExecutionBlocked("The requested seller character does not exist")

    columns = service.schema.auction_columns
    required = ("id", "item_id", "stack", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at")
    if any(not columns.get(name) for name in required):
        raise LegacyTestExecutionBlocked("The live legacy Auction House schema is missing required synthetic-listing columns")

    insert_fields = [columns["item_id"], columns["stack"], columns["seller_id"]]
    params: list[Any] = [item_id, 1 if stack else 0, seller_id]
    if columns.get("seller_name"):
        insert_fields.append(columns["seller_name"])
        params.append(str(seller.get("char_name") or ""))
    insert_fields.extend([columns["listed_at"], columns["asking_price"]])
    timestamp = int(listed_at if listed_at is not None else time.time())
    if timestamp <= 0:
        raise LegacyTestExecutionBlocked("listed_at must be a positive epoch timestamp")
    params.extend([timestamp, price])

    quoted_fields = ",".join(f"`{name}`" for name in insert_fields)
    placeholders = ",".join(["%s"] * len(insert_fields))
    connection = service.connection
    cursor = connection.cursor()
    auction_id: int | None = None
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            f"INSERT INTO `auction_house`({quoted_fields}) VALUES({placeholders})",
            tuple(params),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise LegacyTestExecutionBlocked("Synthetic listing insert did not create exactly one row")
        auction_id = int(getattr(cursor, "lastrowid", 0) or 0)
        if auction_id <= 0:
            raise LegacyTestExecutionBlocked("Synthetic listing insert did not return an auction ID")

        cursor.execute(
            f"SELECT `{columns['item_id']}`,`{columns['stack']}`,`{columns['seller_id']}`,`{columns['asking_price']}`,`{columns['sale_price']}`,`{columns['sold_at']}` "
            f"FROM `auction_house` WHERE `{columns['id']}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LegacyTestExecutionBlocked("Synthetic listing disappeared during post-state verification")
        if (
            int(row[0]) != item_id
            or bool(row[1]) != stack
            or int(row[2]) != seller_id
            or int(row[3]) != price
            or int(row[4] or 0) != 0
            or int(row[5] or 0) != 0
        ):
            raise LegacyTestExecutionBlocked("Synthetic listing post-state verification failed")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    quantity = stack_size if stack else 1
    return {
        "status": "committed",
        "operation": "synthetic_listing",
        "test_only": True,
        "family": str(environment.get("family") or "").strip().lower(),
        "environment": dict(environment),
        "auction_id": auction_id,
        "item_id": item_id,
        "seller_id": seller_id,
        "seller_name": seller.get("char_name"),
        "price": price,
        "stack": stack,
        "quantity": quantity,
        "listed_at": timestamp,
        "economic_effect": {
            "synthetic_supply_injected": quantity,
            "listing_fee_charged": 0,
            "seller_inventory_removed": 0,
            "seller_proceeds_on_sale": "auction_house_buy trigger path",
        },
        "write_feature": LEGACY_TEST_WRITE_ENV,
    }
