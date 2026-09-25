#!/usr/bin/env python3
from workbench.core.services.packet_identity import parse_opcode,canonical_opcode,packet_node_id

def main():
    cases=[(42,"0x02a"),("42","0x02a"),("0x02A","0x02a"),("02A","0x02a"),("002","0x002"),("ABC","0xabc")]
    for raw,expected in cases:
        assert canonical_opcode(raw)==expected,(raw,canonical_opcode(raw))
        assert packet_node_id(raw)=="packet:"+expected
    assert parse_opcode(-1) is None
    assert canonical_opcode("not-an-opcode") is None
    assert packet_node_id("") is None
    print("packet identity self-test: PASS")

if __name__=="__main__":
    main()
