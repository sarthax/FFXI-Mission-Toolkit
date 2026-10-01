#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

from workbench.core.services import capture_integrity
from workbench.core.services.capture_related_evidence import item_identity_matches


def key(**values):
    return capture_integrity.canonical_row_key(values)


def main():
    con=sqlite3.connect(":memory:")
    con.row_factory=sqlite3.Row
    con.execute("""CREATE TABLE capture_structured_records (
        capture_id INTEGER, source_file TEXT, family TEXT, record_key TEXT,
        record_type TEXT, ts TEXT, zone TEXT, entity_id INTEGER, entity_name TEXT,
        item_id INTEGER, item_name TEXT, price INTEGER, payload_json TEXT
    )""")
    rows=[
        (1,"shop.db","shopstock_buy_db","1","stock",None,"Bastok",100,"Vendor A",500,"Potion",100,"{}"),
        (1,"craft.csv","crafttrack_csv","2","synthesis",None,"Bastok",None,None,500,"Potion",None,"{}"),
        (1,"price.log","pricelog_simple","3","price",None,"Bastok",None,None,500,"Potion",120,"{}"),
        (1,"other.csv","poitrack_db","4","poi",None,"Bastok",None,None,500,"Potion",None,"{}"),
        # Same display name, different item id: must not correlate.
        (1,"fake.csv","crafttrack_csv","5","synthesis",None,"Bastok",None,None,501,"Potion",None,"{}"),
    ]
    con.executemany("INSERT INTO capture_structured_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",rows)
    con.commit()

    anchor=key(source_file="shop.db",family="shopstock_buy_db",record_key="1")
    matches=item_identity_matches(con,1,"capture_structured_records",anchor)
    ids={(m["family"],m["row_key"]) for m in matches}
    assert ("crafttrack_csv",key(source_file="craft.csv",family="crafttrack_csv",record_key="2")) in ids,matches
    assert ("pricelog_simple",key(source_file="price.log",family="pricelog_simple",record_key="3")) in ids,matches
    assert ("poitrack_db",key(source_file="other.csv",family="poitrack_db",record_key="4")) in ids,matches
    assert all(m["item_id"]==500 for m in matches),matches
    assert not any(m["row_key"]==key(source_file="fake.csv",family="crafttrack_csv",record_key="5") for m in matches),matches
    assert any(m["relation"]=="crafting evidence for captured item" for m in matches),matches
    assert any(m["relation"]=="vendor/pricing evidence for captured item" for m in matches),matches

    # Key-item rows are a separate table/namespace and must never join here.
    assert item_identity_matches(con,1,"capture_ki_events",key(seq=1))==[]

    con.close()

    # Keep the deterministic chat/native-source relation on the registered core capture path.
    from test_capture_chat_related_evidence import main as chat_related_main
    assert chat_related_main() == 0

    print("Capture item Related Evidence runtime regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
