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

// context_ref handoff: read-only reference, no data taken beyond the label
{
  assert.equal(M.contextRefPath('/feature-testing/coverage/context/gardening/GARD-01'), '/feature-testing/coverage/context/gardening/GARD-01');
  for (const bad of ['https://evil.example/x', '//evil/x', '/feature-testing/coverage/context/../x/y',
    '/feature-testing/coverage/context/a/b/c', '/other', '', null, undefined])
    assert.equal(M.contextRefPath(bad), null);
  const ctx = {contract: 'coverage_behavior_reference_v1', feature_id: 'gardening', behavior_ref: 'GARD-01',
    label: 'place pot', source_pointer: 'features[id=gardening].cases[id=GARD-01]', source_revision: 'UNPINNED',
    context_only: true, design_only: true, review_required: true, auto_populate_allowed: false,
    auto_save_allowed: false, execution_enabled: false, assertions: [{id: 'evil'}], observations: ['gm_aura']};
  const d = M.fromContext(ctx, ['gardening']);
  assert.equal(d.feature_id, 'gardening');
  assert.equal(d.case_id, 'SYNTH-GARD-01-DRAFT');
  assert.equal(d.runner, 'unassigned');
  assert.equal(d.execution_status, 'design_only');
  assert.equal(d.authoring.state, 'draft');
  assert.equal(d.authoring.review_required, true);
  assert.ok(d.steps[0].id.startsWith('SYNTH-GARD-01-DRAFT'));
  assert.deepEqual(d.assertions.map(a => a.id), ['bag_observed']);
  assert.ok(!d.observations.includes('gm_aura'));
  assert.throws(() => M.fromContext({...ctx, auto_save_allowed: true}, ['gardening']), /refused/);
  assert.throws(() => M.fromContext({...ctx, contract: 'x'}, ['gardening']), /refused/);
  assert.throws(() => M.fromContext(ctx, ['voidwalker']), /refused/);
  console.log('Context reference handoff is read-only and design-only: PASS');
}
