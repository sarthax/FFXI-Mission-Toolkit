from workbench.domains.assault_shared_priority import prioritize

def dep(section_id, scope="direct", port="unreviewed", validation="unreviewed"):
    return dict(section_id=section_id,title=f"Topic {section_id}",scope=scope,port=port,validation=validation)

def test_dedup_and_scope():
    rows=prioritize([
        dict(number=1,zone="A",shared_dependencies=[dep(1,"direct + zone")]),
        dict(number=2,zone="A",shared_dependencies=[dep(1,"zone")]),
        dict(number=3,zone="B",shared_dependencies=[dep(2)]),
    ])
    assert rows[0]["section_id"]==1
    assert rows[0]["affected_missions"]==2
    assert rows[0]["explicit_missions"]==1
    assert rows[0]["zone_scoped_missions"]==2
    assert rows[0]["affected_zones"]==["A"]

def test_blocker_prioritized_over_fanout():
    rows=prioritize([
        dict(number=1,zone="A",shared_dependencies=[dep(1),dep(2,port="blocked")]),
        dict(number=2,zone="A",shared_dependencies=[dep(1)]),
    ])
    assert [r["section_id"] for r in rows]==[2,1]
    assert rows[0]["confirmed_blocker"] is True
    assert rows[1]["confirmed_blocker"] is False

def test_unknown_never_assumed_blocked():
    rows=prioritize([dict(number=1,zone="A",shared_dependencies=[dep(1)])])
    assert not rows[0]["confirmed_blocker"]
    assert rows[0]["needs_port_evidence"]
    assert rows[0]["needs_test_evidence"]
    assert prioritize([dict(number=2,zone="B",shared_dependencies=[])])==[]

if __name__=="__main__":
    test_dedup_and_scope()
    test_blocker_prioritized_over_fanout()
    test_unknown_never_assumed_blocked()
