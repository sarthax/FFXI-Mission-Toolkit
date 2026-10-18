from workbench.domains.assault_readiness_filters import filter_missions

def main():
    m={"number":12,"zone":"Periqia","readiness":{"status":"needs_evidence"},
       "reviews":{"implementation":{"state":"validated"},"port":{"state":"validated"},"validation":{"state":"pending"}},
       "issue_crossrefs":[{"id":1,"reviews":{"dsp_port":{"state":"unreviewed"}}}],
       "shared_dependencies":[{"title":"Portal","port":"fixed"}]}
    assert not filter_missions([m],status="ready_for_live_test")
    m["issue_crossrefs"][0]["reviews"]["dsp_port"]["state"]="fixed"
    assert len(filter_missions([m],status="ready_for_live_test"))==1
    m["shared_dependencies"][0]["port"]="unreviewed"
    assert not filter_missions([m],status="ready_for_live_test")
    m["shared_dependencies"][0]["port"]="not_applicable"
    assert len(filter_missions([m],status="ready_for_live_test"))==1
    print("Assault live-test evidence gate: PASS")

if __name__=="__main__":
    main()
