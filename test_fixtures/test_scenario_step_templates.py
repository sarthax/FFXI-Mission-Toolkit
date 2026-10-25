"""Every starter step template must yield a draft the canonical validator accepts."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

SCRIPT = r"""
const fs=require('fs'),vm=require('vm');
const ctx={window:{},console};ctx.globalThis=ctx;vm.createContext(ctx);
for (const f of ['scenario_guided_model.js','scenario_step_templates.js'])
  vm.runInContext(fs.readFileSync('gui/static/'+f,'utf8'),ctx);
const M=ctx.window.ScenarioGuidedModel||ctx.ScenarioGuidedModel, T=ctx.window.ScenarioStepTemplates||ctx.ScenarioStepTemplates;
const out={};
for(const t of T.list()){
  let spec=M.fresh();
  spec.case_id='TPL-01';spec.name='t';spec.purpose='p';spec.rationale='r';
  spec.behavior={given:['g'],when:['w'],then:['t']};
  spec.preconditions=['p'];spec.cleanup=['c'];
  spec=T.apply(spec,t.key,t.subject?'Test Item':'');
  spec=T.apply(spec,t.key,'');            // twice: must reuse checks, new step id
  out[t.key]=spec;
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node unavailable")
def test_every_template_validates_and_reuses_checks():
    raw = subprocess.run([NODE, "-e", SCRIPT], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    specs = json.loads(raw)
    assert len(specs) == 8
    for key, spec in specs.items():
        result = validate_editor_spec(spec)
        assert result["valid"], key
        ids = [s["id"] for s in spec["steps"]]
        assert len(ids) == len(set(ids)), key
        assert len(spec["assertions"]) == len({a["id"] for a in spec["assertions"]}), key
