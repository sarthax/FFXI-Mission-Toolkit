import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"tools/scenario_typed_library_contract_1409.py"
s=importlib.util.spec_from_file_location("typed",P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def make(row="talk_to_npc",val=42,exp=True):
 return {"row_id":row,"phase1_head":m.PHASE1,"native_head":m.NATIVE,"do":{m.ROWS[row][0]:val},
         "expect":{m.ROWS[row][1]:exp},"execution_enabled":False,
         "publish_enabled":False,"oracle_status":"UNAPPROVED","verdict":"UNKNOWN"}
def main():
 candidates=[make(),make("navigate_near",[1.0,2.0],4.2),make("wait_for_state",0,235),
             make("recover_hp",50,90),make("accept_party_invite",True,0),
             make("advance_event",0,123)]
 for a in candidates:
  v=m.validate(a);assert v["admission"]=="BLOCKED" and v["independent_verdict"]=="UNKNOWN"
  assert v["native_shape_recognized"] and not v["execution_enabled"]
 for changes in ({"do":{"talk_npc":-1}},{"do":{"talk_npc":True}},
                 {"do":{"talk_npc":4294967296}},{"do":{"talk_npc":1,"say":"GM"}},
                 {"expect":{"event_active":"true"}},{"expect":{"event_active":True,"event_id":2}},
                 {"execution_enabled":True},{"publish_enabled":True},{"verdict":"PASS"},
                 {"oracle_status":"APPROVED"},{"native_head":"0"*40},
                 {"phase1_head":None},{"row_id":"warp_target"}):
  q=make();q.update(changes);assert "native_shape_recognized" not in m.validate(q),changes
 for val in ([float("nan"),2],[float("inf"),3],[True,3],[1],{"coords":[1,2],"timeout_ms":0}):
  assert "native_shape_recognized" not in m.validate(make("navigate_near",val,1))
 for bad in (None,[],{"do":{}},42):
  assert m.validate(bad)["admission"]=="BLOCKED"
 for name in ("read_inventory","read_progression"):
  assert m.validate({"row_id":name,"phase1_head":m.PHASE1,"native_head":m.NATIVE,
   "execution_enabled":False,"publish_enabled":False,"oracle_status":"UNAPPROVED","verdict":"UNKNOWN"})["reason"].startswith("TOOLKIT_READBACK_ONLY")
 assert m.validate_batch([make(),make()])[0]["reason"]=="DUPLICATE_ROW_ID"
 assert m.validate_batch([None])[0]["admission"]=="BLOCKED"
 print("typed scenario #1409: source pin + positive shape + unsafe authority negative PASS")
if __name__=="__main__":main()
