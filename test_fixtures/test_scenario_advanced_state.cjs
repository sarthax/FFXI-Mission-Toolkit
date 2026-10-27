/* #1302: deterministic Advanced JSON dirty-state + replacement synchronization.
 * Synthetic-only; no browser, storage, network, client or runtime.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const M=require('../gui/static/scenario_guided_model.js');
const script=fs.readFileSync('gui/static/scenario_developer.js','utf8');

const saved=M.fresh();
saved.case_id='SYNTH-REV-A';
saved.purpose='original saved purpose';
const changed=M.clone(saved);
changed.purpose='edited from Advanced JSON';
assert.match(M.advancedRevisionIndicator(saved,JSON.stringify(saved,null,4),3),/Loaded revision 3 · no changes/);
assert.match(M.advancedRevisionIndicator(saved,JSON.stringify(changed,null,2),3),/Loaded revision 3 · unsaved changes/);
assert.match(M.advancedRevisionIndicator(saved,'{"broken":',3),/invalid.*unsaved text/i);
assert.match(M.advancedRevisionIndicator(null,JSON.stringify(changed),0),/New draft.*unsaved/);
assert.equal(saved.purpose,'original saved purpose','inspecting textarea must never mutate spec');
assert.equal(M.parseAdvanced(JSON.stringify(changed)).purpose,changed.purpose);

// Exercise the actual editor helper against a deliberately stale hidden buffer.
const match=script.match(/function syncAdvancedAfterReplacement\(\) \{[\s\S]*?\n  \}/);
assert.ok(match,'the editor must have a scoped after-confirmation sync');
const stale={value:JSON.stringify(changed)};
const guided={pressed:null,setAttribute(k,v){assert.equal(k,'aria-pressed');this.pressed=v;}};
const advanced={pressed:null,setAttribute(k,v){assert.equal(k,'aria-pressed');this.pressed=v;}};
const nodes={'sd-advanced-json':stale,'sd-guided':guided,'sd-advanced':advanced};
const replacement=M.clone(saved);
replacement.case_id='SYNTH-REOPEN-B';
const sync=vm.runInNewContext('('+match[0]+')',{spec:replacement,$:id=>nodes[id],JSON});
sync();
assert.equal(JSON.parse(stale.value).case_id,'SYNTH-REOPEN-B');
assert.equal(JSON.parse(stale.value).purpose,'original saved purpose');
assert.equal(guided.pressed,'true');
assert.equal(advanced.pressed,'false');
assert.equal(M.advancedRevisionIndicator(replacement,stale.value,4),'Loaded revision 4 · no changes');

// The editor must refresh ONLY once a user confirms a document replacement.
for(const action of ['New scenario','Fork published case','Clone current draft','Open saved draft']) {
  const location=script.indexOf("confirmDocumentReplacement('"+action+"')");
  assert.ok(location>=0,'replacement guard: '+action);
  const accepted=script.indexOf('syncAdvancedAfterReplacement();',location);
  assert.ok(accepted>location && accepted-location<850,'sync follows guard: '+action);
}
assert.match(script,/function switchMode\(target\)[\s\S]*?updateAdvancedRevision\(\)/);
assert.match(script,/addEventListener\('input',updateAdvancedRevision\)/);
assert.match(script,/if\(mode!=='advanced'\)return/,'hidden scripted events must not override Guided state');
assert.doesNotMatch(script,/Advanced JSON has unsaved edits — validate before saving/);
console.log('Scenario Advanced dirty and confirmed replacement state: PASS');

// A stale field-error summary must not survive a document replacement (#1403 follow-up).
assert.equal((script.match(/editorGeneration\+\+;resetReadinessViewer\(\);clearValidationSummary\(\);/g)||[]).length,5,
  'New/Fork/Clone/Open/Handoff must all clear the validation summary');
console.log('Stale validation summary cleared on document replacement: PASS');
