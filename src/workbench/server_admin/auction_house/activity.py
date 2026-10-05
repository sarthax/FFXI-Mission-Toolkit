"""Unified read-only Auction House administration activity feed."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .audit_ledger import append_execution_event, list_events, list_execution_events
from .reward_campaigns import get_campaign, list_campaigns


def _environment_name(environment: dict[str, Any] | None) -> str | None:
    env = dict(environment or {})
    value = env.get("name") or env.get("profile_name")
    return None if value is None else str(value)


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value in (None, ""):
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def record_executor_result(
    *, environment: dict[str, Any] | None, result: dict[str, Any], operation: str | None = None,
    request_payload: dict[str, Any] | None = None,
) -> int:
    """Record a completed executor outcome without participating in its server transaction."""
    result = dict(result or {})
    request = dict(request_payload or {})
    op = str(operation or result.get("operation") or "unknown").strip() or "unknown"
    status = str(result.get("status") or "unknown").strip() or "unknown"
    auction_id = _first_int(result.get("auction_id"), request.get("auction_id"))
    item_id = _first_int(result.get("item_id"), request.get("item_id"))
    character_id = _first_int(
        result.get("char_id"), result.get("buyer_id"), result.get("seller_id"),
        request.get("char_id"), request.get("buyer_id"), request.get("seller_id"),
    )
    payload = {
        "result": result,
        "request": {
            key: value for key, value in request.items()
            if key not in {"confirmation", "password", "secret", "token"}
        },
    }
    return append_execution_event(
        operation=op,
        status=status,
        environment=environment,
        payload=payload,
        auction_id=auction_id,
        character_id=character_id,
        item_id=item_id,
        preview_id=str(result.get("preview_id") or request.get("preview_id") or "") or None,
        replay_id=str(result.get("replay_id") or request.get("replay_id") or "") or None,
    )


def _parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
        return dict(parsed) if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _iso(value: str | None) -> str:
    text = str(value or "")
    return text or datetime.now(timezone.utc).isoformat()


def unified_activity(
    *, environment_name: str | None = None, operation: str | None = None, status: str | None = None,
    character_id: int | None = None, item_id: int | None = None,
    since_utc: str | None = None, until_utc: str | None = None,
    include_evidence: bool = True, include_campaigns: bool = True, limit: int = 200,
) -> dict[str, Any]:
    """Merge execution outcomes, preview/replay evidence, and reward campaigns newest-first."""
    safe_limit = max(1, min(int(limit), 1000))
    scan_limit = min(max(safe_limit * 4, 200), 2000)
    rows: list[dict[str, Any]] = []

    for event in list_execution_events(
        environment_name=environment_name,
        operation=operation,
        status=status,
        character_id=character_id,
        item_id=item_id,
        since_utc=since_utc,
        until_utc=until_utc,
        limit=scan_limit,
    ):
        rows.append({
            "source": "execution",
            "id": event.get("event_id"),
            "occurred_at_utc": _iso(event.get("occurred_at_utc")),
            "environment_name": event.get("environment_name"),
            "environment_family": event.get("environment_family"),
            "operation": event.get("operation"),
            "status": event.get("status"),
            "auction_id": event.get("auction_id"),
            "character_id": event.get("character_id"),
            "item_id": event.get("item_id"),
            "preview_id": event.get("preview_id"),
            "replay_id": event.get("replay_id"),
            "payload": event.get("payload") or {},
        })

    if include_evidence and not character_id and not item_id:
        for event in list_events(limit=min(scan_limit, 1000)):
            if environment_name and str(event.get("environment_name") or "") != str(environment_name):
                continue
            if operation and str(event.get("operation") or "") != str(operation):
                continue
            evidence_status = event.get("validation_status") or event.get("event_type")
            if status and str(evidence_status or "") != str(status):
                continue
            occurred = _iso(event.get("occurred_at_utc"))
            if since_utc and occurred < str(since_utc):
                continue
            if until_utc and occurred > str(until_utc):
                continue
            rows.append({
                "source": "evidence",
                "id": event.get("event_id"),
                "occurred_at_utc": occurred,
                "environment_name": event.get("environment_name"),
                "environment_family": event.get("environment_family"),
                "operation": event.get("operation") or event.get("event_type"),
                "status": evidence_status,
                "auction_id": None,
                "character_id": None,
                "item_id": None,
                "preview_id": event.get("preview_id"),
                "replay_id": event.get("replay_id"),
                "payload": _parse_payload(event.get("payload_json")),
            })

    if include_campaigns:
        for campaign in list_campaigns(limit=min(scan_limit, 500)):
            env_name = _environment_name(campaign.get("environment"))
            if environment_name and env_name != str(environment_name):
                continue
            if operation and str(operation) not in {"reward_delivery", "reward_campaign"}:
                continue
            if status and str(campaign.get("overall_status") or "") != str(status):
                continue
            occurred = _iso(campaign.get("completed_at_utc") or campaign.get("created_at_utc"))
            if since_utc and occurred < str(since_utc):
                continue
            if until_utc and occurred > str(until_utc):
                continue
            detail = None
            if character_id is not None:
                detail = get_campaign(str(campaign["campaign_id"]))
                if int(character_id) not in {int(r["char_id"]) for r in detail.get("recipients") or []}:
                    continue
            if item_id is not None and int(item_id) not in {int(i.get("item_id") or 0) for i in campaign.get("items") or []}:
                continue
            rows.append({
                "source": "reward_campaign",
                "id": campaign.get("campaign_id"),
                "occurred_at_utc": occurred,
                "environment_name": env_name,
                "environment_family": (campaign.get("environment") or {}).get("family"),
                "operation": "reward_delivery",
                "status": campaign.get("overall_status"),
                "auction_id": None,
                "character_id": int(character_id) if character_id is not None else None,
                "item_id": int(item_id) if item_id is not None else None,
                "preview_id": campaign.get("preview_id"),
                "replay_id": campaign.get("replay_id"),
                "payload": detail or campaign,
            })

    rows.sort(key=lambda row: (str(row.get("occurred_at_utc") or ""), str(row.get("id") or "")), reverse=True)
    rows = rows[:safe_limit]
    return {
        "count": len(rows),
        "limit": safe_limit,
        "filters": {
            "environment_name": environment_name, "operation": operation, "status": status,
            "character_id": character_id, "item_id": item_id,
            "since_utc": since_utc, "until_utc": until_utc,
            "include_evidence": bool(include_evidence), "include_campaigns": bool(include_campaigns),
        },
        "rows": rows,
        "read_only": True,
    }
