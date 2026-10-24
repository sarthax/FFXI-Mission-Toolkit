// EV16 isolated source-handler rehearsal — synthetic data only; no editor/runtime edits.
// Uses the real Advanced JSON switch and Apply handler extracted from the checked-out editor.
// Distinguishes a known reported P3 from a defect actually reproduced at this source SHA.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'gui/static/scenario_developer.js'), 'utf8');
const modelSource = fs.readFileSync(path.join(root, 'gui/static/scenario_guided_model.js'), 'utf8');
const sandbox = { window: {} };
vm.runInNewContext(modelSource, sandbox, { filename: 'scenario_guided_model.js' });
const M = sandbox.window.ScenarioGuidedModel;
assert.ok(M && typeof M.parseAdvanced === 'function');
const begin = source.indexOf('  function readGuidedFields() {');
const end = source.indexOf('  function staticText(', begin);
assert.ok(begin !== -1 && end > begin, 'real Guided/Advanced handler boundaries exist');
const handler = source.slice(begin, end);
assert.match(handler, /if\(mode==='advanced'\) spec=M\.parseAdvanced/);
assert.match(handler, /if\(target==='advanced'\).*JSON\.stringify\(spec,null,2\)/);
const applyLine = source.match(/\$\('sd-apply-json'\)\.addEventListener\('click',\(\)=>switchMode\('guided'\)\);/);
assert.ok(applyLine, 'real Apply JSON click listener remains wired to Guided switch');
const nodes = new Map();
const $ = id => {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', hidden: false, textContent: '', attrs: {}, listeners: {},
    setAttribute(name, value) { this.attrs[name] = value; },
    addEventListener(type, fn) { this.listeners[type] = fn; }
  });
  return nodes.get(id);
};
const initial = {
  schema_version: 1, runner: 'unassigned', execution_status: 'design_only',
  feature_id: 'synthetic_feature', case_id: 'synthetic_case', name: 'Synthetic case',
  purpose: '', rationale: '', behavior: { given: [], when: [], then: [] },
  preconditions: [], cleanup: [], observations: [], authoring: {blocking_gaps: []},
  contract_v2: { marker: 'OLD_METADATA' }
};
const plain = ['sd-feature', 'sd-case', 'sd-title', 'sd-purpose', 'sd-rationale',
  'sd-given','sd-when','sd-then','sd-preconditions','sd-cleanup','sd-gaps'];
for (const id of plain) $(id).value = '';
$('sd-feature').value = initial.feature_id;
$('sd-case').value = initial.case_id;
$('sd-title').value = initial.name;
const setup = new Function('M', '$', 'initial', 'handler', 'applyLine', `
  let spec = JSON.parse(JSON.stringify(initial)), mode = 'guided';
  const lineItems = value => value.split('\\n').map(s => s.trim()).filter(Boolean);
  const selections = () => [];
  const render = () => {};
  const resetReadinessViewer = () => {};
  const show = text => { $('sd-result').textContent = text; };
  const renderContractV2 = () => {};
  const updateRevision = () => {};
  const el = () => ({});
  const options = { features: [], observations: [] };
  eval(handler + '\\n' + applyLine);
  return { switchMode, current, getSpec: () => spec, getMode: () => mode };
`);
const page = setup(M, $, initial, handler, applyLine[0]);
function exercise(label, transform) {
  // Start from actual Guided -> Advanced handler each time.
  page.switchMode('advanced');
  const json = JSON.parse($('sd-advanced-json').value);
  transform(json);
  $('sd-advanced-json').value = JSON.stringify(json);
  $('sd-apply-json').listeners.click();
  assert.equal(page.getMode(), 'guided', label + ': handler returned to Guided');
  const actual = JSON.parse(JSON.stringify(page.getSpec()));
  const expected = json.contract_v2;
  if (expected === undefined) assert.equal(Object.hasOwn(actual,'contract_v2'),false,label + ': deleted metadata stays deleted');
  else assert.deepEqual(actual.contract_v2,expected,label + ': edited metadata replaces original');
  return actual;
}
exercise('remove existing contract_v2', x => { delete x.contract_v2; });
exercise('replace existing contract_v2', x => { x.contract_v2 = {marker:'NEW_METADATA'}; });
console.log('EV16 SOURCE-HANDLER REHEARSAL: 2 cases PASS (remove and replace contract_v2).');
console.log('REPORTED P3 NOT REPRODUCED in isolated current-main Apply handler; this is NOT real browser acceptance.');
console.log('NOT_RUN: real page DOM, advanced field render, server validation, Save, browser EV16 and combined PR stack.');
