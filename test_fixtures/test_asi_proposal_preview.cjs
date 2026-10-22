/* Synthetic-only #1325 noncanonical proposal-review safety / fake DOM.
 * No local browser, MCP, database, network, editor imports or execution.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const P=require('../gui/static/scenario_proposal_preview.js');
const pair=JSON.parse(fs.readFileSync('test_fixtures/asi_proposal_preview_synthetic.json','utf8'));
const deep=x=>JSON.parse(JSON.stringify(x));
const {baseline,proposal}=pair;
assert.equal(pair.fixture_kind,'SYNTHETIC_ONLY_NO_RECORDED_GAMEPLAY');

const before=JSON.stringify(pair);
const view=P.check(baseline,proposal);
assert.equal(view.contract,P.CONTRACT);
assert.equal(view.scenario.case_id,baseline.specification.case_id);
assert.equal(view.base_revision,3);
assert.equal(view.execution_enabled,false);
assert.equal(view.save_allowed,false);
assert.equal(view.approved_expected,false);
assert.equal(view.normative_expected,null);
assert.equal(view.reviewer_action_enabled,false);
assert.equal(view.canonical_case_step_approval,'UNASSIGNED');
assert.equal(view.source_authenticated,false);
assert.match(view.blockers.join(' | '),/UNAPPROVED/);
assert.match(view.blockers.join(' | '),/BLOCKED/);
assert.equal(JSON.stringify(pair),before,'never mutate baseline/spec/proposal');

function refuse(mutator,needle){
  const a=deep(baseline),b=deep(proposal);
  mutator(a,b);
  assert.throws(()=>P.check(a,b),needle);
}
refuse((a,b)=>b.base.revision=2,/STALE_BASE_REVISION/);
refuse((a,b)=>{a.spec_digest_claim='a'.repeat(64);},/CONFLICTING_BASE_DIGEST/);
refuse((a,b)=>b.scenario.case_id='ANOTHER-SYNTH-CASE',/different canonical case/);
refuse((a,b)=>b.changes[0].before='stale input',/CONFLICTING_BEFORE_VALUE/);
refuse((a,b)=>b.changes.push(deep(b.changes[0])),/Conflicting or duplicated/);
refuse((a,b)=>b.changes.push({path:'/runner',before:'unassigned',after:'xi-test'}),/protected/);
refuse((a,b)=>b.changes[0].path='/contract_v2/oracles/0',/protected/);
refuse((a,b)=>b.approved_expected=true,/cannot claim oracle approval/);
refuse((a,b)=>b.execution_enabled=true,/cannot claim oracle approval/);
refuse((a,b)=>b.changes[0].after=b.changes[0].before,/No-op/);
refuse((a,b)=>b.changes=[],/1–12/);
refuse((a,b)=>b.reason='',/cannot claim oracle approval/);
refuse((a,b)=>b.extra_field='save',/Unexpected or missing/);
refuse((a,b)=>b.source_refs=['SRC','SRC'],/duplicate source_refs/);
refuse((a,b)=>b.feature_trace_refs=[1],/Invalid or duplicate/);
refuse((a,b)=>b.expected_candidates=[{approved:true}],/Invalid unapproved/);
refuse((a,b)=>a.revision=-1,/Invalid selected baseline revision/);
refuse((a,b)=>a.specification.schema_version=3,/canonical v1/);
assert.throws(()=>P.check(baseline,proposal,['PROP-SYNTH-01']),/Duplicate proposal/);
const noSources=deep(proposal);noSources.source_refs=[];noSources.feature_trace_refs=[];
const missing=P.check(baseline,noSources);
assert.match(missing.blockers.join(' | '),/no independently referenced source/);
assert.match(missing.blockers.join(' | '),/no Feature Trace citations/);
const duplicates=deep(proposal);duplicates.duplicate_scenario_ids=['SYNTH-OTHER-CASE'];
assert.match(P.check(baseline,duplicates).blockers.join(' | '),/DUPLICATE_CANDIDATE/);

class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.textContent='';this.listeners={};
    this.files=[];this.disabled=false;this.type='';this.accept='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  addEventListener(type,handler){this.listeners[type]=handler;}
  dispatch(type){return this.listeners[type]?.();}
}
global.document={createElement:tag=>new Element(tag)};
function printed(node){return [node.textContent,...node.children.map(printed)].join(' ');}
const parent=new Element('main');
P.render(parent,view);
assert.match(printed(parent),/BEFORE \(selected baseline\)/);
assert.match(printed(parent),/AFTER \(unapproved candidate\)/);
assert.match(printed(parent),/Source declarations/);
assert.match(printed(parent),/Feature Trace claims/);
assert.match(printed(parent),/Missing observations/);
assert.match(printed(parent),/NOT APPROVED/);
assert.doesNotMatch(printed(parent),/Save design-only draft|Execute test|Accept proposal/);
const attack=deep(proposal);attack.reason='<script>FORGED_HTML</script>';
P.render(parent,P.check(baseline,attack));
assert.match(printed(parent),/<script>FORGED_HTML<\/script>/);
assert.equal(parent.children[0].tagName,'section','no markup interpolated');
assert.equal(JSON.stringify(pair),before,'DOM cannot mutate canonical input');

const file=value=>({size:Buffer.byteLength(value),text:async()=>value});
const baselineFile=file(JSON.stringify(baseline)),proposalFile=file(JSON.stringify(proposal));
async function run(){
  const container=new Element('main'),ui=P.mount(container);
  assert.match(printed(container),/two|baseline/i);
  ui.baseline.files=[baselineFile];ui.proposal.files=[proposalFile];
  await ui.go.dispatch('click');
  assert.match(printed(ui.output),/UNAPPROVED/);
  assert.match(ui.status.textContent,/not imported or approved/);

  // Invalid selection fails closed and clears prior accepted preview.
  ui.proposal.files=[file('{"broken":')];ui.proposal.dispatch('change');
  await ui.go.dispatch('click');
  assert.equal(ui.output.children.length,0);
  assert.match(ui.status.textContent,/Proposal refused/);

  // Changing a selected file while its read is pending invalidates result.
  let release;
  const slow={size:10,text:()=>new Promise(resolve=>{release=resolve;})};
  ui.baseline.files=[slow];ui.proposal.files=[proposalFile];
  const inflight=ui.go.dispatch('click');
  ui.baseline.dispatch('change');
  ui.baseline.files=[baselineFile];
  release(JSON.stringify(baseline));
  await inflight;
  assert.equal(ui.output.children.length,0);

  // Disposing a pending viewer (cancelled navigation) never resurrects it.
  const detached=P.mount(new Element('main'));let finish;
  detached.baseline.files=[{size:10,text:()=>new Promise(resolve=>{finish=resolve;})}];
  detached.proposal.files=[proposalFile];
  const p=detached.go.dispatch('click');
  detached.dispose();
  finish(JSON.stringify(baseline));
  await p;
  assert.equal(detached.output.children.length,0);
  assert.equal(detached.go.disabled,true);
  assert.match(detached.status.textContent,/closed/);
  console.log('ASI proposal read-only diff, conflicts, stale/duplicate, unsafe fields and DOM: PASS');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
