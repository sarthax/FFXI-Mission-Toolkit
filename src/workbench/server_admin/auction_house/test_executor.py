"""Guarded LandSandBoat Auction House executor for TEST environments only.

This module intentionally starts with one narrow mutation: changing the asking price on one
active Auction House row. It exists to prove the write transaction/gating path before player
listing or purchase execution is enabled. It cannot execute against LIVE, DSP, Topaz, custom,
or legacy environments and exposes no free-form SQL surface.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from typing import Any


TEST_WRITE_ENV = "FFXI_MISSION_TOOLKIT_AH_TEST_WRITES"


class TestExecutionBlocked(RuntimeError):
    """Raised when the TEST-only executor fails a safety or consistency gate."""


@dataclass(frozen=True)
class TestWriteIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class TestWriteGate:
    environment: dict[str, Any]
    schema_family_hint: str
    issues: list[TestWriteIssue] = field(default_factory=list)

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
            "supported_operations": ["price_change"],
        }


def test_write_feature_enabled() -> bool:
    return str(os.getenv(TEST_WRITE_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


def evaluate_lsb_test_write_gate(
    *,
    environment: dict[str, Any],
    schema_family_hint: str,
    confirmation: str | None,
    feature_enabled: bool | None = None,
) -> TestWriteGate:
    """Return fail-closed readiness for the narrow LSB TEST executor."""
    issues: list[TestWriteIssue] = []
    family = str(environment.get("family") or "").strip().lower()
    env_kind = str(environment.get("environment") or "").strip().lower()
    schema = str(schema_family_hint or "").strip().lower()
    enabled = test_write_feature_enabled() if feature_enabled is None else bool(feature_enabled)

    if not environment.get("is_active"):
        issues.append(TestWriteIssue("environment_not_active", "The selected server environment is not active."))
    if not environment.get("enabled", True):
        issues.append(TestWriteIssue("environment_disabled", "The selected server environment is disabled."))
    if family != "lsb":
        issues.append(TestWriteIssue("lineage_not_lsb", "TEST execution is currently limited to LandSandBoat."))
    if schema != "lsb-compatible":
        issues.append(TestWriteIssue("schema_not_lsb_compatible", "The live Auction House schema is not LSB-compatible."))
    if env_kind != "test":
        issues.append(TestWriteIssue("environment_not_test", "Auction House execution is currently permitted only for named Test environments."))
    if not enabled:
        issues.append(TestWriteIssue("test_write_feature_disabled", f"Set {TEST_WRITE_ENV}=1 to enable the TEST-only Auction House executor."))

    expected = str(environment.get("name") or "").strip()
    if not expected or str(confirmation or "").strip() != expected:
        issues.append(TestWriteIssue("test_confirmation_required", f"Type the active Test profile name exactly to execute: {expected or 'TEST profile name'}"))

    return TestWriteGate(dict(environment), schema, issues)


def execute_lsb_test_price_change(
    *,
    service,
    environment: dict[str, Any],
    auction_id: int,
    expected_price: int,
    new_price: int,
    confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    """Change one active LSB Auction House asking price inside one guarded transaction.

    This deliberately does not emulate player listing/purchase behavior. It updates only the
    asking-price column of one already-active row, uses SELECT ... FOR UPDATE plus a compare-and-
    swap UPDATE, verifies post-state before commit, and rolls back on every mismatch.
    """
    gate = evaluate_lsb_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise TestExecutionBlocked(f"Auction House TEST execution blocked: {codes}")

    auction_id = int(auction_id)
    expected_price = int(expected_price)
    new_price = int(new_price)
    if auction_id <= 0:
        raise TestExecutionBlocked("auction_id must be positive")
    if expected_price <= 0 or new_price <= 0:
        raise TestExecutionBlocked("Auction House prices must be positive")
    if expected_price == new_price:
        raise TestExecutionBlocked("new_price must differ from expected_price")

    columns = service.schema.auction_columns
    id_col = columns.get("id")
    price_col = columns.get("asking_price")
    sale_col = columns.get("sale_price")
    if not id_col or not price_col or not sale_col:
        raise TestExecutionBlocked("The live LSB Auction House schema is missing required price-change columns")

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
            raise TestExecutionBlocked("The target auction row does not exist")
        current_id, current_price, sale_price = int(row[0]), int(row[1]), int(row[2] or 0)
        before = {"auction_id": current_id, "asking_price": current_price, "sale_price": sale_price}
        if sale_price != 0:
            raise TestExecutionBlocked("The target auction row is no longer active")
        if current_price != expected_price:
            raise TestExecutionBlocked("The target auction price changed after preview; refresh before executing")

        cursor.execute(
            f"UPDATE `auction_house` SET `{price_col}`=%s WHERE `{id_col}`=%s AND `{price_col}`=%s AND `{sale_col}`=0",
            (new_price, auction_id, expected_price),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) != 1:
            raise TestExecutionBlocked("Price update did not affect exactly one active auction row")

        cursor.execute(
            f"SELECT `{id_col}`,`{price_col}`,`{sale_col}` FROM `auction_house` WHERE `{id_col}`=%s FOR UPDATE",
            (auction_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise TestExecutionBlocked("Target auction disappeared during post-state verification")
        after = {"auction_id": int(row[0]), "asking_price": int(row[1]), "sale_price": int(row[2] or 0)}
        if after["asking_price"] != new_price or after["sale_price"] != 0:
            raise TestExecutionBlocked("Auction House post-state verification failed")

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
        "environment": dict(environment),
        "before": before,
        "after": after,
        "write_feature": TEST_WRITE_ENV,
    }
