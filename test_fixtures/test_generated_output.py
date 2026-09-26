#!/usr/bin/env python3
from pathlib import Path
import tempfile

from workbench.migrations.generated_output import (
    GeneratedOutput,
    materialize_generated_outputs,
    write_generated_output_journal,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        output=GeneratedOutput(
            output_id="generated:test",
            relative_path="sql-dsp/generated_test.sql",
            artifact_type="SQL",
            content="INSERT INTO `x` VALUES (1);\n",
            generator="fixture",
            metadata={"target_family":"DSP"},
        )
        result=materialize_generated_outputs([output],root)
        assert result.status=="MATERIALIZED",result
        assert len(result.records)==1,result
        assert len(result.records[0].sha256)==64,result
        assert (root/"sql-dsp"/"generated_test.sql").exists(),result

        journal=write_generated_output_journal(root,result)
        assert journal.exists(),journal
        assert "WORKBENCH_GENERATED_OUTPUT_JOURNAL" in journal.read_text(encoding="utf-8")

        second=materialize_generated_outputs([output],root)
        assert second.status=="SKIPPED",second

        unsafe=GeneratedOutput("bad","../escape.sql","SQL","x","fixture")
        try:
            materialize_generated_outputs([unsafe],root)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe generated output path must be rejected")

    print("generated migration output self-test: PASS")


if __name__=="__main__":
    main()
