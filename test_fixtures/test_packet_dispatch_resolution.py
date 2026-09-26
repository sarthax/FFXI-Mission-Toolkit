#!/usr/bin/env python3
from pathlib import Path
import tempfile

from packet_opcode_index import index_packet_db, index_server


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        packet_db=root/"packets.xml"
        src=root/"src"
        src.mkdir()
        server=src/"packet_system.cpp"
        packet_db.write_text('<packet opcode="0x02A" />\n',encoding="utf-8")
        server.write_text(
            'void SmallPacket0x02A() {}\n'
            'void init() {\n'
            '  PacketParser[0x02A] = &SmallPacket0x02A;\n'
            '}\n',
            encoding="utf-8",
        )
        ops=index_packet_db(packet_db)
        edges=index_server(root,ops)
        handled=[e for e in edges if e["relationship"]=="HANDLED_BY"]
        assert len(handled)==1,edges
        assert handled[0]["target_node"]=="cpp-symbol:SmallPacket0x02A",handled
        assert handled[0]["confidence"]=="VERIFIED",handled
        assert "PacketParser" in handled[0]["notes"][0],handled
    print("packet dispatch resolution self-test: PASS")


if __name__=="__main__":
    main()
