#!/usr/bin/env python3
from pathlib import Path
import tempfile

import workbench.migrations.legacy_package_service as service


class Patch:
    def __init__(self):
        self.original = {}
    def set(self, obj, name, value):
        self.original[(obj,name)] = getattr(obj,name)
        setattr(obj,name,value)
    def restore(self):
        for (obj,name),value in self.original.items():
            setattr(obj,name,value)


def main():
    patch=Patch()
    try:
        patch.set(service.backport_lua_convert,"detect_target_flavor",lambda root:"old_dsp_reference")
        patch.set(service.backport_sql_convert,"load_schema_map",lambda :{"tables":{}})
        patch.set(service.backport_package,"convert_lua_tree",
                  lambda *args,**kwargs:{"total_flags":0,"files":[]})
        patch.set(service.backport_package,"convert_sql_tree",
                  lambda *args,**kwargs:{"ids_by_table":{},"id_to_name_by_table":{},"rows_by_table":{}})
        patch.set(service.backport_binding_audit,"audit_package",
                  lambda *args,**kwargs:{"confirmed":["getID"],"missing":[]})
        patch.set(service.backport_lua_sanity_check,"check_package",
                  lambda *args,**kwargs:{"syntax_errors":[],"undeclared_globals":[]})
        patch.set(service.backport_package,"build_report",
                  lambda *args,**kwargs:"# Report\n\nClean\n")

        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            package=root/"package"
            dsp=root/"dsp"
            (package/"lua").mkdir(parents=True)
            (package/"lua"/"test.lua").write_text("return 1\n",encoding="utf-8")
            (package/"sql").mkdir(parents=True)
            dsp.mkdir()

            result=service.run_legacy_package_workflow(package,dsp)
            assert result["status"]=="VERIFIED",result
            assert result["overall_clean"] is True,result
            assert (package/"BACKPORT_REPORT.md").read_text(encoding="utf-8")=="# Report\n\nClean\n"

            bad=service.run_legacy_package_workflow(root/"missing",dsp)
            assert bad["status"]=="ERROR",bad

            verify=service.run_legacy_package_workflow(package,dsp,verify_only=True)
            assert verify["status"]=="ERROR",verify
            assert "Verify-only needs" in verify["error"],verify

        print("legacy package service self-test: PASS")
    finally:
        patch.restore()


if __name__=="__main__":
    main()
