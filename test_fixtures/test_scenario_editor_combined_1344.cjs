/* #1344 integration-only synthetic contract; NOT a live browser or merge gate. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const editor = read('gui/static/scenario_developer.js');
const html = read('gui/templates/scenario_developer.html');
const Guard = require('../gui/static/scenario_draft_guard.js');

class Element {
  constructor(){this.hidden=true;this.children=[];this.value='';this.textContent='';this.attributes={};}
  append(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
}
const ids = ['sd-work-state','sd-revision-state','sd-validation-summary',
  'sd-purpose','sd-given','sd-when','sd-then','sd-rationale','sd-advanced-json'];
const elements = new Map(ids.map(id=>[id,new Element()]));
const callbacks = new Map();
const win = {
  document: {
    getElementById:id=>elements.get(id)||null,
    createElement:()=>new Element()
  },
  addEventListener(type,handler){
    const handlers=callbacks.get(type)||[];
    handlers.push(handler);callbacks.set(type,handlers);
  },
  removeEventListener(type,handler){
    callbacks.set(type,(callbacks.get(type)||[]).filter(x=>x!==handler));
  }
};
vm.runInNewContext(read('gui/static/scenario_validation_feedback.js'),{window:win});
const feedback=win.ScenarioValidationFeedback;
assert.ok(feedback);
let spec={feature_id:'synthetic',case_id:'editor_collision',
  purpose:'',assertions:[],source_associations:[{scope:'STEP',source_ref:'SYNTH-NOT-AUTH'}]};
let baseline=null,revc=0,pending=false,mode='guided',advanced='';
const copy=x=>JSON.parse(JSON.stringify(x));
const guard=Guard.create({
  win,
  getCurrent:()=>mode==='advanced'?JSON.parse(advanced):spec,
  getBaseline:()=>baseline,
  getRevision:()=>revc,
  isSavePending:()=>pending,
  onStatus:state=>{
    elements.get('sd-work-state').textContent=state.banner;
    elements.get('sd-work-state').setAttribute('data-state',state.state);
    elements.get('sd-revision-state').textContent=state.detail;
  }
});
const attempt=()=>{
  const e={prevented:false,preventDefault(){this.prevented=true;}};
  for(const fn of callbacks.get('beforeunload')||[])fn(e);
  return e;
};
guard.start('new',spec);
assert.equal(guard.refresh().state,'pristine');
spec=copy(spec);spec.purpose='not yet saved';guard.refresh();
assert.equal(guard.inspect().state,'unsaved');
assert.equal(attempt().prevented,true);
const errors=[
 {field:'purpose',control_id:'sd-purpose',message:'Required <script> is TEXT',required:true},
 {field:'given',control_id:'sd-given',message:'Missing precondition',required:true}
];
const before=JSON.stringify(spec);
assert.equal(feedback.show(errors),true);
assert.equal(JSON.stringify(spec),before,'422 feedback must not normalize data');
assert.equal(elements.get('sd-work-state').attributes['data-state'],'unsaved');
assert.equal(elements.get('sd-purpose').attributes['aria-invalid'],'true');
assert.equal(elements.get('sd-validation-summary').children[1].children[0].children[1].textContent,
 'Required <script> is TEXT');
assert.equal(attempt().prevented,true,'422 failure must retain reload guard');
pending=true;assert.equal(guard.refresh().state,'unsaved');
pending=false;assert.equal(guard.refresh().state,'unsaved','failed Save must remain dirty');
feedback.clear();
assert.equal(elements.get('sd-purpose').attributes['aria-invalid'],undefined);
assert.equal(guard.inspect().state,'unsaved','clearing field feedback is NOT saving');
baseline=copy(spec);revc=1;assert.equal(guard.refresh().state,'saved');
assert.equal(attempt().prevented,false);
mode='advanced';advanced=JSON.stringify(spec);
assert.equal(guard.refresh().state,'saved');
advanced='{invalid JSON';assert.equal(guard.refresh().state,'unsaved');
assert.equal(attempt().prevented,true,'invalid Advanced draft protected');
advanced=JSON.stringify({...spec,purpose:'edited in advanced'});
assert.equal(guard.refresh().state,'unsaved');
const cancelled=attempt();assert.equal(cancelled.prevented,true);
assert.equal(guard.inspect().warn,true,'cancelled browser leave must not clear dirty state');
assert.equal((callbacks.get('beforeunload')||[]).length,1);
assert.deepEqual(spec.source_associations,[{scope:'STEP',source_ref:'SYNTH-NOT-AUTH'}],
 'source association not mutated by status/field error render');
guard.dispose();
assert.equal(callbacks.get('beforeunload').length,0);

// Full combined editor integration invariants: these must coexist in one
// actual JS/template revision, not merely pass on separate original PRs.
assert.match(editor,/const Feedback = window\.ScenarioValidationFeedback/);
assert.match(editor,/draftGuard=window\.ScenarioDraftGuard\.create\(/);
assert.match(editor,/if\(Feedback\)Feedback\.show\(e\.validationErrors\)/);
assert.match(editor,/if\(Feedback\)Feedback\.clear\(\)/);
assert.match(editor,/if\(path==='\/scenario-developer\/validate' && detail &&/);
assert.match(editor,/finally \{savePending=false;\$\('sd-save'\)\.disabled=false;draftGuard\.refresh\(\);\}/,
 'validation-feedback Save catch must not erase draft-guard Save finally');
assert.match(editor,/M\.saveResponseDisposition\(toSave,latest,saved,/,
 'successful persistence still obeys original optimistic revision guard');
assert.match(editor,/if\(mode!==target\)resetReadinessViewer\(\)/);
assert.ok((editor.match(/editorGeneration\+\+;resetReadinessViewer\(\);/g)||[]).length>=4,
 'all accepted document replacements invalidate readiness async state');
assert.match(editor,/function resetReadinessViewer\(\) \{\s*if\(readinessViewer\)readinessViewer\.dispose\(\);/);
assert.match(editor,/window\.addEventListener\('pagehide',\(\)=>\{\s*if\(readinessViewer\)readinessViewer\.dispose\(\)/);
assert.match(editor,/if\(mode==='advanced'\)return M\.parseAdvanced\(\$\('sd-advanced-json'\)\.value\)/);
assert.match(editor,/syncAdvancedAfterReplacement\(\)/);
for(const origin of ['new','fork','clone','saved','handoff'])
 assert.match(editor,new RegExp("draftGuard\\.start\\('"+origin+"',spec\\)"));
const scripts=['scenario_guided_model.js','scenario_contract_v2_view.js',
  'scenario_readiness_viewer.js','scenario_draft_guard.js',
  'scenario_validation_feedback.js','scenario_developer.js'];
let previous=-1;
for(const script of scripts){
  const current=html.indexOf('/static/'+script);
  assert.ok(current>previous,'helper order: '+script);previous=current;
}
assert.equal((html.match(/id="sd-work-state"/g)||[]).length,1);
assert.equal((html.match(/id="sd-validation-summary"/g)||[]).length,1);
assert.match(html,/aria-label="Validation field errors"/);
assert.ok(!editor.includes('addEventListener(\'beforeunload\''),
 'native unload listener is owned by one helper');
console.log('#1344 combined-editor lifecycle, 422/dirty, canceled unload, Contract v2 and viewer teardown wiring: PASS');
