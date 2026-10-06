"""Fail-closed evidence policy for decoded FFXI search-server responses.

`search_response_decode` performs source-backed structural parsing after outbound cryptographic
validation. This module adds the semantic trust gate: source-fixed response constants must match,
and shared 0x82 party/linkshell responses must not contradict the exact predecessor request.
"""
from __future__ import annotations

import struct

from workbench.captures import search_response_decode


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def decode_validated_outbound(outbound_result: dict, predecessor_request: dict | None = None) -> dict:
    """Return structurally decoded response evidence with strict semantic promotion rules."""
    result = search_response_decode.decode_validated_outbound(outbound_result, predecessor_request)
    result["semantic_promotion_validated"] = False

    decrypted_hex = result.get("raw_decrypted_hex")
    if not result.get("validated_crypto") or not decrypted_hex:
        return result
    try:
        data = bytes.fromhex(decrypted_hex)
    except ValueError:
        return result

    packet_type = result.get("response_type")

    if packet_type == 0x88:
        # SearchCommentPacket is unusually strong evidence because current LSB fixes every one of
        # these structural constants in its packet constructor.
        mismatches = []
        if len(data) != 204:
            mismatches.append({"field": "wire_length", "expected": 204, "observed": len(data)})
        if len(data) > 0x08 and data[0x08] != 154:
            mismatches.append({"field": "data_size_low_byte", "offset": 0x08, "expected": 154, "observed": data[0x08]})
        if len(data) > 0x0A and data[0x0A] != 0x80:
            mismatches.append({"field": "server_final_flag", "offset": 0x0A, "expected": 0x80, "observed": data[0x0A]})
        if len(data) > 0x0E and data[0x0E] != 0x01:
            mismatches.append({"field": "record_count", "offset": 0x0E, "expected": 1, "observed": data[0x0E]})
        if len(data) >= 0x1E and _u16(data, 0x1C) != 124:
            mismatches.append({"field": "comment_length", "offset": 0x1C, "expected": 124, "observed": _u16(data, 0x1C)})
        if len(data) > 0x9A and data[0x9A] != 0:
            mismatches.append({"field": "comment_terminator", "offset": 0x9A, "expected": 0, "observed": data[0x9A]})

        if mismatches:
            result["decoded"] = False
            result["semantic_promotion_validated"] = False
            result["classification_certainty"] = "crypto_validated_source_layout_mismatch"
            result["fields"] = {}
            result["field_evidence"] = {}
            result.setdefault("diagnostics", []).append({
                "kind": "search_comment_source_layout_mismatch",
                "mismatches": mismatches,
            })
            return result

        if result.get("decoded"):
            result["semantic_promotion_validated"] = True
            result["classification_certainty"] = "verified_from_crypto_and_source_fixed_layout"
        return result

    if packet_type == 0x80:
        if result.get("decoded"):
            result["semantic_promotion_validated"] = True
        return result

    if packet_type != 0x82:
        return result

    entities = result.get("entities") or []
    payload_has_linkshell_rank = any(
        "linkshell_ranks" in (entity.get("fields") or {})
        for entity in entities
    )
    all_entities_fully_decoded = bool(entities) and all(entity.get("fully_decoded") for entity in entities)

    predecessor_family = None
    if predecessor_request and predecessor_request.get("validated") and predecessor_request.get("packet_type_name") == "GROUP_LIST":
        fields = predecessor_request.get("fields") or {}
        if fields.get("party_id") or fields.get("alliance_id"):
            predecessor_family = "party_list"
        elif fields.get("linkshell_id_1") or fields.get("linkshell_id_2"):
            predecessor_family = "linkshell_list"

    conflict = False
    if predecessor_family == "party_list" and payload_has_linkshell_rank:
        conflict = True
    elif predecessor_family == "linkshell_list" and all_entities_fully_decoded and not payload_has_linkshell_rank:
        conflict = True

    if conflict:
        result["decoded"] = False
        result["semantic_promotion_validated"] = False
        result["response_type_name"] = "party_or_linkshell_list"
        result["classification_certainty"] = "ambiguous_conflicting_predecessor_and_payload_structure"
        result.setdefault("diagnostics", []).append({
            "kind": "search_0x82_predecessor_structure_conflict",
            "predecessor_family": predecessor_family,
            "payload_has_linkshell_rank": payload_has_linkshell_rank,
            "entity_count": len(entities),
        })
        # Offset 0x0E differs in width between party and linkshell packet constructors. Once family
        # evidence conflicts, retain both observations instead of silently keeping one interpretation.
        if len(data) >= 0x10:
            fields = result.setdefault("fields", {})
            fields.pop("total_results", None)
            fields["total_results_u8"] = data[0x0E]
            fields["total_results_u16"] = _u16(data, 0x0E)
            result["field_evidence"] = {
                "total_results": {
                    "offset": 0x0E,
                    "length": "ambiguous_1_or_2",
                    "certainty": "ambiguous_conflicting_evidence",
                },
                "entities": {"offset": 0x18, "certainty": "verified_from_source"},
            }
        return result

    if predecessor_family and result.get("response_type_name") == predecessor_family and result.get("decoded"):
        result["semantic_promotion_validated"] = True
        result["classification_certainty"] = "verified_from_crypto_exact_predecessor_and_source_layout"
    elif result.get("response_type_name") == "linkshell_list" and payload_has_linkshell_rank and result.get("decoded"):
        result["semantic_promotion_validated"] = True
        result["classification_certainty"] = "structurally_inferred_from_source_unique_LinkshellRank_layout"
    # An otherwise well-formed 0x82 with no exact predecessor and no unique linkshell structure
    # remains deliberately ambiguous; structural entity fields stay available as evidence.
    return result
