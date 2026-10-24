/* #1387 TEST ONLY — delayed successful Save POST200, actual combined E+B editor.
 * Fake DOM scaffolding copied from E #1362 at exact test-only #1385 parent SHA.
 * The source fixture itself is NEVER altered. All requests intercepted in memory.
 * No real browser, token, runtime API, persistent DB, launcher or gameplay.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../gui/static/',name),'utf8');

class Element {
  constructor(tag='div') {
    this.tag=tag; this.children=[]; this.listeners=new Map(); this.attributes={};
    this.dataset={}; this.hidden=false; this.disabled=false; this._value=undefined;
    this.textContent=''; this.selected=false; this.checked=false; this.files=[];
  }
  get value() {
    if(this._value!==undefined)return this._value;
    if(this.tag==='select')return this.children.find(x=>x.selected)?.value || this.children[0]?.value || '';
    return '';
  }
  set value(value) {this._value=value;}
  get selectedOptions() {return this.children.filter(x=>x.selected);}
  get options() {return this.children;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  replaceChild(newChild,oldChild){
    const i=this.children.indexOf(oldChild);
    if(i>=0)this.children.splice(i,1,newChild);
  }
  addEventListener(type,fn){const list=this.listeners.get(type)||[];list.push(fn);this.listeners.set(type,list);}
  removeEventListener(type,fn){this.listeners.set(type,(this.listeners.get(type)||[]).filter(x=>x!==fn));}
  setAttribute(name,value){this.attributes[name]=String(value);}
  removeAttribute(name){delete this.attributes[name];}
  querySelectorAll(){return [];}
  querySelector(){return null;}
}
const dom=new Map();
const selects=new Set(['sd-feature','sd-observations','sd-catalog-step','sd-seed-select','sd-drafts']);
const get=id=>{
  if(!dom.has(id))dom.set(id,new Element(selects.has(id)?'select':'div'));
  return dom.get(id);
};
get('sd-revision').value='0';
get('sd-purpose').value='';
const document={
  getElementById:get,
  createElement:tag=>new Element(tag),
  createTextNode:value=>({textContent:String(value)})
};
// The standalone E branch has no Agent B guard file. When history-preserved
// #1335+#1337 integration adds it, load the REAL guard (not a no-op stub) and
// exercise its unsaved/pending/unload contract alongside the deferred callbacks.
const lifecycle=new Map();
const win={
  document,location:{search:''},confirm:()=>true,
  addEventListener(type,fn){
    const handlers=lifecycle.get(type)||[];
    handlers.push(fn);lifecycle.set(type,handlers);
  },
  removeEventListener(type,fn){
    lifecycle.set(type,(lifecycle.get(type)||[]).filter(x=>x!==fn));
  },
  ScenarioGuidedModel:require('../gui/static/scenario_guided_model.js'),
  ScenarioContractV2View:require('../gui/static/scenario_contract_v2_view.js'),
  ScenarioReadinessViewer:{mount:()=>({dispose(){}})}
};
const guardPath=path.join(__dirname,'../gui/static/scenario_draft_guard.js');
const combinedGuardPresent=fs.existsSync(guardPath);
if(combinedGuardPresent) {
  win.ScenarioDraftGuard=require(guardPath);
  assert.equal(typeof win.ScenarioDraftGuard.create,'function',
    'combined editor must use real draft-guard implementation');
}
function beforeUnloadAttempt() {
  const e={prevented:false,returnValue:undefined,preventDefault(){this.prevented=true;}};
  for(const fn of lifecycle.get('beforeunload')||[])fn(e);
  return e;
}
vm.runInNewContext(read('scenario_validation_feedback.js'),{window:win,document});
const feedback=win.ScenarioValidationFeedback;
const requests=[];
const draftRequests=[]; // synthetic POST interception; never contacts a server
const network=[];
function fetch(path,options={}) {
  network.push({path,method:options.method||'GET'});
  if(path==='/scenario-developer/options')
    return Promise.resolve({ok:true,status:200,json:async()=>({
      features:[{id:'inventory_observation',name:'Synthetic inventory'}],
      observations:['client_bag'],operations:['nonempty'],
      catalog_status:'synthetic',catalog_note:'no live data'
    })});
  if(path==='/scenario-developer/validate')
    return new Promise(resolve=>requests.push({resolve,path,request:JSON.parse(options.body)}));
  if(path==='/feature-testing/builder/drafts' && options.method==='POST')
    return new Promise(resolve=>draftRequests.push({resolve,path,request:JSON.parse(options.body)}));
  throw Error('UNEXPECTED network call: '+path);
}
const context={window:win,document,fetch,URLSearchParams,console,Set,Error};
vm.runInNewContext(read('scenario_developer.js'),context,{filename:'scenario_developer.js'});
const click=id=>{
  const handlers=get(id).listeners.get('click')||[];
  assert.equal(handlers.length,1,'one bound click handler for '+id);
  return handlers[0]({preventDefault(){}});
};
function settle(index,status,payload) {
  const item=requests[index];
  assert.ok(item,'pending synthetic response '+index);
  item.resolve({ok:status>=200&&status<300,status,json:async()=>payload});
}
const invalid=message=>({detail:{message:'Canonical scenario validation rejected',
  canonical_error:message,errors:[
    {field:'purpose',control_id:'sd-purpose',
      message:'Purpose required',required:true},
    {field:'behavior.given',control_id:'sd-given',
      message:'Given required',required:true}
  ]}});
const valid=label=>({
  preview:{
    title:label,purpose:'synthetic-only',maturity:'DESIGN_ONLY',
    independent_verification:'NOT_TESTED',catalog_identity:'SYNTHETIC',
    behavior:{given:['synthetic'],when:['synthetic'],then:['UNKNOWN']},
    steps:[],unmapped_assertions:[],unresolved_expected_steps:[],blocking_gaps:[]
  },
  reader_view:{available:false},contract_v2_compatibility:null,
  contract_v2_source_attribution:null,warnings:['not runnable']
});
const ui=()=>({
  summaryHidden:get('sd-validation-summary').hidden,
  summaryCount:get('sd-validation-summary').children.length,
  purposeInvalid:get('sd-purpose').attributes['aria-invalid'],
  result:get('sd-result').textContent,
  previewHidden:get('sd-preview').hidden,
  previewTitle:get('sd-preview').children[0]?.textContent,
  revision:get('sd-revision').value,
  purpose:get('sd-purpose').value,
  advanced:get('sd-advanced-json').value
});

const OriginalGuard=win.ScenarioDraftGuard;
assert.equal(combinedGuardPresent,true,'#1387 requires B real guard, not E-only mode');
assert.equal(typeof OriginalGuard?.create,'function','real draft guard module must be present');
function input(id,value) {
  get(id).value=value;
  for(const fn of get(id).listeners.get('input')||[])fn({target:get(id)});
}
function expectGuard(state,warn,label) {
  assert.equal(get('sd-work-state').dataset.state,state,label+' status');
  assert.equal(beforeUnloadAttempt().prevented,warn,label+' beforeunload');
}
async function flush() {
  for(let i=0;i<12;i++)await Promise.resolve();
}
function replyDraft(index,submitted,revision) {
  assert.ok(draftRequests[index],'synthetic draft POST #'+index+' queued');
  draftRequests[index].resolve({ok:true,status:200,
    json:async()=>({feature_id:submitted.feature_id,case_id:submitted.case_id,revision})});
}
function showUnchanged(previous,label) {
  assert.equal(get('sd-result').textContent,previous.result,label+' newer status');
  assert.equal(get('sd-validation-summary').hidden,previous.summaryHidden,label+' newer field summary visibility');
  assert.equal(get('sd-purpose').attributes['aria-invalid'],previous.purposeInvalid,label+' field marker');
  assert.equal(get('sd-preview').hidden,previous.previewHidden,label+' preview visibility');
  assert.equal(get('sd-preview').children[0]?.textContent,previous.previewTitle,label+' preview title');
}
async function runSave200() {
  await flush(); // initial synthetic /scenario-developer/options render
  assert.ok(get('sd-feature').options.length,'editor initialized from fake options');
  assert.equal((lifecycle.get('beforeunload')||[]).length,1,'exactly one REAL beforeunload listener');
  get('sd-token').value='synthetic-only-fake-token-not-an-operator-secret';
  input('sd-case','SYNTH_1387_DELAYS');
  input('sd-purpose','snapshot S1 for SAVE'); 
  expectGuard('unsaved',true,'initial modified draft');

  // S1: canonical preflight accepted and draft POST dispatched, then a DIFFERENT
  // canonical Validate V2 rejects a newer edit before late draft POST200 arrives.
  const save1=click('sd-save');
  expectGuard('unsaved',true,'save1 pending');
  assert.equal(requests.length,1);
  const s1=requests[0].request.specification;
  assert.equal(s1.purpose,'snapshot S1 for SAVE');
  settle(0,200,{...valid('S1 server preflight'),canonical_specification:s1});
  await flush();
  assert.equal(draftRequests.length,1,'one S1 draft POST, no implicit retries');
  assert.equal(draftRequests[0].request.expected_revision,0);
  assert.equal(draftRequests[0].request.specification.purpose,s1.purpose);

  input('sd-purpose','newer edited S2 after POST');
  const validation1=click('sd-validate');
  assert.equal(requests.length,2);
  settle(1,422,invalid('newer S2 field rejection'));await validation1;
  const latestError=ui();
  assert.equal(latestError.summaryHidden,false);
  assert.equal(latestError.purposeInvalid,'true');
  replyDraft(0,s1,1);await save1;
  assert.equal(get('sd-revision').value,1,'late successful S1 POST advances persisted revision');
  assert.equal(get('sd-purpose').value,'newer edited S2 after POST','newer draft bytes preserved');
  showUnchanged(latestError,'late S1 POST200');
  expectGuard('unsaved',true,'late S1 POST200 leaves newer edits dirty');
  assert.equal(draftRequests.length,1,'late S1 response never dispatches another POST');

  // S2: save a snapshot at EXPECTED revision 1; a still newer editor edit
  // validates successfully before the persisted POST200 resolves. The old
  // save must attach revision 2 to the same document but preserve the newer
  // preview/status and retain the dirty/leave warning for unsaved latest text.
  const save2=click('sd-save');
  assert.equal(requests.length,3);
  const s2=requests[2].request.specification;
  assert.equal(s2.purpose,'newer edited S2 after POST');
  settle(2,200,{...valid('S2 server preflight'),canonical_specification:s2});
  await flush();
  assert.equal(draftRequests.length,2);
  assert.equal(draftRequests[1].request.expected_revision,1,
    'second write must use new persisted CAS revision, not initial revision 0');
  input('sd-purpose','latest S3 not yet persisted');
  const validation2=click('sd-validate');
  assert.equal(requests.length,4);
  settle(3,200,valid('newest S3 preview'));await validation2;
  const latestPreview=ui();
  assert.equal(latestPreview.previewHidden,false);
  replyDraft(1,s2,2);await save2;
  assert.equal(get('sd-revision').value,2,'S2 successful POST advances saved CAS revision');
  assert.equal(get('sd-purpose').value,'latest S3 not yet persisted');
  showUnchanged(latestPreview,'late S2 POST200');
  expectGuard('unsaved',true,'late S2 success cannot mark newer S3 changes saved');

  // S3: save the exact latest snapshot without concurrent changes. This must
  // clear dirty, advance baseline to S3 and remove the native unload warning.
  const save3=click('sd-save');
  assert.equal(requests.length,5);
  const s3=requests[4].request.specification;
  assert.equal(s3.purpose,'latest S3 not yet persisted');
  settle(4,200,{...valid('S3 server preflight'),canonical_specification:s3});
  await flush();
  assert.equal(draftRequests.length,3);
  assert.equal(draftRequests[2].request.expected_revision,2);
  replyDraft(2,s3,3);await save3;
  assert.equal(get('sd-revision').value,3);
  expectGuard('saved',false,'unchanged S3 POST200 correctly saves baseline');
  assert.match(get('sd-revision-state').textContent,/Saved revision 3/);
  assert.match(get('sd-result').textContent,/Saved DESIGN_ONLY/);

  // S4: optimistic accepted POST but the RESPONSE identity conflicts with
  // submitted canonical snapshot. Reject revision attachment and baseline
  // adoption. This is deliberately a mock protocol violation, not a server call.
  input('sd-purpose','S4 awaiting mismatched identity');
  const save4=click('sd-save');
  assert.equal(requests.length,6);
  const s4=requests[5].request.specification;
  settle(5,200,{...valid('S4 server preflight'),canonical_specification:s4});
  await flush();
  assert.equal(draftRequests.length,4);
  assert.equal(draftRequests[3].request.expected_revision,3);
  draftRequests[3].resolve({ok:true,status:200,json:async()=>({
    feature_id:s4.feature_id,case_id:'DIFFERENT_SYNTHETIC_CASE',revision:99
  })});
  await save4;
  assert.equal(get('sd-revision').value,3,'mismatched identity may not attach wrong revision');
  assert.equal(get('sd-purpose').value,s4.purpose,'mismatched Save retains buffer');
  expectGuard('unsaved',true,'mismatched identity remains dirty');
  assert.match(get('sd-result').textContent,/unexpected saved document identity/);
  assert.equal((lifecycle.get('beforeunload')||[]).length,1,'no new unload listener');
  assert.equal(draftRequests.length,4,'no duplicate draft POST');
  assert.equal(network.filter(x=>x.path.includes('/launch')).length,0,
    'no execution dispatch');
  assert.equal(network.filter(x=>x.path==='/feature-testing/builder/drafts'&&x.method==='POST').length,4,
    'exactly the four intercepted mock persistence requests');
  console.log('#1387 TEST ONLY: REAL B guard + actual combined E/B clicks delayed successful POST200; latest feedback, CAS/baseline, dirty/unload, mismatched identity: PASS');
}
runSave200().catch(err=>{console.error(err);process.exitCode=1;});
