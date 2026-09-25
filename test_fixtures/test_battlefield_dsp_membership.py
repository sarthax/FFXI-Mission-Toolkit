#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_dsp import propose_dsp_battlefield_membership


def main():
    groups=((101,102),(103,))
    exact=[
        {"battlefield_id":960,"battlefield_number":1,"entity_id":101,"conditions":3},
        {"battlefield_id":960,"battlefield_number":1,"entity_id":102,"conditions":3},
        {"battlefield_id":960,"battlefield_number":2,"entity_id":103,"conditions":3},
    ]
    same=propose_dsp_battlefield_membership(960,groups,exact)
    assert same.status=="EQUIVALENT",same
    assert not same.insert_sql,same

    additive=propose_dsp_battlefield_membership(960,groups,exact[:-1])
    assert additive.status=="ADDITIVE",additive
    assert additive.safe_to_generate,additive
    assert len(additive.insert_sql)==1,additive
    assert "(960,2,103,3)" in additive.insert_sql[0],additive

    conflict=propose_dsp_battlefield_membership(
        960,
        groups,
        exact[:-1]+[{"battlefield_id":960,"battlefield_number":3,"entity_id":103,"conditions":3}],
    )
    assert conflict.status=="DRIFT",conflict
    assert not conflict.safe_to_generate,conflict
    assert not conflict.insert_sql,conflict
    assert conflict.missing_rows and conflict.extra_rows,conflict

    print("DSP battlefield membership proposal self-test: PASS")


if __name__=="__main__":
    main()
