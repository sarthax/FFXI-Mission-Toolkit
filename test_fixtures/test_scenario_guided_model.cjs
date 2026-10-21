/* Synthetic-only browser-independent model acceptance for #1261. */
const assert = require('node:assert/strict');
const M = require('../gui/static/scenario_guided_model.js');

const spec = M.fresh();
assert.equal(spec.schema_version, 1);
assert.equal(spec.runner, 'unassigned');
assert.equal(spec.execution_status, 'design_only');
assert.equal(spec.authoring.review_required, true);

const firstId = spec.steps[0].id;
const withStep = M.addStep(spec);
assert.equal(withStep.steps.length, 2);
assert.equal(spec.steps.length, 1);
assert.equal(withStep.steps[0].id, firstId);
const secondId = withStep.steps[1].id;
assert.notEqual(secondId, firstId);
const moved = M.moveStep(withStep, 1, -1);
assert.deepEqual(moved.steps.map(s => s.id), [secondId, firstId]);
const edited = M.clone(moved);
edited.steps[1].title = 'Synthetic revised content';
assert.equal(edited.steps[1].id, firstId);
const roundtrip = M.parseAdvanced(JSON.stringify(edited));
assert.deepEqual(roundtrip, edited);
assert.deepEqual(M.parseAdvanced(JSON.stringify(roundtrip)), edited);

const broken = M.clone(edited);
broken.steps[1].id = broken.steps[0].id;
broken.steps[0].assertion_ids = ['invented_assertion'];
broken.steps[0].evidence_refs = ['unverified_client_id'];
const issues = M.referenceIssues(broken);
assert(issues.some(s => s.includes('Duplicate step ID')));
assert(issues.some(s => s.includes('unknown assertion')));
assert(issues.some(s => s.includes('unknown observation')));

const untouched = M.deleteStep(edited, 1);
assert.equal(untouched.steps.length, 1);
assert.equal(edited.steps.length, 2);
assert.throws(() => M.parseAdvanced(JSON.stringify({...spec,runner:'xiheadless_observation_v1'})),/design-only/);
assert.throws(() => M.parseAdvanced(JSON.stringify({...spec,execution_status:'verified_runner'})),/design-only/);

const published = M.clone(spec);
published.runner = 'xiheadless_observation_v1';
published.execution_status = 'verified_runner';
published.case_id = 'MOG-09';
published.steps[0].id = 'MOG-09-S01';
const fork = M.forkPublished(published);
assert.equal(fork.case_id, 'SYNTH-MOG-09-DRAFT');
assert.equal(fork.runner, 'unassigned');
assert.equal(fork.execution_status, 'design_only');
assert.equal(fork.steps[0].id, published.steps[0].id);
assert.equal(fork.authoring.review_required,true);
console.log('Guided scenario model synthetic round-trip and safety: PASS');

const candidate = {
  kind:'npc',id:7001,name:'Synthetic Candidate NPC',
  source_path:'sql/npc_list.sql',duplicate_id_in_results:true,
  identity_status:'unreconciled_source_candidate',
  binding_verified:false,execution_enabled:false,operator_review_required:true,
};
const withCandidate = M.attachCandidate(spec, spec.steps[0].id, candidate);
assert.equal(withCandidate.steps[0].id,spec.steps[0].id);
assert.match(withCandidate.steps[0].confidence_note,/UNVERIFIED catalog candidate/);
assert.match(withCandidate.steps[0].confidence_note,/DUPLICATE ID/);
assert.match(withCandidate.steps[0].confidence_note,/source commit UNKNOWN/);
assert(withCandidate.authoring.blocking_gaps.some(g=>g.includes('reconcile')));
assert.equal(spec.steps[0].confidence_note.includes('catalog candidate'),false);
assert.deepEqual(M.parseAdvanced(JSON.stringify(withCandidate)),withCandidate);
assert.deepEqual(M.parseAdvanced(JSON.stringify(M.parseAdvanced(JSON.stringify(withCandidate)))),withCandidate);
const repeat=M.attachCandidate(withCandidate,withCandidate.steps[0].id,candidate);
assert.equal(repeat.steps[0].confidence_note.match(/UNVERIFIED catalog candidate/g).length,1);
const secondChoice={...candidate,id:7002,name:'Synthetic Other NPC',duplicate_id_in_results:false};
const changed=M.attachCandidate(repeat,repeat.steps[0].id,secondChoice);
assert.match(changed.steps[0].confidence_note,/7002/);
assert.doesNotMatch(changed.steps[0].confidence_note,/7001/);
assert.throws(()=>M.attachCandidate(spec,spec.steps[0].id,{...candidate,binding_verified:true}),/unverified/);
assert.throws(()=>M.attachCandidate(spec,'missing-step',candidate),/Choose a step/);
const cloned=M.cloneDraft(withCandidate);
assert.equal(cloned.case_id,'SYNTH-EDITOR-01-COPY');
assert.equal(cloned.runner,'unassigned');
assert.equal(cloned.execution_status,'design_only');
assert.equal(cloned.steps[0].id,withCandidate.steps[0].id);
assert.equal(cloned.steps[0].confidence_note,withCandidate.steps[0].confidence_note);
assert.match(M.revisionIndicator(null,cloned,0),/New draft/);
assert.match(M.revisionIndicator(cloned,M.clone(cloned),1),/no changes/);
const editedClone=M.clone(cloned);editedClone.purpose='Changed in editor';
assert.match(M.revisionIndicator(cloned,editedClone,1),/unsaved changes/);
console.log('Synthetic catalog attachment, clone and revision indicators: PASS');


const coverageContext={
 contract:'coverage_behavior_reference_v1',feature_id:'gardening',
 behavior_ref:'GARD-SYNTH-01',label:'Synthetic declared test intent',
 source_pointer:'features[id=gardening].cases[id=GARD-SYNTH-01]',
 expected_oracle:'UNKNOWN',context_only:true,review_required:true,
 design_only:true,auto_populate_allowed:false,auto_save_allowed:false,
 proposed_case_id:null,assertions:[],observations:[],capability_bindings:[],
 execution_enabled:false
};
const coverageDraft=M.draftFromCoverage(coverageContext);
assert.equal(coverageDraft.feature_id,'gardening');
assert.equal(coverageDraft.case_id,'');
assert.deepEqual(coverageDraft.assertions,[]);
assert.deepEqual(coverageDraft.observations,[]);
assert.deepEqual(coverageDraft.steps,[]);
assert.equal(coverageDraft.runner,'unassigned');
assert.equal(coverageDraft.execution_status,'design_only');
assert.match(coverageDraft.rationale,/UNVERIFIED/);
assert.deepEqual(M.parseAdvanced(JSON.stringify(coverageDraft)),coverageDraft);
assert.throws(()=>M.draftFromCoverage({...coverageContext,expected_oracle:'PASS'}),/Unsupported/);

const captureReview={
 contract:'editor_evidence_suggestions_v1', capture_id:1,
 projection_sha256:'a'.repeat(64), required_confirmation:true,
 original_capture_authenticated:false,execution_enabled:false,
 steps:[{step_id:'OBS-S001',observed_summary:'Synthetic indexed actor',
          suggested_title:'Observed synthetic actor',decision:'ACCEPT',
          evidence_refs:['capture-row:111'],bindings:[]},
        {step_id:'OBS-S002',observed_summary:'Synthetic second step',
          suggested_title:'Observed key item',decision:'PENDING',
          evidence_refs:['capture-row:222'],bindings:[]}]
};
assert.throws(()=>M.draftFromEvidence(captureReview,[]),/Confirm/);
assert.throws(()=>M.draftFromEvidence(captureReview,[{id:'OBS-S001',title:'A',confirmed:false}]),/confirmation/);
assert.throws(()=>M.draftFromEvidence(captureReview,[{id:'OBS-S002',title:'B',confirmed:true}]),/confirmation/);
const reverse=M.draftFromEvidence(captureReview,[{id:'OBS-S001',title:'Reviewed synthetic observation',confirmed:true,bindings:[]}]);
assert.equal(reverse.steps.length,1);
assert.equal(reverse.steps[0].id,'OBS-S001');
assert.deepEqual(reverse.steps[0].assertion_ids,[]);
assert.deepEqual(reverse.steps[0].evidence_refs,[]);
assert.match(reverse.steps[0].expected,/UNKNOWN/);
assert.match(reverse.steps[0].confidence_note,/capture-row:111/);
assert.match(reverse.rationale,/a{64}/);
assert.equal(reverse.execution_status,'design_only');
assert.deepEqual(M.parseAdvanced(JSON.stringify(reverse)),reverse);
reverse.behavior.given=['Synthetic manual precondition'];
reverse.observations=['client_bag'];
reverse.assertions=[{id:'manual_assertion',operation:'nonempty',observed:'client_bag',expected:null}];
reverse.steps[0].assertion_ids=['manual_assertion'];
reverse.steps[0].evidence_refs=['client_bag'];
reverse.preconditions=['Synthetic setup only'];reverse.cleanup=['No mutation'];
reverse.feature_id='inventory_observation';reverse.case_id='SYNTH-REVIEW-01';
assert.deepEqual(M.parseAdvanced(JSON.stringify(reverse)),reverse);
assert.equal(reverse.runner,'unassigned');
console.log('Coverage and evidence handoffs remain provisional through Guided/Advanced: PASS');

// context_ref handoff: read-only reference, no data taken beyond the label
{
  assert.equal(M.contextRefPath('/feature-testing/coverage/context/gardening/GARD-01'), '/feature-testing/coverage/context/gardening/GARD-01');
  for (const bad of ['https://evil.example/x', '//evil/x', '/feature-testing/coverage/context/../x/y',
    '/feature-testing/coverage/context/a/b/c', '/other', '', null, undefined])
    assert.equal(M.contextRefPath(bad), null);
  const ctx = {contract: 'coverage_behavior_reference_v1', feature_id: 'gardening', behavior_ref: 'GARD-01',
    label: 'place pot', source_pointer: 'features[id=gardening].cases[id=GARD-01]', source_revision: 'UNPINNED',
    context_only: true, design_only: true, review_required: true, auto_populate_allowed: false,
    auto_save_allowed: false, execution_enabled: false, proposed_case_id:null,
    expected_oracle:'UNKNOWN', assertions: [], observations: [], capability_bindings:[]};
  const d = M.fromContext(ctx, ['gardening']);
  assert.equal(d.feature_id, 'gardening');
  assert.equal(d.case_id, ''); // user must choose unique ID; no synthetic ID generation
  assert.equal(d.runner, 'unassigned');
  assert.equal(d.execution_status, 'design_only');
  assert.equal(d.authoring.state, 'draft');
  assert.equal(d.authoring.review_required, true);
  assert.deepEqual(d.steps,[]);
  assert.deepEqual(d.assertions,[]);
  assert.deepEqual(d.observations,[]);
  assert.match(d.behavior.then[0],/UNKNOWN/);
  assert.deepEqual(M.parseAdvanced(JSON.stringify(d)),d);
  assert.throws(() => M.fromContext({...ctx, auto_save_allowed: true}, ['gardening']), /(?:refused|Unsupported)/);
  assert.throws(() => M.fromContext({...ctx, contract: 'x'}, ['gardening']), /(?:refused|Unsupported)/);
  assert.throws(() => M.fromContext(ctx, ['voidwalker']), /(?:refused|Unsupported)/);
  console.log('Context reference handoff is read-only and design-only: PASS');
}


const reviewWithBindings={...captureReview,steps:[
  {...captureReview.steps[0],bindings:[
    {binding_id:'candidate:synthetic1',kind:'npc',identity:'original actor',
     suggested_identity:'proposed actor',review_decision:'EDIT',classification:'AMBIGUOUS'},
    {binding_id:'candidate:synthetic2',kind:'item',identity:'recorded item',
     review_decision:'PENDING',classification:'DECODED'}]}
]};
const selectStep=(bindings)=>[{id:'OBS-S001',title:'Observe original evidence',confirmed:true,bindings}];
assert.throws(()=>M.draftFromEvidence(reviewWithBindings,selectStep([])),/every candidate binding/);
assert.throws(()=>M.draftFromEvidence(reviewWithBindings,selectStep([
  {id:'candidate:synthetic1',choice:'INCLUDE_UNVERIFIED',confirmed:true},
  {id:'candidate:synthetic2',choice:'INCLUDE_UNVERIFIED',confirmed:true}])),/pending/);
assert.throws(()=>M.draftFromEvidence(reviewWithBindings,selectStep([
  {id:'candidate:synthetic1',choice:'',confirmed:false},
  {id:'candidate:synthetic2',choice:'EXCLUDE',confirmed:true}])),/unreviewed/);
const reviewedWithBindings=M.draftFromEvidence(reviewWithBindings,selectStep([
  {id:'candidate:synthetic1',choice:'INCLUDE_UNVERIFIED',confirmed:true},
  {id:'candidate:synthetic2',choice:'EXCLUDE',confirmed:true}]));
assert.match(reviewedWithBindings.steps[0].confidence_note,/source=original actor/);
assert.match(reviewedWithBindings.steps[0].confidence_note,/reviewer-proposal=proposed actor/);
assert.doesNotMatch(reviewedWithBindings.steps[0].confidence_note,/recorded item/);
assert.match(reviewedWithBindings.steps[0].expected,/UNKNOWN/);
assert.deepEqual(reviewedWithBindings.assertions,[]);
assert.deepEqual(M.parseAdvanced(JSON.stringify(reviewedWithBindings)),reviewedWithBindings);
assert.throws(()=>M.draftFromCoverage({...coverageContext,assertions:[{id:'smuggled'}]}),/Unsupported/);
console.log('Unified intake: no implicit assertion, explicit step AND identity decisions: PASS');


{
  const clean=M.fresh();
  assert.equal(M.handoffReplacementIssue(clean,null,0,null),null);
  const unsaved=M.clone(clean);
  unsaved.name='Operator-edited draft, must not be dropped';
  assert.match(M.handoffReplacementIssue(unsaved,null,0,null),/unsaved editor changes/);
  assert.match(M.handoffReplacementIssue(clean,clean,2,null),/saved draft is open/);
  assert.match(M.handoffReplacementIssue(clean,null,1,null),/saved draft is open/);
  assert.match(M.handoffReplacementIssue(clean,null,0,'coverage:gardening/GARD-01'),/already open/);
  assert.match(M.handoffReplacementIssue(reverse,null,0,'evidence:1/checksum'),/already open/);
  assert.match(M.handoffReplacementIssue(M.parseAdvanced(JSON.stringify(unsaved)),null,0,null),/unsaved editor changes/);
  assert.equal(M.handoffReplacementIssue(M.fresh(),null,0,null),null);
  console.log('No silent handoff replacement of unsaved/loaded drafts: PASS');
}


{
  const first={...coverageContext,category:'positive',source:'data/testing/feature_test_readiness.json',
    source_revision:'UNPINNED',label:'Original declared test intent',
    return_url:'/feature-testing/coverage'};
  assert.equal(M.coverageContextChanged(first,{...first}),false);
  assert.equal(M.coverageContextChanged(first,{...first,label:'Updated declared test intent'}),true);
  assert.equal(M.coverageContextChanged(first,{...first,source_revision:'PINNED'}),true);
  assert.equal(M.coverageContextChanged(first,{...first,auto_save_allowed:true}),true);
  assert.equal(M.coverageContextChanged(first,null),true);
  console.log('Coverage context revalidation rejects changed/expired source: PASS');
}

{
  // Every explicitly included source identity must survive; never claim
  // provenance survived round-trip if it was silently cut at 1000 chars.
  const bloated={...captureReview,steps:[{...captureReview.steps[0],
    evidence_refs:['capture-row:'+('A'.repeat(975))],bindings:[]}]};
  assert.throws(()=>M.draftFromEvidence(bloated,[
    {id:'OBS-S001',title:'Synthetic source',confirmed:true,bindings:[]}
  ]),/provenance exceeds/);
  console.log('Oversized source provenance fails closed instead of truncating accepted identities: PASS');
}

{
  const initial=M.fresh(),modified=M.clone(initial);
  modified.name='Unsaved operator edit';
  assert.equal(M.replacementConfirmationReason(initial,null,0,null),null);
  assert.match(M.replacementConfirmationReason(modified,null,0,null),/unsaved draft edits/);
  assert.match(M.replacementConfirmationReason(initial,initial,2,null),/loaded revision/);
  assert.match(M.replacementConfirmationReason(initial,null,0,'coverage:garden/GARD-01'),/source-derived/);
  const saved={feature_id:initial.feature_id,case_id:initial.case_id,revision:3};
  assert.deepEqual(M.saveResponseDisposition(initial,initial,saved,false),{
    apply_revision:true,unsaved_edits:false
  });
  assert.deepEqual(M.saveResponseDisposition(initial,modified,saved,false),{
    apply_revision:true,unsaved_edits:true
  });
  assert.match(M.saveResponseDisposition(initial,{...initial,case_id:'SYNTH-OTHER'},saved,false).reason,/identity changed/);
  assert.match(M.saveResponseDisposition(initial,initial,{...saved,case_id:'SYNTH-WRONG'},false).reason,/saved document identity/);
  assert.match(M.saveResponseDisposition(initial,initial,saved,true).reason,/document changed/);
  assert.equal(M.saveResponseDisposition(initial,null,saved,false).apply_revision,false);
  console.log('Discard guards and delayed save-response identity/revision semantics: PASS');
}
