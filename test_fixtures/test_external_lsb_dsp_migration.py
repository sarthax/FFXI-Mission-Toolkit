#!/usr/bin/env python3
"""Public-source migration smoke: pinned LSB Excavation Duty -> archived DSP."""
from __future__ import annotations
import json,sys
from pathlib import Path

from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.migrations.instance_feature_slice import extract_instance_feature_slice
from workbench.migrations.instance_slice_compare import compare_instance_slices

def main():
    if len(sys.argv)!=3:
        raise SystemExit("usage: test_external_lsb_dsp_migration.py <lsb-root> <dsp-root>")
    lsb_root=Path(sys.argv[1]).resolve()
    dsp_root=Path(sys.argv[2]).resolve()
    source=extract_instance_feature_slice(LSBAdapter(lsb_root),6300)
    target=extract_instance_feature_slice(DSPAdapter(dsp_root),6300)
    assert source.instance is not None,source.counts()
    result=compare_instance_slices(source,target,"migration:lsb-to-dsp:excavation-duty")
    summary={
        "source":source.counts(),
        "target":target.counts(),
        "actions":{
            "total":len(result.actions),
            "implement":sum(1 for a in result.actions if a.action=="IMPLEMENT"),
            "manual_review":sum(1 for a in result.actions if a.action=="MANUAL_REVIEW"),
            "not_required":sum(1 for a in result.actions if a.action=="NOT_REQUIRED"),
        },
        "comparisons":len(result.comparisons),
    }
    assert result.actions,summary
    if target.instance is None:
        assert any(a.action=="IMPLEMENT" and a.metadata.get("logical_type")=="instances" for a in result.actions),summary
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
