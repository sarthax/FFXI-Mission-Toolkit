"""Protect read-only Wiki -> Feature Trace navigation and its evidence boundaries."""
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    wiki=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert 'if len(identities)==1:' in host
    assert 'exact_node=f"catalog:{table}:{key}"' in host
    assert 'confirmed_node=feature_trace.node_info(con,exact_node,con)' in host
    assert 'if confirmed_node and str(confirmed_node.get("node_id"))==exact_node:' in host
    assert 'link["entity_target"]["trace_node"]=exact_node' in host
    assert '{% if link.entity_target.trace_node %}' in wiki
    assert '/features/trace?q={{ link.entity_target.trace_node|urlencode }}' in wiki
    assert '/features/trace?q={{ link.entity_target.trace_query|urlencode }}' in wiki
    assert 'search is not a verified mapping' in wiki
    assert 'link["entity_resolution"]="NOT_APPLICABLE"' in host
    print("Wiki Feature Trace handoff contract: PASS")

if __name__=="__main__":
    main()
