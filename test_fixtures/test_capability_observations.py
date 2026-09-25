#!/usr/bin/env python3
"""Regression checks for snapshot-specific capability observations in Feature Checker."""
from pathlib import Path
import tempfile
from workbench.core import graph
from workbench.core.schema import Capability, CapabilityObservation, CapabilityRequirement, Feature
from feature_checker import resolve_feature, check_feature

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        feature=Feature(
            "feature:test","Test","SYSTEM","domain:test","src","dst","ANALYZED"
        )
        graph.insert_record(con,feature)
        graph.insert_record(con,Capability(
            "capability:feature:test:mission_completion",
            "mission_completion",
            "FEATURE_SURFACE",
            subject_id="feature:test",
            status="UNKNOWN",
        ))
        graph.insert_record(con,CapabilityRequirement(
            "requirement:test:mission_completion",
            "feature:test",
            "capability:feature:test:mission_completion",
            True,
            "DISCOVERED",
        ))
        graph.insert_record(con,CapabilityObservation(
            "observation:src",
            "capability:feature:test:mission_completion",
            "src",
            "VERIFIED",
        ))
        graph.insert_record(con,CapabilityObservation(
            "observation:dst",
            "capability:feature:test:mission_completion",
            "dst",
            "VERIFIED",
        ))

        resolved=resolve_feature(con,"feature:test")
        result=check_feature(con,resolved)
        assert result["status"]=="REQUIRED_CAPABILITIES_VERIFIED",result
        check=result["requirements"][0]
        assert check["observed_status"]=="VERIFIED",check
        assert check["observation_selection"]=="TARGET_SNAPSHOT",check
        assert [o["observation_id"] for o in check["selected_observations"]]==["observation:dst"],check

        con.execute("DELETE FROM capability_observations WHERE observation_id='observation:dst'")
        con.commit()
        result=check_feature(con,resolve_feature(con,"feature:test"))
        assert result["status"]=="UNKNOWN_REQUIRED_CAPABILITY",result
        check=result["requirements"][0]
        assert check["observed_status"]=="UNKNOWN",check
        assert check["observation_selection"]=="NO_TARGET_OBSERVATION",check
        con.close()
    print("capability observation self-test: PASS")

if __name__=="__main__":
    main()
