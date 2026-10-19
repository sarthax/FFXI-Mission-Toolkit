"""Evidence importer contract tests; no live DSP or local data required."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("chocobo_import", Path(__file__).resolve().parents[1] / "scripts/import_chocobo_audit.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def domain():
    return {"domains": {"chocobo_raising": {"findings": [{"name": "Eggs and inventory exdata", "dsp": "unknown"}]}}}


def record(status="present", evidence=None):
    return {"target_commit": "123456789abcdef", "findings": [{
        "name": "Eggs and inventory exdata",
        "dsp": status,
        "evidence": evidence if evidence is not None else ["source:src/map/items/exdata/chocobo_egg.h:12"],
        "note": "Compared checkout at pinned commit.",
    }]}


def test_evidence_import():
    updated, names = mod.merge(domain(), record())
    finding = updated["domains"]["chocobo_raising"]["findings"][0]
    assert names == ["Eggs and inventory exdata"]
    assert finding["dsp"] == "present"
    assert finding["dsp_target_commit"] == "123456789abcdef"


@pytest.mark.parametrize("bad", [
    {"target_commit": "", "findings": []},
    {"target_commit": "123456789abcdef", "findings": [{"name": "invalid", "dsp": "present", "evidence": ["source:x"], "note": "ok"}]},
    record(status="validated"),
    record(evidence=[]),
])
def test_reject_weak_evidence(bad):
    with pytest.raises(ValueError):
        mod.merge(domain(), bad)


def test_validated_requires_runtime_evidence():
    report = record(status="validated", evidence=["test:pytest test_chocobo_packet.py::test_egg"])
    updated, _ = mod.merge(domain(), report)
    assert updated["domains"]["chocobo_raising"]["findings"][0]["dsp"] == "validated"
