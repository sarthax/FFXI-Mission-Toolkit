/* #1362 synthetic asynchronous real click-handler regression.
 * Runs actual Scenario Developer + Guided Model + Validation Feedback scripts in
 * a bounded fake DOM with two independently deferred HTTP responses.
 * No Toolkit server, filesystem data store, browser, gameplay or credential use.
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
async function run() {
  // Complete startup options request before the first synthetic interaction.
  for(let i=0;i<8;i++)await Promise.resolve();
  assert.ok((get('sd-feature').options||[]).length>0,'editor initialized');
  if(combinedGuardPresent) {
    assert.equal((lifecycle.get('beforeunload')||[]).length,1,
      'combined editor must register exactly one native unsaved-work listener');
    assert.equal(get('sd-work-state').dataset.state,'pristine',
      'real guard starts with a pristine unsaved-by-default design');
  }

  // Two actual clicks, two independent fetch promises. V2 422 settles first.
  get('sd-purpose').value='synthetic V1';
  const v1=click('sd-validate');
  get('sd-purpose').value='synthetic V2';
  const v2=click('sd-validate');
  assert.equal(requests.length,2);
  settle(1,422,invalid('invalid purpose V2'));await v2;
  assert.equal(get('sd-validation-summary').hidden,false);
  assert.equal(get('sd-purpose').attributes['aria-invalid'],'true');
  const newest=ui();
  settle(0,422,invalid('invalid purpose V1'));await v1;
  assert.deepEqual(ui(),newest,'stale V1 rejection must not hide/clear newer V2 422');

  // V2 success before V1 rejection, and no older callback hides newer preview.
  get('sd-purpose').value='synthetic preview V1';
  const v3=click('sd-validate');
  get('sd-purpose').value='synthetic preview V2';
  const v4=click('sd-validate');
  settle(3,200,valid('newest preview'));await v4;
  assert.equal(get('sd-preview').hidden,false);
  assert.equal(get('sd-validation-summary').hidden,true);
  const newestPreview=ui();
  settle(2,422,invalid('obsolete V1 failure'));await v3;
  assert.deepEqual(ui(),newestPreview,'stale V1 422 must not hide current V2 success');

  // Old successful preview cannot overwrite newer V2 rejected errors either.
  get('sd-purpose').value='synthetic success V1';
  const v5=click('sd-validate');
  get('sd-purpose').value='synthetic error V2';
  const v6=click('sd-validate');
  settle(5,422,invalid('invalid current V2'));await v6;
  const newerError=ui();
  settle(4,200,valid('stale preview'));await v5;
  assert.deepEqual(ui(),newerError,'stale V1 200 must not erase current V2 422');

  // Stale Save preflight must be a UI no-op after a later Validate.
  get('sd-token').value='synthetic-test-token-only-not-a-real-credential-0000';
  get('sd-purpose').value='synthetic Save S1';
  const save=click('sd-save');
  assert.equal(get('sd-save').disabled,true,'Save pending');
  if(combinedGuardPresent) {
    assert.equal(beforeUnloadAttempt().prevented,true,
      'real guard protects in-flight Save against unload');
  }
  get('sd-purpose').value='newer Validate V2';
  const current=click('sd-validate');
  settle(7,422,invalid('newer V2 422'));await current;
  const validError=ui();
  settle(6,422,invalid('stale S1 preflight'));await save;
  assert.deepEqual(ui(),validError,'stale Save must not clear newer validation');
  assert.equal(get('sd-save').disabled,false,'Save controls restored');
  if(combinedGuardPresent) {
    assert.equal(get('sd-work-state').dataset.state,'unsaved',
      'failed Save remains dirty with real ScenarioDraftGuard');
    assert.equal(beforeUnloadAttempt().prevented,true,
      'failed Save retains native unsaved-work protection');
  }
  assert.equal(draftRequests.length,0,
    'superseded preflight MUST NOT dispatch a draft write');

  // Save rejected after a new successful Validate preserves the preview/status.
  get('sd-purpose').value='Save S2';
  const save2=click('sd-save');
  get('sd-purpose').value='newer success V2';
  const v7=click('sd-validate');
  settle(9,200,valid('V2 after Save'));await v7;
  const afterValidate=ui();
  settle(8,422,invalid('old Save 422'));await save2;
  assert.deepEqual(ui(),afterValidate,'stale Save must not clear later preview');

  // Even with identical draft snapshots, newest response owns the screen.
  // A generation/content-only check cannot protect this case by itself.
  get('sd-purpose').value='unchanged between two validations';
  const identicalOld=click('sd-validate');
  const identicalNew=click('sd-validate');
  assert.equal(requests.length,12);
  settle(11,422,invalid('newer identical-input error'));await identicalNew;
  const identicalNewUi=ui();
  settle(10,200,valid('older identical-input success'));await identicalOld;
  assert.deepEqual(ui(),identicalNewUi,
    'old successful response for SAME INPUT must not clear later current errors');

  // Save preflight was authorized for a synthetic-only draft store request;
  // simulate a later 403 from that already in-flight Save after newer Validate.
  get('sd-purpose').value='in-flight scratch save';
  const inFlightSave=click('sd-save');
  assert.equal(requests.length,13);
  settle(12,200,{...valid('save preview'),
    canonical_specification:requests[12].request.specification});
  for(let n=0;n<8;n++)await Promise.resolve();
  assert.equal(draftRequests.length,1,'only one synthetic draft POST was queued');
  get('sd-purpose').value='current result after save dispatch';
  const newerValidation=click('sd-validate');
  assert.equal(requests.length,14);
  settle(13,422,invalid('new current error'));await newerValidation;
  const beforeDelayedSave=ui();
  draftRequests[0].resolve({ok:false,status:403,
    json:async()=>({detail:'Operator permission denied'})});
  await inFlightSave;
  assert.deepEqual(ui(),beforeDelayedSave,
    'delayed rejected draft POST must not erase newer validation UI');
  assert.equal(get('sd-save').disabled,false,'Save finally always releases controls');
  assert.equal(draftRequests.length,1,'no duplicate synthetic draft Save');

  // Invalid Advanced buffer is not parsed/replaced by a delayed old 422.
  await click('sd-advanced');
  const advancedBefore=JSON.stringify({...requests[13].request.specification,purpose:'source-only'});
  get('sd-advanced-json').value=advancedBefore;
  const advancedReq=click('sd-validate');
  const bad='{broken : [';
  get('sd-advanced-json').value=bad;
  settle(14,422,invalid('old Advanced 422'));await advancedReq;
  assert.equal(get('sd-advanced-json').value,bad,'invalid Advanced bytes preserved');
  assert.equal(get('sd-revision').value,'0','unsaved draft revision preserved');
  if(combinedGuardPresent) {
    assert.equal(get('sd-work-state').dataset.state,'unsaved',
      'invalid Advanced JSON cannot clear dirty guard state');
    assert.equal(beforeUnloadAttempt().prevented,true,
      'native unload guard must survive out-of-order validation and invalid JSON');
    assert.equal((lifecycle.get('beforeunload')||[]).length,1,
      'Validate/Save callbacks must not register duplicate native unload listeners');
  }
  assert.equal(network.some(x=>x.path.includes('/launch')),false);
  console.log('#1362 actual click handlers with deferred V2-before-V1 Validate, Save, preview and invalid Advanced: PASS');
  console.log(combinedGuardPresent
    ? '#1378 combined REAL ScenarioDraftGuard pending/invalid/unload coverage: PASS'
    : '#1378 E-only fixture: ScenarioDraftGuard absent, combined guard checks NOT_RUN');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
