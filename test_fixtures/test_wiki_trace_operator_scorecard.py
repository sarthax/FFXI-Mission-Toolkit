"""Scorecard must not mistake missing acceptance for a passing run."""
from scripts.wiki_trace_acceptance_score import CASES, METRICS, summarize


def main():
    empty = summarize([])
    assert not empty["all_passed"] and empty["counts"]["PASS"] == 0
    blocked = summarize([{"case":"medusa","status":"BLOCKED"}])
    assert blocked["counts"]["BLOCKED"] == 1 and not blocked["all_passed"]
    passed=[{"case":case,"status":"PASS","checks":{k:True for k in METRICS},
             "clicks":2,"environment":"local-db-verified","source_revision":"captured-revision"}
            for case in CASES]
    assert summarize(passed)["all_passed"]
    for bad in (
        [{"case":"medusa","status":"PASS"}],
        [{"case":"medusa","status":"PASS","checks":{k:True for k in METRICS},
          "clicks":2,"environment":"local","source_revision":"rev"},
         {"case":"medusa","status":"NOT_RUN"}],
        [{"case":"medusa","status":"PASS","checks":{k:False for k in METRICS},
          "clicks":2,"environment":"local","source_revision":"rev"}],
    ):
        try:
            summarize(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid observations: {bad}")
    print("Wiki Trace operator scorecard contract: PASS")


if __name__ == "__main__":
    main()
