"""Additive, metadata-only v2 contract for canonical v1 scenario specifications.

Syntactic validation is NOT source authentication, permission approval,
capability registration, or execution authorization. Existing v1 evaluators,
importers, runner gates and viewer logic remain unchanged.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath

_SOURCE_TYPES = frozenset({"dsp_source", "client_dat", "capture_observation",
                           "toolkit_code", "documentation"})
_PARAM_KINDS = frozenset({"item", "key_item", "npc", "mob", "zone", "catalog"})
_BINDING_STATES = frozenset({"unresolved", "candidate", "ambiguous",
                             "independently_source_verified"})
_ORACLE_TYPES = frozenset({"unknown", "source_rule", "source_literal", "reviewed_manual"})
_CONFIDENCE = frozenset({"unknown", "candidate", "source_cited"})
_CAPABILITIES = frozenset({"unassigned", "read_only_observation",
                           "server_readback_candidate", "gm_diagnostic_candidate",
                           "client_action_candidate", "gm_action_candidate",
                           "manual_checkpoint"})
_OPERATION_CLASSES = frozenset({"unknown", "read_only", "mutating"})
_PERMISSIONS = frozenset({"operator_approval", "disposable_character",
                          "server_read_grant", "client_control",
                          "gm_privilege", "cleanup_verification"})
_SHA40 = re.compile(r"[0-9a-fA-F]{40}\Z")
_SHA64 = re.compile(r"[0-9a-fA-F]{64}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_READBACK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.: -]{0,119}\Z")
_FIELDS = frozenset({"contract_version", "sources", "parameters", "oracles",
                     "step_requirements", "fingerprints"})
# Explicit case/step source attribution is an OPTIONAL metadata-only extension.
# Existing Contract v2 objects without this key retain exactly their old shape.
_OPTIONAL_FIELDS = frozenset({"source_associations"})


def _object(value: object, keys: set[str] | frozenset[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("invalid v2 " + label + " fields")
    return value


def _list(value: object, limit: int, label: str) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError("invalid v2 " + label + " list")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid v2 " + label)
    return value


def _sha(value: object, bits: int, label: str) -> None:
    if value is not None and (not isinstance(value, str) or
                              not (_SHA40 if bits == 40 else _SHA64).fullmatch(value)):
        raise ValueError("invalid v2 " + label)


def _unique_refs(value: object, known: set[str], label: str, *, limit: int = 20) -> list:
    refs = _list(value, limit, label)
    if any(not isinstance(ref, str) or ref not in known for ref in refs) or len(refs) != len(set(refs)):
        raise ValueError("unknown, duplicate, or invalid v2 " + label + " source reference")
    return refs


def _validate_sources(items: object) -> dict[str, dict]:
    sources = {}
    for src in _list(items, 20, "sources"):
        _object(src, {"ref", "repository", "path", "line_start", "line_end",
                      "revision", "classification", "sha256"}, "source")
        key = _identifier(src["ref"], "source ref")
        if key in sources:
            raise ValueError("duplicate v2 source ref")
        repo = src["repository"]
        if (not isinstance(repo, str) or not _REPOSITORY.fullmatch(repo) or
            any(segment in ("", ".", "..") for segment in repo.split("/"))):
            raise ValueError("invalid v2 repository")
        path = src["path"]
        if (not isinstance(path, str) or not 1 <= len(path) <= 300 or
            "\\" in path or ":" in path or path.startswith("/") or
            not PurePosixPath(path).parts or
            any(segment in ("", ".", "..") for segment in path.split("/"))):
            raise ValueError("invalid v2 source path")
        lo, hi = src["line_start"], src["line_end"]
        if not (lo is None and hi is None) and not (
            type(lo) is int and type(hi) is int and 1 <= lo <= hi <= 10_000_000
            and hi - lo <= 1000
        ):
            raise ValueError("invalid v2 line span")
        if not isinstance(src["classification"], str) or src["classification"] not in _SOURCE_TYPES:
            raise ValueError("invalid v2 source classification")
        _sha(src["revision"], 40, "source revision")
        _sha(src["sha256"], 64, "source SHA-256")
        sources[key] = src
    return sources


def _pinned_source(refs: list[str], sources: dict[str, dict],
                   classes: set[str] | frozenset[str]) -> bool:
    return any(sources[r]["classification"] in classes and sources[r]["revision"]
               and sources[r]["sha256"] for r in refs)


def _validate_parameters(items: object, sources: dict[str, dict]) -> None:
    names = set()
    for param in _list(items, 30, "parameters"):
        _object(param, {"name", "kind", "identity", "namespace", "zone_id",
                        "binding_state", "source_refs"}, "parameter")
        name = _identifier(param["name"], "parameter name")
        if name in names:
            raise ValueError("duplicate v2 parameter")
        names.add(name)
        if (not isinstance(param["kind"], str) or param["kind"] not in _PARAM_KINDS or
            not isinstance(param["binding_state"], str) or param["binding_state"] not in _BINDING_STATES):
            raise ValueError("unsupported v2 identity kind or binding state")
        identity = param["identity"]
        if identity is not None and not (
            type(identity) is int and 0 <= identity <= 2**32-1 or
            isinstance(identity, str) and 1 <= len(identity) <= 120 and
            all(ch.isalnum() or ch in "_:-." for ch in identity)
        ):
            raise ValueError("invalid v2 identity")
        ns = param["namespace"]
        if ns is not None:
            _identifier(ns, "catalog namespace")
        zone_id = param["zone_id"]
        if zone_id is not None and not (type(zone_id) is int and 0 <= zone_id <= 2**32-1):
            raise ValueError("invalid v2 zone scope")
        refs = _unique_refs(param["source_refs"], set(sources), "parameter")
        if param["binding_state"] == "unresolved" and identity is not None:
            raise ValueError("unresolved v2 binding cannot supply an identity")
        if param["binding_state"] == "ambiguous" and identity is not None:
            raise ValueError("ambiguous v2 binding cannot select one identity")
        if param["binding_state"] == "independently_source_verified":
            if identity is None or ns is None or not _pinned_source(
                refs, sources, _SOURCE_TYPES - {"capture_observation", "documentation"}
            ):
                raise ValueError("source-verified v2 binding lacks pinned non-observation source")
            if param["kind"] in {"npc", "mob"} and zone_id is None:
                raise ValueError("source-verified NPC/mob binding requires zone scope")


def _validate_oracles(items: object, sources: dict[str, dict], assertions: set[str]) -> None:
    names = set()
    for oracle in _list(items, 30, "oracles"):
        _object(oracle, {"assertion_id", "oracle_type", "source_refs", "confidence"}, "oracle")
        key = oracle["assertion_id"]
        if not isinstance(key, str) or key not in assertions or key in names:
            raise ValueError("invalid, duplicate, or unknown v2 oracle assertion")
        names.add(key)
        kind, confidence = oracle["oracle_type"], oracle["confidence"]
        if (not isinstance(kind, str) or kind not in _ORACLE_TYPES or
            not isinstance(confidence, str) or confidence not in _CONFIDENCE):
            raise ValueError("unsupported v2 oracle kind/confidence")
        refs = _unique_refs(oracle["source_refs"], set(sources), "oracle")
        if kind == "unknown":
            if refs or confidence != "unknown":
                raise ValueError("unknown v2 oracle cannot claim source certainty")
        if kind in {"source_rule", "source_literal"} and not any(
            sources[r]["classification"] in {"dsp_source", "toolkit_code"} for r in refs
        ):
            raise ValueError("source-backed v2 oracle requires normative code source, not only captured observations")
        if confidence == "source_cited" and not (
            kind in {"source_rule", "source_literal"} and
            _pinned_source(refs, sources, {"dsp_source", "toolkit_code"})
        ):
            raise ValueError("source-cited v2 oracle requires pinned normative source")


def _validate_requirements(items: object, steps: set[str]) -> None:
    used = set()
    for req in _list(items, 100, "step requirements"):
        _object(req, {"step_id", "capability", "operation_class", "required_permissions",
                      "required_readbacks", "approval_required", "execution_gate"},
                "step requirement")
        key = req["step_id"]
        if not isinstance(key, str) or key not in steps or key in used:
            raise ValueError("unknown or duplicate v2 step reference")
        used.add(key)
        if (not isinstance(req["capability"], str) or req["capability"] not in _CAPABILITIES or
            not isinstance(req["operation_class"], str) or req["operation_class"] not in _OPERATION_CLASSES):
            raise ValueError("unsupported or prohibited v2 capability")
        if req["execution_gate"] != "blocked" or type(req["approval_required"]) is not bool:
            raise ValueError("v2 metadata cannot authorize execution")
        permissions = _list(req["required_permissions"], 10, "permissions")
        if any(not isinstance(x, str) or x not in _PERMISSIONS for x in permissions) or len(permissions) != len(set(permissions)):
            raise ValueError("unsupported v2 permission")
        readbacks = _list(req["required_readbacks"], 20, "readbacks")
        if any(not isinstance(x, str) or not _READBACK.fullmatch(x) for x in readbacks) or len(readbacks) != len(set(readbacks)):
            raise ValueError("invalid or duplicate v2 readback")
        capability = req["capability"]
        if capability in {"gm_diagnostic_candidate", "gm_action_candidate", "client_action_candidate"} and req["operation_class"] == "read_only":
            raise ValueError("unverified GM/client action cannot assert read-only safety")
        if req["operation_class"] == "mutating":
            if not req["approval_required"] or not {
                "operator_approval", "disposable_character", "cleanup_verification"
            }.issubset(permissions):
                raise ValueError("mutating v2 step requires approval, isolation and cleanup")
        if req["operation_class"] == "unknown" and not req["approval_required"] and capability in {
            "gm_diagnostic_candidate", "gm_action_candidate", "client_action_candidate"
        }:
            raise ValueError("unknown action safety requires operator review")


def _validate_source_associations(
    items: object, sources: dict[str, dict], steps: set[str],
) -> None:
    """Validate explicit case/step *citations*, not evidence or oracle approval.

    A source declaration by itself never implies a relationship to a step.
    Repeated target rows and source revisions at one scoped target are
    ambiguous; require one explicit, unambiguous author-reviewed association.
    """
    seen_targets = set()
    for association in _list(items, 100, "source associations"):
        _object(association, {"scope", "target_id", "source_refs"},
                "source association")
        scope, target_id = association["scope"], association["target_id"]
        if scope == "case":
            if target_id is not None:
                raise ValueError("case source association must use null target_id")
        elif scope == "step":
            if not isinstance(target_id, str) or target_id not in steps:
                raise ValueError("source association references unknown step")
        else:
            raise ValueError("unsupported source association scope")
        target = (scope, target_id)
        if target in seen_targets:
            raise ValueError("duplicate or ambiguous source association target")
        seen_targets.add(target)
        refs = _unique_refs(association["source_refs"], set(sources),
                            "association")
        if not refs:
            raise ValueError("empty source association leaves provenance unknown")
        file_pins = {}
        for ref in refs:
            src = sources[ref]
            location = (src["repository"], src["path"])
            pins = (src["revision"], src["sha256"])
            if location in file_pins and file_pins[location] != pins:
                raise ValueError("conflicting source revisions or digests for associated file")
            file_pins[location] = pins


def base_spec_sha256(spec: dict) -> str:
    """Deterministic fingerprint of *v1* spec fields, omitting recursive v2 and the automatable ``native_steps``.

    ``native_steps`` is descriptive draft data like ``contract_v2``; editing it must not invalidate recorded v2
    fingerprints. Specifications without it hash exactly as before.
    """
    if not isinstance(spec, dict):
        raise ValueError("invalid scenario specification")
    core = {key: value for key, value in spec.items() if key not in ("contract_v2", "native_steps")}
    raw = json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_contract_v2(spec: dict) -> None:
    """Validate optional v2 *claims*; do not convert them into trusted facts."""
    value = spec.get("contract_v2")
    if value is None:
        raise ValueError("null v2 namespace is unsupported; omit it for v1")
    if (not isinstance(value, dict) or not _FIELDS.issubset(value) or
            set(value) - (_FIELDS | _OPTIONAL_FIELDS)):
        raise ValueError("invalid v2 contract fields")
    if type(value["contract_version"]) is not int or value["contract_version"] != 2:
        raise ValueError("unsupported v2 metadata contract version")
    sources = _validate_sources(value["sources"])
    _validate_parameters(value["parameters"], sources)
    _validate_oracles(value["oracles"], sources, {
        item["id"] for item in spec["assertions"]
    })
    steps = {item["id"] for item in spec.get("steps", [])}
    _validate_requirements(value["step_requirements"], steps)
    if "source_associations" in value:
        _validate_source_associations(value["source_associations"], sources, steps)
    fingerprints = _object(value["fingerprints"], {
        "base_spec_sha256", "dsp_commit", "headless_commit", "toolkit_commit"
    }, "fingerprints")
    _sha(fingerprints["base_spec_sha256"], 64, "base specification SHA-256")
    for name in ("dsp_commit", "headless_commit", "toolkit_commit"):
        _sha(fingerprints[name], 40, name)


def source_attribution_report(spec: dict) -> dict:
    """Pure read-only explicit association display; absent link is UNKNOWN.

    Source declarations, staged citations and oracle/parameter links never
    automatically become per-step source attribution. No trust or execution
    permissions are granted by this report.
    """
    from .test_specifications import validate_spec

    validate_spec(spec)
    meta = spec.get("contract_v2") or {}
    associations = meta.get("source_associations", [])
    by_step = {
        step["id"]: {"state": "UNKNOWN", "source_refs": []}
        for step in spec.get("steps", [])
    }
    case = {"state": "UNKNOWN", "source_refs": []}
    for association in associations:
        item = {"state": "EXPLICIT_CITATION_CLAIM",
                "source_refs": list(association["source_refs"])}
        if association["scope"] == "case":
            case = item
        else:
            by_step[association["target_id"]] = item
    return {
        "case": case, "steps": by_step,
        "independent_verification": "NOT_ESTABLISHED",
        "execution_enabled": False,
        "oracle_approval": "NOT_ESTABLISHED",
    }


def compatibility_report(
    spec: dict,
    observed_versions: dict | None = None,
    *,
    observed_sources: dict | None = None,
) -> dict:
    """Fail-closed read-only revision comparison, not authority or dispatch."""
    from .test_specifications import validate_spec

    validate_spec(spec)
    metadata = spec.get("contract_v2")
    if metadata is None:
        return {"state": "UNKNOWN", "reasons": ["legacy v1 has no contract_v2 fingerprints"],
                "execution_enabled": False, "independent_verification": "NOT_ESTABLISHED"}
    pins = metadata["fingerprints"]
    reasons = []
    mismatch = []
    declared = pins["base_spec_sha256"]
    if declared is None:
        reasons.append("base specification SHA-256 missing")
    elif declared.lower() != base_spec_sha256(spec):
        mismatch.append("base specification SHA-256 mismatch")
    if observed_versions is None:
        reasons.append("runtime engine versions not independently supplied")
    else:
        if not isinstance(observed_versions, dict) or set(observed_versions) != {
            "dsp_commit", "headless_commit", "toolkit_commit"
        }:
            raise ValueError("observed versions require exact three engine commits")
        for key in ("dsp_commit", "headless_commit", "toolkit_commit"):
            claimed, observed = pins[key], observed_versions[key]
            _sha(observed, 40, "observed " + key)
            if not claimed or not observed:
                reasons.append(key + " unavailable")
            elif claimed.lower() != observed.lower():
                mismatch.append(key + " mismatch")
    # The source metadata contains only a claimed digest. Independent local
    # verification MUST be supplied by a caller that has rehashed exact source
    # bytes and checked the repository/revision. This pure helper never opens
    # paths, downloads sources or upgrades oracle/binding confidence.
    sources = {item["ref"]: item for item in metadata["sources"]}
    for ref, src in sources.items():
        if not src["revision"] or not src["sha256"]:
            reasons.append("source " + ref + " revision/content digest unpinned")
    if observed_sources is None:
        if sources:
            reasons.append("independently rehashed source fingerprints unavailable")
    else:
        if not isinstance(observed_sources, dict) or set(observed_sources) - set(sources):
            raise ValueError("observed source fingerprints contain unrecognized refs")
        for ref, src in sources.items():
            expected_revision, expected_hash = src["revision"], src["sha256"]
            if ref not in observed_sources:
                reasons.append("source " + ref + " rehashed bytes not supplied")
                continue
            evidence = observed_sources[ref]
            if not isinstance(evidence, dict) or set(evidence) != {"revision", "sha256"}:
                raise ValueError("observed source requires exact revision and sha256")
            current_rev, current_sha = evidence["revision"], evidence["sha256"]
            _sha(current_rev, 40, "observed source revision")
            _sha(current_sha, 64, "observed source SHA-256")
            if current_rev is None or current_sha is None:
                reasons.append("source " + ref + " independent revision/hash unavailable")
            if expected_revision and current_rev and expected_revision.lower() != current_rev.lower():
                mismatch.append("source " + ref + " revision mismatch")
            if expected_hash and current_sha and expected_hash.lower() != current_sha.lower():
                mismatch.append("source " + ref + " content SHA-256 mismatch")
    state = "BLOCKED" if mismatch else "UNKNOWN" if reasons else "MATCHED_PINNED_ONLY"
    return {"state": state, "reasons": mismatch + reasons,
            "execution_enabled": False, "independent_verification": "NOT_ESTABLISHED"}


def serialize_spec(spec: dict) -> str:
    """Lossless deterministic JSON within the existing draft size limit."""
    from .test_specifications import validate_spec

    validate_spec(spec)
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # spec_drafts.save_draft currently persists JSON with the Python default
    # ensure_ascii=True. Unicode escapes can nearly double encoded size, so
    # using only the compact UTF-8 length here would falsely promise a draft
    # can be saved under the existing 32 KiB operator-authenticated limit.
    storage_payload = json.dumps(spec, sort_keys=True, ensure_ascii=True,
                                 separators=(",", ":"), allow_nan=False)
    if max(len(payload.encode("utf-8")), len(storage_payload.encode("utf-8"))) > 32768:
        raise ValueError("scenario draft exceeds existing 32KiB limit")
    return payload


def deserialize_spec(payload: str) -> dict:
    """Fail-closed loader; duplicate JSON keys must not erase provenance."""
    from .test_specifications import validate_spec

    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 32768:
        raise ValueError("invalid or oversized serialized scenario")

    def pairs(items: list[tuple[str, object]]) -> dict:
        value = {}
        for key, content in items:
            if key in value:
                raise ValueError("duplicate JSON key in scenario")
            value[key] = content
        return value

    try:
        doc = json.loads(payload, object_pairs_hook=pairs,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("invalid serialized scenario JSON") from exc
    # Match the existing draft-store wire format limit after parsing as well:
    # a compact Unicode JSON document may expand when save_draft escapes it.
    serialize_spec(doc)
    return doc
