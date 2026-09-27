#!/usr/bin/env python3
"""Regression for reviewable client item-DAT migration orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.client.dat_adapter import ClientDatRecord
from workbench.migrations.client_dat_migration import (
    ClientDatOperation,
    apply_approved_client_dat_plan,
    assess_client_dat_plan_for_approval,
    build_client_dat_approval_request,
    build_client_dat_patch_plan,
    rollback_client_dat_apply,
)
from workbench.migrations.generated_output import (
    materialize_generated_outputs,
    write_generated_output_journal,
)
from workbench.migrations.patch_package_integrity import verify_patch_package_integrity


class FakeAdapter:
    def __init__(self, record: ClientDatRecord):
        self.snapshot_id=record.snapshot_id
        self.record=record

    def read(self,item_id: int):
        if int(item_id)!=self.record.item_id:
            return None
        return self.record


def record(level: int = 99) -> ClientDatRecord:
    return ClientDatRecord(
        item_id=10478,
        snapshot_id="client:30191204_1",
        category="armor",
        layout="armor",
        format="legacy",
        source_path="ROM/119/57.DAT",
        record_index=238,
        fields={
            "id":10478,
            "name":"Euxine Coat +3",
            "level":level,
            "jobs":1234,
            "slots":32,
            "flags":0,
        },
    )


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        adapter=FakeAdapter(record())
        writer_calls=[]

        op=ClientDatOperation(
            operation_id="client-dat:item-10478-level",
            item_id=10478,
            fields={"level":90},
            expected_fields={"level":99,"name":"Euxine Coat +3"},
            metadata={"reason":"fixture client/server synchronization"},
        )
        plan=build_client_dat_patch_plan("fixture",adapter,(op,))
        assert plan.artifact_type=="CLIENT_DAT_PLAN",plan
        payload=json.loads(plan.content)
        assert payload["status"]=="READY",payload
        assert payload["operations"][0]["source_fingerprint"],payload
        assert writer_calls==[],writer_calls

        ready=assess_client_dat_plan_for_approval(plan.content,adapter)
        assert ready.status=="READY_FOR_APPROVAL",ready

        adapter.record=record(level=98)
        drift=assess_client_dat_plan_for_approval(plan.content,adapter)
        assert drift.status=="DRIFTED",drift
        adapter.record=record()

        request=build_client_dat_approval_request(plan.content,ready,request_id="fixture")
        assert request.artifact_type=="CLIENT_DAT_APPROVAL_REQUEST",request

        target=root/"pivot"/"ROM"/"119"/"57.DAT"
        target.parent.mkdir(parents=True)
        original=b"original-dat-bytes"
        target.write_bytes(original)

        def fake_writer(item_id: int,fields: dict):
            writer_calls.append((item_id,dict(fields)))
            backup=root/"backups"/"before.dat"
            backup.parent.mkdir(parents=True,exist_ok=True)
            backup.write_bytes(target.read_bytes())
            target.write_bytes(b"patched-dat-bytes")
            return {
                "ok":True,
                "category":"armor",
                "dat":str(target),
                "dat_ui":"ROM/119/57.DAT",
                "record_index":238,
                "format":"legacy",
                "fields":list(fields),
                "target":"pivot",
                "target_existed":True,
                "backup_path":str(backup),
            }

        journal_path=root/"journals"/"client_dat_apply.json"
        try:
            apply_approved_client_dat_plan(
                plan.content,adapter,request.content,journal_path,writer=fake_writer
            )
        except ValueError as ex:
            assert "not APPROVED" in str(ex),ex
        else:
            raise AssertionError("PENDING client DAT approval must block apply")
        assert writer_calls==[],writer_calls
        assert target.read_bytes()==original

        approved=json.loads(request.content)
        approved["status"]="APPROVED"
        journal=apply_approved_client_dat_plan(
            plan.content,adapter,approved,journal_path,writer=fake_writer
        )
        assert journal["status"]=="APPLIED",journal
        assert writer_calls==[(10478,{"level":90})],writer_calls
        assert target.read_bytes()==b"patched-dat-bytes"
        assert journal["entries"][0]["backup_path"],journal

        rolled=rollback_client_dat_apply(journal_path)
        assert rolled["status"]=="ROLLED_BACK",rolled
        assert target.read_bytes()==original

        package=root/"package"
        result=materialize_generated_outputs((plan,request),package)
        write_generated_output_journal(package,result)
        integrity=verify_patch_package_integrity(package)
        assert integrity.status=="COHERENT",integrity

        approval_path=package/request.relative_path
        broken=json.loads(approval_path.read_text(encoding="utf-8"))
        broken["client_dat_plan_sha256"]="wrong"
        approval_path.write_text(json.dumps(broken,indent=2)+"\n",encoding="utf-8")
        failed=verify_patch_package_integrity(package)
        assert failed.status=="FAILED",failed

    print("client DAT migration orchestration self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
