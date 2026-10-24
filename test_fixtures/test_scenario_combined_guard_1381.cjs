/* #1381 — synthetic ONLY, verify actual combined E+B editor lifecycle.
 * Invokes E's real deferred-click handler harness. No server, live browser or writes.
 * This test MUST fail rather than treating a missing B guard as acceptable.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const file=name=>fs.readFileSync(path.join(root,name),'utf8');
const js=file('gui/static/scenario_developer.js');
const html=file('gui/templates/scenario_developer.html');
const guardPath=path.join(root,'gui/static/scenario_draft_guard.js');
assert.equal(fs.existsSync(guardPath),true,'real B draft guard required, not optional/mock');
const DraftGuard=require(guardPath);
assert.equal(typeof DraftGuard.create,'function');
const expectedScripts=[
  'scenario_guided_model.js','scenario_contract_v2_view.js',
  'scenario_readiness_viewer.js','scenario_draft_guard.js',
  'scenario_validation_feedback.js','scenario_developer.js'];
let last=-1;
for(const name of expectedScripts) {
  const pos=html.indexOf('/static/'+name);
  assert.ok(pos>last,'editor script order must load '+name+' before the editor');
  last=pos;
}
assert.equal((html.match(/id="sd-work-state"/g)||[]).length,1);
assert.equal((html.match(/id="sd-validation-summary"/g)||[]).length,1);
assert.match(js,/const Feedback = window\.ScenarioValidationFeedback/);
assert.match(js,/draftGuard=window\.ScenarioDraftGuard\.create\(/);
assert.match(js,/let validationUiRequest = 0/);
assert.match(js,/if\(uiRequest!==validationUiRequest\)return/);
assert.match(js,/validationRequestCurrent\(generation,input,rev\)/);
assert.match(js,/finally \{savePending=false;\$\('sd-save'\)\.disabled=false;draftGuard\.refresh\(\);\}/,
 'E deferred Save flow must always update B unsaved indicator in finally');
assert.match(js,/M\.saveResponseDisposition\(toSave,latest,saved,/,
 'optimistic persisted-revision gate must remain active');
assert.match(js,/contract_v2_source_attribution/);
assert.match(js,/function resetReadinessViewer\(\) \{\s*if\(readinessViewer\)readinessViewer\.dispose\(\);/);
assert.match(js,/window\.addEventListener\('pagehide',\(\)=>\{\s*if\(readinessViewer\)readinessViewer\.dispose\(\)/);
assert.match(js,/draftGuard\.start\('new',spec\)/);
assert.match(js,/draftGuard\.start\('saved',spec\)/);
const output=execFileSync(process.execPath,
  [path.join(root,'test_fixtures/test_scenario_validation_async_1362.cjs')],
  {cwd:root,encoding:'utf8',timeout:20000});
assert.match(output,/#1362 actual click handlers.*: PASS/);
assert.match(output,/#1378 combined REAL ScenarioDraftGuard pending\/invalid\/unload coverage: PASS/,
 'must execute REAL combined guard, not silently downgrade to E-only NOT_RUN');
assert.doesNotMatch(output,/combined guard checks NOT_RUN/);
console.log('#1381 combined B+E editor: real draft guard + deferred Save/Validate + viewer/v2 wiring PASS');
