"""Untrusted, offline #1208 declared-test-intent -> review-only Given/When/Then preview.

Not a native Headless scenario, oracle, catalog publisher, source verification, or execution.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
PTR = re.compile(r"features\[id=([A-Za-z0-9_-]+)\]\.cases\[id=([A-Za-z0-9_-]+)\]\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
SOURCE = "data/testing/feature_test_readiness.json"
ALLOWED = {"positive", "negative", "boundary", "persistence", "recovery"}
REQUIRED_FLAGS = {"context_only":True,"design_only":True,"review_required":True,
                  "auto_populate_allowed":False,"auto_save_allowed":False,"execution_enabled":False}
def preview(context: object) -> dict:
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if context.get("contract") != "coverage_behavior_reference_v1":
        raise ValueError("unsupported source contract")
    if any(type(context.get(k)) is not bool or context[k] != v for k,v in REQUIRED_FLAGS.items()):
        raise ValueError("context authority flags invalid")
    for k in ("feature_id","behavior_ref"):
        if not isinstance(context.get(k),str) or not REF.fullmatch(context[k]):
            raise ValueError("invalid declared source identity")
    if context["feature_id"] == context["behavior_ref"]:
        raise ValueError("ambiguous duplicate feature/behavior identity")
    label=context.get("label")
    if not isinstance(label,str) or not 1<=len(label.strip())<=240:
        raise ValueError("invalid label")
    if not isinstance(context.get("category"),str) or context["category"] not in ALLOWED:
        raise ValueError("unsupported intent category")
    pointer=context.get("source_pointer")
    match=PTR.fullmatch(pointer) if isinstance(pointer,str) else None
    if not match or match.groups()!=(context["feature_id"],context["behavior_ref"]):
        raise ValueError("invalid or mismatched source pointer")
    if context.get("source")!=SOURCE or context.get("reference_kind")!="declared_test_case_intent_not_behavior_trace_identity":
        raise ValueError("source claim not recognized")
    rev=context.get("source_revision")
    if not isinstance(rev,str) or (rev!="UNPINNED" and not SHA.fullmatch(rev)):
        raise ValueError("missing/invalid/conflicting source revision")
    if context.get("expected_oracle")!="UNKNOWN" or context.get("proposed_case_id") is not None:
        raise ValueError("forged authority or case ID")
    for k in ("assertions","observations","capability_bindings"):
        if type(context.get(k)) is not list or context[k]:
            raise ValueError("unsupported capability or invented assertion")
    return {
      "schema":"untrusted-feature-intent-preview/1","state":"REVIEW_REQUIRED","executable":False,
      "save_allowed":False,"publish_allowed":False,"canonical":False,
      "source":{"repository":"sarthax/FFXI-Mission-Toolkit","file":SOURCE,"pointer":pointer,"revision":rev,
                "identity_kind":"DECLARED_TEST_INTENT_NOT_VERIFIED_BEHAVIOR"},
      "feature_ref":context["feature_id"],"behavior_ref":context["behavior_ref"],
      "scenario_id":None,"title":label.strip(),
      "given":"UNKNOWN — operator must specify test environment, character and prerequisites",
      "when":"PROPOSED — review declared intent: "+label.strip(),
      "then":"UNKNOWN — expected effects and independently approved oracle not established",
      "required_fixture":"UNKNOWN","action_capability":"BLOCKED_UNVERIFIED",
      "oracle":"UNKNOWN","verdict":"NOT_RUN","notes":["No source identity or FFXI IDs inferred",
            "No automatic action, observation or assertion generation",
            "Manual review required before any versioned specification"],
    }
def preview_file(path: str|Path) -> dict:
    # Explicit offline local input only. No network, API or database access.
    return preview(json.loads(Path(path).read_text(encoding="utf-8")))
