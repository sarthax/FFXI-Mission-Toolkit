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
