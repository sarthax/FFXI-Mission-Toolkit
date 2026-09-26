"""Normalize observed runtime behavior for capture-driven reconstruction.

This layer is deliberately domain-neutral. It does not decide that an event ID is a
quest CSID, nor does it infer mission ownership from numeric identifiers. Upstream
capture/correlation code supplies only semantics supported by evidence.

ObservedTransition is the deterministic handoff between runtime/capture evidence and
implementation-gap/research tooling.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


CAPTURE_AWARE_GAP_STATUSES = {
    "IMPLEMENTED_AND_CAPTURE_OBSERVED",
    "PLACEHOLDER_WITH_RETAIL_BEHAVIOR_AVAILABLE",
    "PARTIAL_WITH_RETAIL_BEHAVIOR_AVAILABLE",
    "MISSING_WITH_RETAIL_BEHAVIOR_AVAILABLE",
    "OBSERVED_WITH_IMPLEMENTATION_UNKNOWN",
}


@dataclass(frozen=True)
class ObservedEffect:
    """One evidence-backed effect seen during an observed transition."""

    kind: str
    subject: str | None = None
    value: Any = None
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservedTransition:
    """A correlated behavior transition observed in one runtime capture.

    event_kind remains explicit because a numeric identifier alone is not a stable
    semantic identity. Use values such as MESSAGE_OR_EVENT_ID until deterministic
    evidence proves a narrower meaning such as CSID.
    """

    transition_id: str
    capture_id: str
    zone: str | None = None
    actor: str | None = None
    actor_id: str | None = None
    event_id: str | int | None = None
    event_kind: str = "MESSAGE_OR_EVENT_ID"
    owner_id: str | None = None
    trigger: str | None = None
    preconditions: tuple[str, ...] = ()
    effects: tuple[ObservedEffect, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    status: str = "OBSERVED"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaptureGapAssessment:
    transition_id: str
    implementation_status: str
    status: str
    has_capture_evidence: bool
    reason: str


def _norm_status(value: str | None) -> str:
    return str(value or "UNKNOWN").strip().upper().replace(" ", "_")


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def normalize_transition(
    *,
    transition_id: str,
    capture_id: str | int,
    zone: str | None = None,
    actor: str | None = None,
    actor_id: str | int | None = None,
    event_id: str | int | None = None,
    event_kind: str | None = None,
    owner_id: str | None = None,
    trigger: str | None = None,
    preconditions: Iterable[str] = (),
    effects: Iterable[ObservedEffect | dict[str, Any]] = (),
    evidence_ids: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
) -> ObservedTransition:
    """Build a normalized transition while preserving conservative semantics."""

    normalized_effects: list[ObservedEffect] = []
    for effect in effects:
        if isinstance(effect, ObservedEffect):
            normalized_effects.append(effect)
            continue
        if not isinstance(effect, dict) or not effect.get("kind"):
            raise ValueError("Each observed effect must provide a non-empty kind")
        normalized_effects.append(
            ObservedEffect(
                kind=str(effect["kind"]).strip().upper(),
                subject=None if effect.get("subject") is None else str(effect["subject"]),
                value=effect.get("value"),
                evidence_ids=_dedupe(effect.get("evidence_ids") or ()),
                metadata=dict(effect.get("metadata") or {}),
            )
        )

    if not str(transition_id).strip():
        raise ValueError("transition_id is required")
    if not str(capture_id).strip():
        raise ValueError("capture_id is required")

    return ObservedTransition(
        transition_id=str(transition_id).strip(),
        capture_id=str(capture_id).strip(),
        zone=zone,
        actor=actor,
        actor_id=None if actor_id is None else str(actor_id),
        event_id=event_id,
        event_kind=_norm_status(event_kind or "MESSAGE_OR_EVENT_ID"),
        owner_id=owner_id,
        trigger=trigger,
        preconditions=_dedupe(preconditions),
        effects=tuple(normalized_effects),
        evidence_ids=_dedupe(evidence_ids),
        metadata=dict(metadata or {}),
    )


def assess_capture_gap(
    transition: ObservedTransition,
    implementation_status: str | None,
) -> CaptureGapAssessment:
    """Classify implementation state relative to an observed Retail transition.

    This function does not decide whether a capture is authoritative enough to promote
    a Finding. It only preserves the stronger semantic distinction that observed Retail
    behavior exists for a missing/partial/placeholder implementation.
    """

    impl = _norm_status(implementation_status)
    has_capture = bool(transition.evidence_ids) or any(
        effect.evidence_ids for effect in transition.effects
    )

    if not has_capture:
        return CaptureGapAssessment(
            transition_id=transition.transition_id,
            implementation_status=impl,
            status="OBSERVED_TRANSITION_WITHOUT_EVIDENCE_LINK",
            has_capture_evidence=False,
            reason="Transition record has no linked capture evidence IDs.",
        )

    if impl in {"IMPLEMENTED", "VERIFIED", "COMPLETE", "PRESENT"}:
        status = "IMPLEMENTED_AND_CAPTURE_OBSERVED"
        reason = "Implementation is present and Retail behavior is observed."
    elif impl in {"PLACEHOLDER", "STUB"}:
        status = "PLACEHOLDER_WITH_RETAIL_BEHAVIOR_AVAILABLE"
        reason = "Implementation is a placeholder while Retail behavior is available as reconstruction evidence."
    elif impl in {"PARTIAL", "PARTIALLY_IMPLEMENTED", "INCOMPLETE"}:
        status = "PARTIAL_WITH_RETAIL_BEHAVIOR_AVAILABLE"
        reason = "Implementation is partial while Retail behavior is available as reconstruction evidence."
    elif impl in {"MISSING", "NOT_IMPLEMENTED", "ABSENT"}:
        status = "MISSING_WITH_RETAIL_BEHAVIOR_AVAILABLE"
        reason = "Implementation is missing while Retail behavior is available as reconstruction evidence."
    else:
        status = "OBSERVED_WITH_IMPLEMENTATION_UNKNOWN"
        reason = "Retail behavior is observed but implementation status is not yet resolved."

    return CaptureGapAssessment(
        transition_id=transition.transition_id,
        implementation_status=impl,
        status=status,
        has_capture_evidence=True,
        reason=reason,
    )


def transition_dict(transition: ObservedTransition) -> dict[str, Any]:
    """Return a JSON-serializable representation for graph/research adapters."""

    return asdict(transition)


def assessment_dict(assessment: CaptureGapAssessment) -> dict[str, Any]:
    return asdict(assessment)
