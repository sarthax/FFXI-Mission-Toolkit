"""Bounded, in-memory, OFFLINE reconciliation of untrusted evidence receipts.

This is a local regression adapter, NOT the unapproved XIHeadless #105 wire
protocol, an artifact verifier, a v1 importer replacement, or durable storage.
It cannot confer normative PASS/FAIL, authenticate sources, or start tasks.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
from threading import RLock

FORMAT = "toolkit-offline-receipt/1"
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_PHASES = frozenset({"PARTIAL", "TERMINAL"})
_STATES = frozenset({"accepted", "running", "completed", "failed", "cancelled", "interrupted"})
_TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted"})
_REPORTED = frozenset({"PASS", "FAIL", "BLOCKED", "SKIPPED", "UNKNOWN"})
_KEYS = frozenset({
    "format", "run_id", "execution_id", "attempt", "operation_id",
    "receipt_id", "feature_id", "case_id", "definition_revision",
    "phase", "operation_state", "evidence_complete", "reported_verdict",
    "evidence_digest", "evidence", "missing_artifacts", "provenance",
})
_PROVENANCE = frozenset({
    "observer", "original_ref", "source_authenticated", "oracle_approved",
})


def canonical_evidence_digest(evidence: dict) -> str:
    """Hash only supplied JSON data; this does NOT hash physical evidence."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a JSON object")
    try:
        data = json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("evidence is not bounded JSON") from exc
    if len(data) > 32768:
        raise ValueError("evidence exceeds offline limit")
    return sha256(data).hexdigest()


def _validate(receipt: object) -> dict:
    if not isinstance(receipt, dict) or set(receipt) != _KEYS:
        raise ValueError("invalid offline receipt fields")
    if receipt["format"] != FORMAT:
        raise ValueError("unsupported offline receipt version")
    for name in ("run_id", "execution_id", "operation_id", "receipt_id",
                 "feature_id", "case_id", "definition_revision"):
        if not isinstance(receipt[name], str) or not _ID.fullmatch(receipt[name]):
            raise ValueError("invalid offline identity")
    if type(receipt["attempt"]) is not int or not 1 <= receipt["attempt"] <= 1000000:
        raise ValueError("invalid attempt")
    if receipt["phase"] not in _PHASES or receipt["operation_state"] not in _STATES:
        raise ValueError("unsupported lifecycle state")
    if receipt["phase"] == "TERMINAL" and receipt["operation_state"] not in _TERMINAL:
        raise ValueError("terminal receipt requires observed terminal state")
    if type(receipt["evidence_complete"]) is not bool:
        raise ValueError("invalid completeness")
    if receipt["reported_verdict"] is not None and receipt["reported_verdict"] not in _REPORTED:
        raise ValueError("unsupported reported verdict")
    missing = receipt["missing_artifacts"]
    if not isinstance(missing, list) or len(missing) > 20 or any(
        not isinstance(x, str) or not _ID.fullmatch(x) for x in missing
    ) or len(missing) != len(set(missing)):
        raise ValueError("invalid missing artifact identifiers")
    if receipt["evidence_complete"] and (
        receipt["phase"] != "TERMINAL" or missing
    ):
        raise ValueError("incomplete evidence cannot be declared complete")
    provenance = receipt["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE:
        raise ValueError("invalid provenance shape")
    for name in ("observer", "original_ref"):
        if not isinstance(provenance[name], str) or not 1 <= len(provenance[name]) <= 128:
            raise ValueError("invalid provenance claim")
    # No accepted offline fixture may assert independent authority.
    if (provenance["source_authenticated"] is not False or
            provenance["oracle_approved"] is not False):
        raise ValueError("offline receipt cannot assert source/oracle authority")
    claimed = receipt["evidence_digest"]
    if not isinstance(claimed, str) or not re.fullmatch(r"[0-9a-f]{64}", claimed):
        raise ValueError("invalid digest claim")
    if canonical_evidence_digest(receipt["evidence"]) != claimed:
        raise ValueError("evidence digest mismatch")
    try:
        raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("receipt is not JSON") from exc
    if len(raw) > 65536:
        raise ValueError("offline receipt exceeds limit")
    return deepcopy(receipt)


def _blocked(reason: str) -> dict:
    return {"status": "BLOCKED", "reason": reason,
            "authoritative_gameplay_verdict": "UNKNOWN"}


def _apply(attempts: dict, receipt: dict) -> dict:
    key = (receipt["run_id"], receipt["execution_id"], receipt["attempt"])
    identity = (receipt["feature_id"], receipt["case_id"],
                receipt["definition_revision"])
    attempt = attempts.get(key)
    if attempt is None:
        attempt = {"identity": identity, "operations": {}}
        attempts[key] = attempt
    if attempt["identity"] != identity:
        return _blocked("ATTEMPT_DEFINITION_CONFLICT")
    operations = attempt["operations"]
    # Receipt IDs are unique within the whole attempt, not merely per operation.
    for operation_id, history in operations.items():
        for old in history:
            if old["receipt_id"] == receipt["receipt_id"]:
                if old == receipt:
                    return {"status": "NO_CHANGE", "reason": "EXACT_REPLAY",
                            "authoritative_gameplay_verdict": "UNKNOWN"}
                return _blocked("IDENTITY_DIGEST_CONFLICT")
            if operation_id == receipt["operation_id"] and (
                old["phase"] == receipt["phase"] == "TERMINAL"
            ):
                return _blocked("TERMINAL_DIGEST_CONFLICT")
    history = operations.setdefault(receipt["operation_id"], [])
    if history and history[-1]["phase"] == "TERMINAL":
        return _blocked("TERMINAL_IMMUTABLE")
    if any(old["evidence_digest"] == receipt["evidence_digest"] and
           old["phase"] == receipt["phase"] and
           old["operation_state"] == receipt["operation_state"]
           for old in history):
        return _blocked("DUPLICATE_DIGEST_DIFFERENT_RECEIPT")
    status = "FIRST_SEEN" if len(history) == 0 else (
        "PARTIAL_TO_TERMINAL" if receipt["phase"] == "TERMINAL" else "PARTIAL_UPDATED"
    )
    history.append(receipt)
    return {"status": status, "reason": "UNVERIFIED_OFFLINE_RECEIPT",
            "authoritative_gameplay_verdict": "UNKNOWN"}


class OfflineEvidenceLedger:
    """Session-local reconciliation. No DB, disk, network, or v1 importer writes."""

    def __init__(self) -> None:
        self._attempts: dict = {}
        self._lock = RLock()

    def ingest_many(self, receipts: list[dict]) -> dict:
        """Atomic in-memory batch: reject all changes if any receipt conflicts."""
        if not isinstance(receipts, list) or not 1 <= len(receipts) <= 100:
            return {"status": "BLOCKED", "reason": "INVALID_BATCH", "results": []}
        with self._lock:
            staged = deepcopy(self._attempts)
            results = []
            for raw in receipts:
                try:
                    receipt = _validate(raw)
                except (ValueError, TypeError, KeyError) as exc:
                    return {"status": "BLOCKED", "reason": str(exc), "results": []}
                verdict = _apply(staged, receipt)
                if verdict["status"] == "BLOCKED":
                    return {"status": "BLOCKED", "reason": verdict["reason"],
                            "results": []}
                results.append(verdict)
            self._attempts = staged
            return {"status": "ACCEPTED", "results": results}

    def ingest(self, receipt: dict) -> dict:
        batch = self.ingest_many([receipt])
        if batch["status"] == "BLOCKED":
            return _blocked(batch["reason"])
        return batch["results"][0]

    def snapshot(self, run_id: str, execution_id: str, attempt: int) -> dict | None:
        """Detached original receipts and classification; NEVER an approved PASS."""
        with self._lock:
            state = self._attempts.get((run_id, execution_id, attempt))
            if state is None:
                return None
            operations = {}
            for op_id, history in state["operations"].items():
                latest = history[-1]
                operations[op_id] = {
                    "receipts": deepcopy(history),
                    "phase": latest["phase"],
                    "operation_state": latest["operation_state"],
                    "evidence_complete_claim": latest["evidence_complete"],
                    "missing_artifacts": list(latest["missing_artifacts"]),
                    "reported_verdict": latest["reported_verdict"],
                    "authoritative_gameplay_verdict": "UNKNOWN",
                    "source_authenticated": False,
                    "oracle_approved": False,
                }
            return {"identity": dict(zip(
                        ("feature_id", "case_id", "definition_revision"),
                        state["identity"])),
                    "operations": operations, "authoritative_gameplay_verdict": "UNKNOWN",
                    "durable": False, "source_authenticated": False,
                    "v1_import_eligible": False}
