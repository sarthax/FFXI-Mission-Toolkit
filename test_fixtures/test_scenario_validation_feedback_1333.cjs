/* #1333 DOM regression: field summary does not rewrite editor values. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
class Element {
  constructor(tag) { this.tag=tag; this.hidden=true; this.children=[]; this.attributes={};
    this.value='unchanged draft content'; this.textContent=''; }
  append(node) { this.children.push(node); }
  replaceChildren() { this.children=[]; }
  setAttribute(name,value) { this.attributes[name]=value; }
  removeAttribute(name) { delete this.attributes[name]; }
}
const fields=new Map([['sd-validation-summary',new Element('section')],
  ...['sd-purpose','sd-given','sd-advanced-json','sd-when','sd-rationale','sd-then','sd-gaps']
    .map(id=>[id,new Element('textarea')])]);
const fakeWindow={document:{
  getElementById:id=>fields.get(id)||null,
  createElement:tag=>new Element(tag)
}};
const source=fs.readFileSync(path.join(__dirname,'../gui/static/scenario_validation_feedback.js'),'utf8');
vm.runInNewContext(source,{window:fakeWindow});
const f=fakeWindow.ScenarioValidationFeedback;
assert.equal(f.show([{field:'purpose',control_id:'sd-purpose',
  message:'Enter a purpose <img src=x onerror=bad()>',required:false},
 {field:'behavior.given',control_id:'sd-given',
  message:'Given required',required:true},
 {field:'authoring',control_id:'sd-advanced-json',
  message:'Inspect metadata',required:true}]),true);
assert.equal(fields.get('sd-validation-summary').hidden,false);
assert.equal(fields.get('sd-validation-summary').children.length,2);
assert.equal(fields.get('sd-purpose').attributes['aria-invalid'],'true');
assert.equal(fields.get('sd-given').value,'unchanged draft content');
assert.equal(fields.get('sd-advanced-json').value,'unchanged draft content');
assert.equal(fields.get('sd-validation-summary').children[1].children[0].children[1].textContent,
  'Enter a purpose <img src=x onerror=bad()>');
f.clear();
assert.equal(fields.get('sd-validation-summary').hidden,true);
assert.equal(fields.get('sd-purpose').attributes['aria-invalid'],undefined);
assert.equal(fields.get('sd-purpose').value,'unchanged draft content');
assert.equal(f.show(null),false);
console.log('validation feedback fake-DOM PASS');


// Verify that the *actual editor* stale-response guard is executable,
// not merely a presentation-only mock. No DOM/network/browser is used.
const editorSource=fs.readFileSync(path.join(__dirname,'../gui/static/scenario_developer.js'),'utf8');
const guard=editorSource.match(/(function validationRequestCurrent\([\s\S]*?\n  \})\n  async function validatePreview\(/);
assert.ok(guard,'editor must keep an explicit stale-response check');
const state={
  editorGeneration:3,
  draft:{purpose:'Original',behavior:{given:['known']}},
  revision:2,
  failRead:false
};
const context={
  editorGeneration:state.editorGeneration,
  current:()=>{if(state.failRead)throw Error('Invalid Advanced JSON');return state.draft;},
  $:id=>{assert.equal(id,'sd-revision');return {value:String(state.revision)};}
};
const isCurrent=vm.runInNewContext('('+guard[1]+')',context);
const original={purpose:'Original',behavior:{given:['known']}};
assert.equal(isCurrent(3,original),true);
assert.equal(isCurrent(3,original,2),true);
assert.equal(isCurrent(3,original,1),false,'revision mismatch blocks stale Save feedback');
state.draft={purpose:'Modified',behavior:{given:['known']}};
assert.equal(isCurrent(3,original),false,'new Guided edit blocks stale Validate feedback');
state.failRead=true;
assert.equal(isCurrent(3,original),false,'invalid Advanced buffer is never overwritten');
state.failRead=false;
state.draft=original;
context.editorGeneration=4;
assert.equal(isCurrent(3,original),false,'replaced draft blocks stale reply');
assert.match(editorSource,/catch\(e\)\{\s*if\(uiRequest!==validationUiRequest \|\| generation!==editorGeneration \|\|\s*!validationRequestCurrent\(generation,input\)\)return/,
  'rejected Validate responses must check original identity before surfacing errors');
assert.match(editorSource,/const isCurrent=submitted!==null &&\s*validationRequestCurrent\(generation,submitted,submittedRevision\)/,
  'rejected Save responses must check generation, contents and revision');
assert.match(editorSource,/if\(Feedback && isCurrent && Array\.isArray\(e\.validationErrors\)\)/,
  'stale field errors must not paint another draft');
console.log('validation feedback stale-response guard PASS');

assert.match(editorSource,/let validationUiRequest = 0;/,
  'a single UI request sequence must order Validate and Save');
assert.match(editorSource,/if\(uiRequest!==validationUiRequest\)return; \/\/ previous request cannot hide\/clear newer UI/,
  'outer Validate catch must skip stale hide, Feedback.show(undefined) and status');
assert.match(editorSource,/if\(uiRequest!==validationUiRequest \|\| \(submitted!==null && !isCurrent\)\)\s*return;/,
  'stale Save catch must not clear current Validate feedback');
