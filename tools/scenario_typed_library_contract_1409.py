"""Noncanonical #1409 phase-2 typed proposal guard; never dispatches game actions."""
from __future__ import annotations
import math, re, struct
PHASE1="f784bd6f22f57e707d937bd9d63ab98bd34700db"
NATIVE="159a5b9d4b4e43397bd509a816a7241a97511319"
# Narrow shape-level subset verified by reading pinned native schemas; does not attest runtime.
ROWS={
"navigate_near":("walk_to","x_near"),"talk_to_npc":("talk_npc","event_active"),
"inspect_npc":("examine_npc","event_id"),"advance_event":("event_update","event_param0"),
"finish_event":("event_finish","event_active"),"wait_for_state":("wait_ms","zone"),
"recover_hp":("rest_hp","hpp"),"invite_party":("invite","party_members_gt"),
"accept_party_invite":("accept_invite","party_members_gt"),"engage_target":("engage","entities_gt"),
"read_inventory":(None,None),"read_progression":(None,None)}
IDS=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
def blocked(reason, row=None):
    return {"schema":"typed-library-proposal-validation/1","state":"REVIEW_REQUIRED","admission":"BLOCKED",
     "independent_verdict":"UNKNOWN","oracle":"UNAPPROVED","execution_enabled":False,
     "publish_enabled":False,"native_runtime_verified":False,"reason":reason,"row_id":row}
def integer(v,low=0,high=4294967295):
    return type(v) is int and low<=v<=high
def finite(v):
    return type(v) in (int,float) and math.isfinite(v)
def finite_float32(v):
    """Mirror native TryGetSingle plus float.IsFinite (not Python double finiteness)."""
    if not finite(v):
        return False
    try:
        return math.isfinite(struct.unpack("!f", struct.pack("!f", v))[0])
    except (OverflowError, ValueError, struct.error):
        return False

def valid_action(key,value):
    if key=="walk_to":
        if isinstance(value,list): return len(value) in (2,3) and all(finite_float32(n) for n in value)
        if isinstance(value,dict):
            return set(value)<= {"coords","timeout_ms","stall_ms"} and "coords" in value and valid_action("walk_to",value["coords"]) and all(integer(v,1,3600000) for k,v in value.items() if k!="coords")
        return False
    if key in {"talk_npc","examine_npc","event_update","event_finish","invite","engage"}:return integer(value)
    if key=="wait_ms":return integer(value,0,3600000)
    if key=="rest_hp":return integer(value,1,100)
    if key=="accept_invite":return type(value) is bool
    return False
def valid_expect(key,value):
    if key in {"x_near"}:return finite(value)
    if key=="event_active":return type(value) is bool
    if key in {"event_id","event_param0","zone","hpp","party_members_gt","entities_gt"}:return integer(value,0,2**53)
    return False
def validate(candidate):
    if not isinstance(candidate,dict):return blocked("MALFORMED_CANDIDATE")
    row=candidate.get("row_id")
    if not isinstance(row,str) or not IDS.fullmatch(row) or row not in ROWS:return blocked("UNKNOWN_OR_FORGED_ROW")
    if candidate.get("phase1_head")!=PHASE1 or candidate.get("native_head")!=NATIVE:
        return blocked("MISSING_OR_CONFLICTING_SOURCE_REVISION",row)
    if any(candidate.get(k) is not False for k in ("execution_enabled","publish_enabled")) or candidate.get("oracle_status")!="UNAPPROVED" or candidate.get("verdict")!="UNKNOWN":
        return blocked("FORGED_AUTHORITY",row)
    native,expect=ROWS[row]
    if native is None:
        return blocked("TOOLKIT_READBACK_ONLY__NO_AUTHORIZED_COLLECTOR_OR_ORACLE",row)
    actions=candidate.get("do");expects=candidate.get("expect")
    if not isinstance(actions,dict) or set(actions)!={native}:
        return blocked("MISSING_UNSUPPORTED_OR_AMBIGUOUS_ACTION",row)
    if not isinstance(expects,dict) or set(expects)!={expect}:
        return blocked("MISSING_UNSUPPORTED_OR_AMBIGUOUS_EXPECTATION",row)
    if not valid_action(native,actions[native]):return blocked("INVALID_NATIVE_PARAMETER_SHAPE",row)
    if not valid_expect(expect,expects[expect]):return blocked("INVALID_EXPECTATION_SHAPE",row)
    return {**blocked("SYNTAX_ONLY__COLLECTOR_AND_ORACLE_NOT_APPROVED",row),
            "native_shape_recognized":True,"parameters_source":"pinned-native-schema-shape-only",
            "readback_available":"NOT_ESTABLISHED"}
def validate_batch(obj):
    if not isinstance(obj,list) or not obj:return [blocked("MALFORMED_BATCH")]
    if len(obj)>100:return [blocked("OVERSIZED_BATCH")]
    seen=set();out=[]
    for row in obj:
        ident=row.get("row_id") if isinstance(row,dict) else None
        if ident in seen:return [blocked("DUPLICATE_ROW_ID")]
        seen.add(ident)
        out.append(validate(row))
    return out
