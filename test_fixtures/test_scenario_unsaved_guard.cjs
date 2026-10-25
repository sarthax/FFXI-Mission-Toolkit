/* #1333 synthetic-only navigation/dirty state; NO local browser or runtime. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const M=require('../gui/static/scenario_guided_model.js');
const G=require('../gui/static/scenario_draft_guard.js');
const editor=fs.readFileSync('gui/static/scenario_developer.js','utf8');
const template=fs.readFileSync('gui/templates/scenario_developer.html','utf8');
const copy=v=>JSON.parse(JSON.stringify(v));
const windowMock={
  handlers:new Map(),
  addEventListener(type,handler){
    const list=this.handlers.get(type)||[];
    list.push(handler);this.handlers.set(type,list);
  },
  removeEventListener(type,handler){
    this.handlers.set(type,(this.handlers.get(type)||[]).filter(f=>f!==handler));
  },
  fire(type,evt){
    for(const handler of this.handlers.get(type)||[])handler(evt);
  }
};
let current=M.fresh(),baseline=null,revision=0,mode='guided',advancedText='',saving=false;
const events=[];
const guard=G.create({
  win:windowMock,
  getCurrent(){return mode==='advanced'?M.parseAdvanced(advancedText):current;},
  getBaseline(){return baseline;},getRevision(){return revision;},
  isSavePending(){return saving;},onStatus(s){events.push(s);}
});
const attempt=()=>{
  const ev={prevented:false,preventDefault(){this.prevented=true;}};
  windowMock.fire('beforeunload',ev);
  return ev;
};
assert.equal((windowMock.handlers.get('beforeunload')||[]).length,1);
guard.start('new',current);
assert.equal(guard.refresh().state,'pristine');
assert.equal(guard.inspect().warn,false);
assert.equal(attempt().prevented,false,'pristine New draft need not prompt');

current=copy(current);current.purpose='User typed a new source-backed claim (not verified)';
assert.equal(guard.refresh().state,'unsaved');
assert.match(guard.inspect().banner,/UNSAVED WORK/);
assert.equal(attempt().prevented,true,'reload must warn on unsaved new draft');
const canceled=attempt();
assert.equal(canceled.returnValue,'');
assert.equal(guard.inspect().warn,true,'canceled browser dialog preserves edited state');
assert.equal(attempt().prevented,true,'same-app full-page link also uses beforeunload');
assert.equal((windowMock.handlers.get('beforeunload')||[]).length,1,'no duplicate prompts');

guard.start('new',M.fresh());current=M.fresh();
assert.equal(guard.refresh().state,'pristine','accepted New replacement resets baseline');
current=copy(current);current.contract_v2={
  contract_version:2,source_associations:[{scope:'case',target_id:null,source_refs:['SYNTH-SRC']}]
};
assert.equal(guard.refresh().state,'unsaved');
const v2Snapshot=JSON.stringify(current.contract_v2);
mode='advanced';advancedText=JSON.stringify(current,null,2);
assert.equal(guard.inspect().state,'unsaved');
advancedText='{"broken":';
assert.equal(guard.refresh().invalid,true);
assert.equal(attempt().prevented,true,'invalid Advanced JSON must not lose unload warning');
advancedText=JSON.stringify(current);
mode='guided';
assert.equal(JSON.stringify(current.contract_v2),v2Snapshot,'Contract v2 remains unchanged');

current=M.forkPublished({...M.fresh(),runner:'xiheadless_observation_v1',execution_status:'verified_runner'});
baseline=null;revision=0;
guard.start('fork',current);
assert.equal(guard.refresh().state,'unsaved','unmodified fork itself needs protection');
assert.equal(attempt().prevented,true);
current=M.cloneDraft(current);
guard.start('clone',current);
assert.equal(guard.inspect().state,'unsaved','unmodified clone also needs protection');
const copyBefore=copy(current);
saving=true;
assert.equal(guard.inspect().warn,true,'in-flight save cannot relax warning');
saving=false; // simulated failed save
assert.equal(guard.inspect().state,'unsaved','failed save must not clear marker');
assert.deepEqual(current,copyBefore);

baseline=copy(current);revision=1;
assert.equal(guard.refresh().state,'saved','only confirmed persisted snapshot clears marker');
assert.equal(attempt().prevented,false);
assert.match(guard.inspect().banner,/SAVED/);
current=copy(current);current.name='edited after saved revision';
assert.equal(guard.inspect().state,'unsaved');
const savedSnapshot=copy(current);
saving=true;
current=copy(current);current.purpose='newer unsaved change during async save';
baseline=savedSnapshot;revision=2;
assert.equal(guard.inspect().state,'unsaved');
saving=false;
assert.equal(guard.refresh().state,'unsaved','save response for older snapshot leaves later edit dirty');
assert.equal(attempt().prevented,true);
baseline=copy(current);revision=3; // successful exact latest save
assert.equal(guard.refresh().state,'saved');
mode='advanced';advancedText=JSON.stringify(current);
assert.equal(guard.inspect().state,'saved','no false dirty for formatted Advanced JSON');
advancedText=JSON.stringify({...current,rationale:'edited through Advanced'});
assert.equal(guard.inspect().state,'unsaved');
assert.equal(attempt().prevented,true);
baseline=copy(current);
guard.start('saved',current);
assert.equal((windowMock.handlers.get('beforeunload')||[]).length,1,'Open/Save do not stack listeners');
baseline=null;revision=0;current=M.fresh();
guard.start('handoff',current);
assert.equal(guard.inspect().warn,true,'source-derived draft is unsaved even without edits');
assert.equal(attempt().prevented,true);
guard.dispose();guard.dispose();
assert.equal(windowMock.handlers.get('beforeunload').length,0,'dispose removes exactly one event');
assert.equal(attempt().prevented,false,'no stale unload handler after disposal');

// Source wiring: no replacement/guard triggers before confirmation, and no
// new click prompts to duplicate the native browser unload dialog.
for(const [action,kind] of [
  ['New scenario','new'],['Fork published case','fork'],
  ['Clone current draft','clone'],['Open saved draft','saved']
]){
  const start=editor.indexOf("confirmDocumentReplacement('"+action+"')");
  assert.ok(start>=0,action+' has established discard confirmation');
  const next=editor.indexOf("draftGuard.start('"+kind+"',spec)",start);
  assert.ok(next>start&&next-start<1100,action+' starts tracking after accepted replacement');
}
assert.match(editor,/draftGuard.start\('handoff',spec\)/);
assert.match(editor,/getCurrent:\(\)=>\{[\s\S]*?mode==='advanced'\)return M.parseAdvanced/);
assert.match(editor,/finally \{savePending=false;\$\('sd-save'\).disabled=false;draftGuard.refresh\(\);\}/);
assert.match(editor,/baseline=M.clone\(toSave\);updateRevision\(\);/);
assert.match(editor,/if\(mode!==target\)resetReadinessViewer\(\)/);
assert.match(editor,/editorGeneration\+\+;resetReadinessViewer\(\);/);
assert.match(editor,/window.addEventListener\('pagehide'/);
assert.match(template,/id="sd-work-state"/);
assert.match(template,/src="\/static\/scenario_draft_guard.js"/);
assert.equal((editor.match(/addEventListener\('beforeunload'/g)||[]).length,0,
  'single lifecycle guard owns all beforeunload handlers');
console.log('Scenario #1333 pristine/new/fork/clone/saved/Advanced, unload cancellation, save races and viewer wiring: PASS');
