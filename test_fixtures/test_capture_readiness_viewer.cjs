/* Synthetic, no browser/network/GitHub/DSP. Tests actual optional DOM presenter. */
'use strict';
const assert=require('node:assert/strict');
const V=require('../gui/static/scenario_readiness_viewer.js');
const examples=require('./r7_capture_readiness_authoring_projection_synthetic.json');
class Element {
  constructor(tag) {this.tag=tag;this.children=[];this.textContent='';this.events={};this.files=[];this.disabled=false;this.type='';}
  append(...xs){this.children.push(...xs);}
  replaceChildren(...xs){this.children=[...xs];}
  addEventListener(type,fn){this.events[type]=fn;}
  dispatch(type){return this.events[type]();}
}
global.document={createElement:tag=>new Element(tag)};
function model(item) {
  const p=item.read_only_projection;
  return {
    contract:'read_only_paired_capture_readiness_view_v1_NONCANONICAL',
    capture_id:p.capture_id,
    pair_integrity:'BOTH_INDEXED_PROJECTIONS_RECOMPUTED_FROM_SELECTED_REVIEW',
    original_handoff_projection_sha256:'a'.repeat(64),
    indexed_observation_projection_sha256:'b'.repeat(64),
    original_capture_authenticated:false,
    parser_decoder_authenticated:false,source_bytes_rehashed:false,
    automatic_import:false,save_allowed:false,approved_for_execution:false,
    execution_enabled:false,canonical_step_associations:'UNASSIGNED',
    scenario_specification:null,normative_expected:null,verdict:'UNKNOWN',
    source_integrity:{state:p.source_compatibility_state,issues:p.source_provenance_issues},
    source_compatibility_state:p.source_compatibility_state,
    source_provenance_issues:p.source_provenance_issues,
    security_notice:'SOURCE NOT AUTHENTICATED; <script>ALWAYS_TEXT_NOT_HTML</script>',
    steps:p.steps
  };
}
const unknown=model(examples.samples[0]),blocked=model(examples.samples[1]);
const original=JSON.stringify([unknown,blocked]);
const root=new Element('main');
assert.equal(V.verify(unknown),unknown);
assert.equal(V.verify(blocked),blocked);
V.render(root,unknown);
assert.equal(root.children.length,1);
function plainText(node) {
  return [node.textContent,...node.children.flatMap(plainText)].join(' ');
}
const printed=plainText(root);
assert.match(printed,/UNKNOWN/);
assert.match(printed,/job_state/);
assert.match(printed,/UNAPPROVED/);
assert.match(printed,/<script>ALWAYS_TEXT_NOT_HTML<\/script>/);
V.render(root,blocked);
assert.match(plainText(root),/BLOCKED/);
assert.match(plainText(root),/mob_state/);
assert.match(plainText(root),/ACCEPT/);
assert.equal(JSON.stringify([unknown,blocked]),original);
const selected=structuredClone(unknown);
selected.steps[0].reviewer_step_decision_selected={
  decision:'ACCEPT',note:'Observation only; expected oracle remains UNAPPROVED'
};
selected.steps[0].identity_confidence[0].review_decision_selected={
  decision:'ACCEPT',note:'Identity label chosen but unverified'
};
V.render(root,selected);
assert.match(plainText(root),/Selected reviewed-decision export CHOICE \(not an oracle\): ACCEPT/);
assert.match(plainText(root),/selected reviewer CHOICE ACCEPT/);
assert.match(plainText(root),/UNAPPROVED/);
assert.equal(V.verify(selected).execution_enabled,false);
for(const [field,value] of [
  ['execution_enabled',true],['approved_for_execution',true],
  ['original_capture_authenticated',true],['parser_decoder_authenticated',true],
  ['automatic_import',true],['scenario_specification',{}],
  ['canonical_step_associations','VERIFIED']
]){
  const bad=structuredClone(unknown);bad[field]=value;
  assert.throws(()=>V.verify(bad),/Untrusted readiness/);
}
for(const [field,value] of [
  ['oracle_approval_state','APPROVED'],
  ['canonical_step_id','OBS-S001'],
  ['execution_enabled',true],['verdict','PASS']
]){
  const bad=structuredClone(unknown);bad.steps[0][field]=value;
  assert.throws(()=>V.render(root,bad),/attempted canonical or oracle/);
}

for(const mutate of [
  m=>{m.steps[0].original_evidence_refs.push(m.steps[0].original_evidence_refs[0]);},
  m=>{m.steps[0].indexed_evidence_provenance[0].capture_id=999;},
  m=>{m.steps[0].canonical_source_association.source_refs='forged-ref';},
  m=>{m.steps[0].identity_confidence[0].source_identity_verified=true;},
  m=>{m.steps[0].missing_readbacks[0].permission_granted=true;},
  m=>{m.steps[0].missing_readbacks[0].status='VERIFIED';},
]){
  const bad=structuredClone(unknown);mutate(bad);
  assert.throws(()=>V.verify(bad),/attempted/);
}
for(const mutate of [
  m=>{m.steps[0].indexed_evidence_provenance[0].source_file_claims[0].indexed_digests_rehashed=true;},
  m=>{m.steps[0].indexed_evidence_provenance[0].source_file_claims[0].decoder_version='FORGED';},
]){
  const bad=structuredClone(blocked);mutate(bad);
  assert.throws(()=>V.verify(bad),/attempted source/);
}

async function run(){
  const host=new Element('main');
  let wait=null;
  const view=V.mount(host,()=>new Promise(resolve=>{wait=resolve;}));
  assert.match(plainText(host),/Select TWO local JSON files/);
  const file=txt=>({size:txt.length,text:async()=>txt});
  view.review.files=[file('{"review":1}')];
  view.advisory.files=[file('{"sidecar":1}')];
  view.review.dispatch('change');
  const promise=view.inspectButton.dispatch('click');
  // Wait for file.text promises so injected inspector is pending.
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  assert.equal(typeof wait,'function');
  view.advisory.files=[file('{"different":1}')];
  view.advisory.dispatch('change');
  wait(unknown);await promise;
  assert.equal(view.output.children.length,0);
  assert.match(view.status.textContent,/Selection changed/);
  // Click again with the selected file; authorized verifier returns UNKNOWN.
  const next=view.inspectButton.dispatch('click');
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  wait(unknown);await next;
  assert.equal(view.output.children.length,1);
  assert.match(view.status.textContent,/UNVERIFIED READ-ONLY/);
  assert.match(plainText(view.output),/UNKNOWN/);
  // A verifier must refuse a forged result (never show it).
  const bad=structuredClone(blocked);bad.automatic_import=true;
  const final=view.inspectButton.dispatch('click');
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  wait(bad);await final;
  assert.equal(view.output.children.length,0);
  assert.match(view.status.textContent,/Pair NOT accepted/);
  // Agent B must dispose when navigating New/Open/Fork/Clone. Even a
  // successful old response must never resurrect a closed advisory panel.
  const closedHost=new Element('main');
  let complete=null;
  const closed=V.mount(closedHost,()=>new Promise(resolve=>{complete=resolve;}));
  closed.review.files=[file('{"original":true}')];
  closed.advisory.files=[file('{"advisory":true}')];
  const pending=closed.inspectButton.dispatch('click');
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  assert.equal(typeof complete,'function');
  closed.dispose();
  complete(unknown);await pending;
  assert.equal(closed.output.children.length,0);
  assert.equal(closed.inspectButton.disabled,true);
  assert.match(closed.status.textContent,/Viewer closed/);
  await closed.inspectButton.dispatch('click');
  assert.equal(closed.output.children.length,0);
  // No save/import/GM controls are provided by this module.
  assert.doesNotMatch(plainText(host),/Save design-only draft|Execute test|Send GM/);
  console.log('R7 independent read-only readiness panel, two-file guard and stale-selection DOM: PASS');
}
run().catch(err=>{console.error(err);process.exitCode=1;});
