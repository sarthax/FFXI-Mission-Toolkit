/* #1403: source-backed, synthetic, browser-independent characterization.
 * These assertions document CURRENT defects; they do not assert remediation.
 * Run: node --test test_fixtures/scenario_shape_1403.test.cjs
 */
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const editor = fs.readFileSync(path.join(root,'gui/static/scenario_developer.js'),'utf8');
const model = fs.readFileSync(path.join(root,'gui/static/scenario_guided_model.js'),'utf8');
function extract(src, name) {
  // Repository functions use two-space indentation; stop at next sibling.
  const begin = src.indexOf('  function '+name+'(');
  assert.notEqual(begin,-1,'missing actual source function '+name);
  const end = src.indexOf('\n  function ',begin+3);
  assert.notEqual(end,-1,'cannot locate end of '+name);
  return src.slice(begin,end);
}
function compile(src, name, params, values) {
  return Function(...params, '"use strict";\n'+extract(src,name)+'\nreturn '+name+';')(...values);
}
function element() {return {value:'',hidden:false,textContent:'',replaceChildren(){},append(){},setAttribute(){}};}
const $ = () => element();
function syntheticSpec(overrides={}) {
  return {schema_version:1,runner:'unassigned',execution_status:'design_only',
    feature_id:'synthetic',case_id:'synthetic',name:'Synthetic',purpose:'',
    rationale:'',behavior:{given:[],when:[],then:[]},preconditions:[],
    cleanup:[],steps:[],assertions:[],observations:[],authoring:{blocking_gaps:[]},
    ...overrides};
}
test('SOURCE REPRO: forked published seed without steps triggers renderSteps TypeError',()=>{
  const spec=syntheticSpec();delete spec.steps;
  const renderSteps=compile(editor,'renderSteps',['spec','$','renderCatalogSteps'],[spec,$,()=>{}]);
  assert.throws(()=>renderSteps(),{name:'TypeError'});
});
test('SOURCE REPRO: wrong-typed cleanup throws during actual Guided render',()=>{
  const spec=syntheticSpec({cleanup:'x'});
  const render=compile(editor,'render',['spec','$','options'],[spec,$,{features:[],observations:[]}]);
  assert.throws(()=>render(),{name:'TypeError'});
});
test('SOURCE REPRO: parseAdvanced accepts schema-valid but wrong-typed cleanup',()=>{
  const parse=compile(model,'parseAdvanced',[],[]);
  const malformed=syntheticSpec({cleanup:'x'});
  assert.equal(parse(JSON.stringify(malformed)).cleanup,'x');
});
test('SOURCE CONTROL: empty arrays pass renderer entry checks',()=>{
  const spec=syntheticSpec();
  const renderSteps=compile(editor,'renderSteps',['spec','$','renderCatalogSteps'],[spec,$,()=>{}]);
  assert.doesNotThrow(()=>renderSteps());
});
test('SOURCE CONTROL: syntax-invalid Advanced JSON rejects without mutating input',()=>{
  const parse=compile(model,'parseAdvanced',[],[]);
  const raw='{"cleanup":';
  assert.throws(()=>parse(raw),SyntaxError);
  assert.equal(raw,'{"cleanup":');
});
test('ACCEPTANCE PENDING: missing steps must be rejected or safely normalized without a TypeError',{todo:'requires separately authorized production implementation'},()=>{
  const spec=syntheticSpec();delete spec.steps;
  const renderSteps=compile(editor,'renderSteps',['spec','$','renderCatalogSteps'],[spec,$,()=>{}]);
  assert.doesNotThrow(()=>renderSteps());
});
test('ACCEPTANCE PENDING: cleanup string must be rejected before Guided render',{todo:'requires separately authorized production implementation'},()=>{
  const parse=compile(model,'parseAdvanced',[],[]);
  assert.throws(()=>parse(JSON.stringify(syntheticSpec({cleanup:'x'}))),/cleanup/i);
});
