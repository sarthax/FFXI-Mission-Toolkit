#!/usr/bin/env python3
"""Regression coverage for progression logical records across server lineages."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter, load_lsb_merits
from workbench.adapters.servers.logical import compare_records


MERIT_YAML = """merits:
  upgrade_costs:
    hp_mp: [1, 2, 3]
  categories:
    hp_mp:
      id: 0x0040
      max_upgrades: 75
      merits:
        max_hp:
          id: 0x0040
          value: 10
          upgrade_cost: hp_mp
"""


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        (root/"sql").mkdir()
        topaz=TopazAdapter(root)
        dsp=DSPAdapter(root)
        lsb=LSBAdapter(root)

        legacy_job={
            "job_pointid":64,
            "name":"mighty_strikes_effect",
            "upgrade":2,
            "jobs":1,
        }
        modern_job={
            "job_pointid":32,
            "name":"mighty_strikes_effect",
            "upgrade":2,
            "jobs":1,
        }
        topaz_job=topaz.normalize_row("job_points",legacy_job)
        dsp_job=dsp.normalize_row("job_points",legacy_job)
        lsb_job=lsb.normalize_row("job_points",modern_job)

        assert topaz_job.identity==(("job_id",1),("name","mighty_strikes_effect")),topaz_job
        assert compare_records(topaz_job,dsp_job).status=="EQUIVALENT"
        job_drift=compare_records(topaz_job,lsb_job)
        assert job_drift.status=="DIFFERENT",job_drift
        assert any(
            diff.field=="job_point_id"
            and diff.source_value==64
            and diff.target_value==32
            and diff.status=="VALUE_MISMATCH"
            for diff in job_drift.differences
        ),job_drift

        legacy_merit=topaz.normalize_row("merits",{
            "meritid":64,
            "name":"max_hp",
            "upgrade":15,
            "value":10,
            "jobs":1048575,
            "upgradeid":0,
            "catagoryid":0,
        })
        dsp_merit=dsp.normalize_row("merits",{
            "meritid":64,
            "name":"max_hp",
            "upgrade":15,
            "value":10,
            "jobs":1048575,
            "upgradeid":0,
            "catagoryid":0,
        })
        assert compare_records(legacy_merit,dsp_merit).status=="EQUIVALENT"

        merit_path=root/"merits.yaml"
        merit_path.write_text(MERIT_YAML,encoding="utf-8")
        modern_merits=load_lsb_merits(merit_path)
        assert len(modern_merits)==1,modern_merits
        modern_merit=modern_merits[0]
        assert modern_merit.identity==(("merit_id",64),),modern_merit
        assert modern_merit.fields["name"]=="max_hp",modern_merit
        assert modern_merit.fields["value"]==10,modern_merit
        assert modern_merit.fields["upgrade_cost_key"]=="hp_mp",modern_merit
        assert modern_merit.fields["lsb_category_id"]==64,modern_merit
        assert modern_merit.fields["category_max_upgrades"]==75,modern_merit

        merit_drift=compare_records(legacy_merit,modern_merit)
        assert merit_drift.status=="DIFFERENT",merit_drift
        assert not any(diff.field in {"name","value"} for diff in merit_drift.differences),merit_drift
        assert any(diff.field=="jobs_mask" and diff.status=="MISSING_FIELD_VALUE" for diff in merit_drift.differences),merit_drift
        assert any(diff.field=="upgrade_cost_key" and diff.status=="MISSING_FIELD_VALUE" for diff in merit_drift.differences),merit_drift

        assert lsb.resolve_table("merits") is None
        assert lsb.resolve_table("job_points") is not None

    print("progression logical schema self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
