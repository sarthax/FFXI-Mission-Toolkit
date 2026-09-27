#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"test_fixtures"/"fixtures"/"mission_mechanic_coverage_probe.json"

def main():
    p=json.loads(P.read_text(encoding="utf-8"))
    samples=p["samples"]; support=p["current_model_support"]
    assert len(samples)>=4
    seen={m for s in samples for m in s["mechanics"]}
    assert seen <= set(support),seen-set(support)
    missing=sorted(m for m in seen if support[m]=="MISSING")
    partial=sorted(m for m in seen if support[m]=="PARTIAL")
    assert "parallel_status_channels" in missing
    assert "timed_expiry" in missing
    assert "spawn_mob" in missing
    assert "client_transport" in missing
    assert "battlefield_result_guard" in partial
    print("multi-mission mechanic coverage probe: PASS")
    print("samples",len(samples),"mechanics",len(seen),"full",sum(support[m]=="FULL" for m in seen),"partial",len(partial),"missing",len(missing))
    print("missing",",".join(missing))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
