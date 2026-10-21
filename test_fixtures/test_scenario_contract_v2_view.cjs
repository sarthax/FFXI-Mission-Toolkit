/* R7 #1302. Pure synthetic, no browser, network or game client. */
const assert=require('node:assert/strict');
const M=require('../gui/static/scenario_guided_model.js');
const V=require('../gui/static/scenario_contract_v2_view.js');

const legacy=M.fresh();
const before=JSON.stringify(legacy);
const old=V.project(legacy);
assert.equal(old.present,false);
assert.equal(old.legacy,true);
assert.equal(JSON.stringify(legacy),before);
assert.match(old.message,/Legacy v1/);

const v=M.clone(legacy), sid=v.steps[0].id,aid=v.assertions[0].id;
v.contract_v2={
  contract_version:2,
  sources:[
    {ref:'SrcOne',repository:'sarthax/darkstar-to-valhalla',
      path:'scripts/zones/Zone/npcs/Synthetic.lua',line_start:1,line_end:3,
      revision:'a'.repeat(40),classification:'dsp_source',sha256:'b'.repeat(64)},
    {ref:'SrcOther',repository:'sarthax/darkstar-to-valhalla',
      path:'scripts/zones/Zone/npcs/Other.lua',line_start:7,line_end:8,
      revision:null,classification:'documentation',sha256:null}
  ],
  parameters:[
    {name:'Candidate',kind:'npc',identity:7,namespace:'DSP',zone_id:12,binding_state:'candidate',source_refs:['SrcOne']},
    {name:'Ambiguous',kind:'npc',identity:null,namespace:null,zone_id:null,binding_state:'ambiguous',source_refs:['SrcOther']},
    {name:'Unresolved',kind:'npc',identity:null,namespace:null,zone_id:null,binding_state:'unresolved',source_refs:[]},
    {name:'PinnedClaim',kind:'npc',identity:8,namespace:'DSP',zone_id:12,binding_state:'independently_source_verified',source_refs:['SrcOne']}
  ],
  oracles:[{assertion_id:aid,oracle_type:'source_rule',source_refs:['SrcOne'],confidence:'candidate'}],
  step_requirements:[{step_id:sid,capability:'client_action_candidate',operation_class:'unknown',
    required_permissions:['operator_approval'],required_readbacks:['client_inventory','server_inventory'],
    approval_required:true,execution_gate:'blocked'}],
  fingerprints:{base_spec_sha256:null,dsp_commit:null,headless_commit:null,toolkit_commit:null}
};
const json=JSON.stringify(v),beforeV=JSON.parse(json);
const projected=V.project(v);
assert.equal(projected.present,true);
assert.equal(projected.compatibility.state,'UNKNOWN');
assert.equal(projected.execution_enabled,false);
assert.equal(projected.sources[1].digest_state,'UNKNOWN / UNHASHED');
assert.match(projected.sources[0].digest_state,/NOT INDEPENDENTLY REHASHED/);
assert.equal(projected.bindings[1].identity,'UNRESOLVED');
assert.equal(projected.bindings[1].claim.includes('AMBIGUOUS'),true);
assert.equal(projected.bindings[3].approved,false);
assert.match(projected.bindings[3].claim,/not independently reconciled/);
assert.equal(projected.oracles[0].approved,false);
assert.equal(projected.oracles[0].expected_candidate,true);
// An oracle source supports an assertion's proposed expected value. It is
// NOT an explicit source-to-step citation, even if that assertion is linked.
assert.equal(projected.steps[0].sources.length,0);
assert.equal(projected.steps[0].oracle_citations.length,1);
assert.equal(projected.steps[0].oracle_citations[0].ref,'SrcOne');
assert.match(projected.steps[0].attribution,/STEP-LEVEL SOURCE ATTRIBUTION UNAVAILABLE/);
assert.match(projected.sources[0].attribution,/ATTRIBUTION UNASSIGNED/);
assert.doesNotMatch(projected.sources[0].attribution,/CASE-LEVEL SOURCE/);
assert.equal(projected.steps[0].execution_gate,'BLOCKED');
assert.equal(projected.steps[0].permissions[0],'operator_approval');
assert.equal(projected.steps[0].readbacks.length,2);
assert.equal(JSON.stringify(v),json); // read-only render
assert.deepEqual(M.parseAdvanced(JSON.stringify(v)),beforeV);

const changedCore=M.clone(v);changedCore.steps[0].expected='UNKNOWN — new source expected candidate';
const blocked=V.project(changedCore,{state:'BLOCKED',reasons:['base specification SHA-256 mismatch']});
assert.equal(blocked.compatibility.state,'BLOCKED');
assert.deepEqual(blocked.compatibility.reasons,['base specification SHA-256 mismatch']);
const claimedMatch=V.project(v,{state:'MATCHED_PINNED_ONLY',reasons:[],execution_enabled:true});
assert.equal(claimedMatch.compatibility.state,'MATCHED_PINNED_ONLY');
assert.equal(claimedMatch.execution_enabled,false);
assert.equal(claimedMatch.compatibility.execution_enabled,false);
assert.equal(claimedMatch.independently_verified,false);
const arbitrary=V.project(v,{state:'SOURCE_AUTHENTICATED',reasons:[]});
assert.equal(arbitrary.compatibility.state,'UNKNOWN'); // fail closed

const withUnrelated=M.addStep(v),newStep=V.project(withUnrelated).steps[1];
assert.equal(newStep.sources.length,0);
assert.match(newStep.attribution,/STEP-LEVEL SOURCE ATTRIBUTION UNAVAILABLE/);
assert.equal(newStep.execution_gate,'BLOCKED');
const withoutOracle=M.clone(v);withoutOracle.contract_v2.oracles=[];
assert.equal(V.project(withoutOracle).steps[0].sources.length,0);

const moved=M.moveStep(withUnrelated,1,-1);
assert.deepEqual(moved.contract_v2, v.contract_v2);
const fork=M.forkPublished({...v,runner:'xiheadless_observation_v1',execution_status:'verified_runner'});
const clone=M.cloneDraft(v);
for(const doc of [fork,clone,changedCore,moved]) {
  assert.deepEqual(doc.contract_v2,v.contract_v2); // must retain stale claims, never silently repin
  assert.deepEqual(M.parseAdvanced(JSON.stringify(doc)).contract_v2,v.contract_v2);
  assert.equal(V.project(doc).execution_enabled,false);
}
assert.equal(V.project(M.draftFromCoverage({contract:'coverage_behavior_reference_v1',
  feature_id:'inventory_observation',behavior_ref:'CASE-01',label:'Synthetic context',
  source_pointer:'fixture',expected_oracle:'UNKNOWN',context_only:true,review_required:true,
  design_only:true,auto_populate_allowed:false,auto_save_allowed:false,
  proposed_case_id:null,assertions:[],observations:[],capability_bindings:[],
  execution_enabled:false})).present,false);
console.log('R7 canonical optional-v2 rendering identity provenance and preservation: PASS');

const orphan=M.clone(v);
orphan.contract_v2.oracles=[];
orphan.contract_v2.parameters=[];
const unassociated=V.project(orphan);
assert.equal(unassociated.sources.length,2); // preserve every declared source
assert.equal(unassociated.steps[0].sources.length,0);
assert.equal(unassociated.steps[0].oracle_citations.length,0);
assert.match(unassociated.sources[1].attribution,/UNASSIGNED/);

// Agent D's additional indexed-evidence sidecar is *not* the reviewed
// evidence-decision envelope and cannot be silently imported as one.
const sidecar={
  contract:'capture_reviewer_readiness_sidecar_v0_NONCANONICAL',
  original_evidence_handoff:{capture_id:1},
  indexed_observation_projection_sha256:'a'.repeat(64),
  original_handoff_projection_sha256:'b'.repeat(64),
  scenario_developer_handoff:{read_only_projection:{
    contract:'capture_readiness_authoring_projection_v1_NONCANONICAL',
    steps:[{indexed_evidence_provenance:[{parser_support:'UNRECOGNIZED_OR_UNSUPPORTED',
      decoder_version:null,independent_source_authentication:false,
      indexed_digests_rehashed:false}]}],
    automatic_import:false,execution_enabled:false
  }}
};
assert.throws(()=>M.draftFromEvidence(sidecar,[]),/Unreviewed or unsupported evidence suggestion/);
assert.deepEqual(M.parseAdvanced(JSON.stringify(v)).contract_v2,v.contract_v2);
console.log('R7 no inferred source scope or sidecar import/approval: PASS');


// #1309 proposed optional canonical association is not merged in this test
// baseline. Preserve the raw metadata in editor operations, but NEVER derive
// case/step proof from an unknown extension before the canonical helper exists.
const proposed=M.clone(v);
proposed.contract_v2.source_associations=[
  {scope:'case',target_id:null,source_refs:['SrcOther']},
  {scope:'step',target_id:sid,source_refs:['SrcOne']}
];
const proposalBefore=JSON.stringify(proposed);
const proposalView=V.project(proposed);
assert.deepEqual(proposalView.steps[0].sources,[]);
assert.equal(proposalView.steps[0].oracle_citations[0].ref,'SrcOne');
assert.match(proposalView.sources[0].attribution,/ATTRIBUTION UNASSIGNED/);
assert.equal(proposalView.execution_enabled,false);
assert.equal(JSON.stringify(proposed),proposalBefore);
for(const transformed of [
  M.parseAdvanced(JSON.stringify(proposed)),
  M.cloneDraft(proposed),
  M.forkPublished({...proposed,runner:'xiheadless_observation_v1',
    execution_status:'verified_runner'}),
  M.moveStep(M.addStep(proposed),1,-1)
]) {
  assert.deepEqual(transformed.contract_v2.source_associations,
    proposed.contract_v2.source_associations);
  assert.equal(V.project(transformed).execution_enabled,false);
}
const spoof=M.clone(proposed);
spoof.contract_v2.source_associations[1].target_id='OBS-CAPTURE-S001';
assert.deepEqual(V.project(spoof).steps[0].sources,[]);
assert.equal(V.project(spoof).execution_enabled,false);

// #1308 proposed indexed source provenance is a noncanonical read-only
// producer sidecar and remains excluded from reviewed-decision import.
const richerSidecar={
  contract:'capture_reviewer_readiness_sidecar_v0_NONCANONICAL',
  indexed_observation_projection_sha256:'d'.repeat(64),
  original_handoff_projection_sha256:'e'.repeat(64),
  scenario_developer_handoff:{read_only_projection:{
    contract:'capture_readiness_authoring_projection_v1_NONCANONICAL',
    capture_id:42,physical_source_authenticated:false,
    automatic_import:false,save_allowed:false,execution_enabled:false,
    steps:[{
      step_id:'OBS-S001',canonical_step_id:null,
      canonical_source_association:{
        state:'UNASSIGNED_REQUIRES_INDEPENDENT_CANONICAL_CROSSWALK',
        scope:null,source_refs:[]},
      identity_confidence:[{classification:'AMBIGUOUS',
        proposed_v2_binding_state:'ambiguous',identity_candidate:null,
        source_identity_verified:false}],
      missing_readbacks:[{observation:'server_inventory_readback',
        readiness_state:'UNKNOWN'}],
      readiness_state:'UNKNOWN',oracle_approval_state:'UNAPPROVED',
      normative_expected:null,execution_enabled:false,
      indexed_evidence_provenance:[{
        evidence_ref:'capture-row:1',capture_id:42,source_table:'capture_events',
        original_row_key:'row-1',native_timestamp:'2026-10-21T12:00:00Z',
        source_file_claims:[{parser_name_claim:'capture-parser',
          parser_version_claim:'synthetic',decoder_version:null,
          locator_sha256_claim:'f'.repeat(64),manifest_sha256_claim:'f'.repeat(64),
          indexed_digests_rehashed:false}],
        independent_source_authentication:false
      }]
    }]
  }}
};
assert.throws(()=>M.draftFromEvidence(richerSidecar,[]),
  /Unreviewed or unsupported evidence suggestion/);
assert.equal(richerSidecar.scenario_developer_handoff.read_only_projection
  .steps[0].canonical_step_id,null);
assert.equal(V.project(v).execution_enabled,false);
console.log('R7 pending C/D interface compatibility stays noncanonical and unapproved: PASS');


// Accepted #1309 server report, not a client-side reconstruction of
// source_associations; prove explicit CASE and STEP scopes stay independent.
const acceptedAssociation={
  case:{state:'EXPLICIT_CITATION_CLAIM',source_refs:['SrcOther']},
  steps:{[sid]:{state:'EXPLICIT_CITATION_CLAIM',source_refs:['SrcOne']}},
  independent_verification:'NOT_ESTABLISHED',
  oracle_approval:'NOT_ESTABLISHED',
  execution_enabled:false
};
const explicit=V.project(proposed,{state:'UNKNOWN',reasons:['no verified engine']},
  acceptedAssociation);
assert.equal(explicit.case_association.state,'EXPLICIT_CITATION_CLAIM');
assert.deepEqual(explicit.case_association.sources.map(x=>x.ref),['SrcOther']);
assert.equal(explicit.steps[0].association_state,'EXPLICIT_CITATION_CLAIM');
assert.deepEqual(explicit.steps[0].sources.map(x=>x.ref),['SrcOne']);
assert.equal(explicit.steps[0].oracle_citations[0].ref,'SrcOne');
assert.equal(explicit.oracles[0].approved,false);
assert.equal(explicit.bindings[1].approved,false);
assert.equal(explicit.execution_enabled,false);
assert.equal(explicit.unassigned_sources.length,0);
assert.match(explicit.sources[0].attribution,/EXPLICIT STEP/);
assert.match(explicit.sources[1].attribution,/EXPLICIT CASE/);
assert.equal(JSON.stringify(proposed),proposalBefore);

const caseOnly=V.project(proposed,null,{
  ...acceptedAssociation,steps:{[sid]:{state:'UNKNOWN',source_refs:[]}}
});
assert.equal(caseOnly.case_association.state,'EXPLICIT_CITATION_CLAIM');
assert.equal(caseOnly.steps[0].sources.length,0);
assert.equal(caseOnly.steps[0].association_state,'UNKNOWN');
assert.equal(caseOnly.unassigned_sources[0].ref,'SrcOne');

const stepOnly=V.project(proposed,null,{
  ...acceptedAssociation,case:{state:'UNKNOWN',source_refs:[]}
});
assert.equal(stepOnly.case_association.sources.length,0);
assert.deepEqual(stepOnly.steps[0].sources.map(x=>x.ref),['SrcOne']);
assert.equal(stepOnly.unassigned_sources[0].ref,'SrcOther');

const unassignedCanonical=V.project(proposed,null,{
  ...acceptedAssociation,case:{state:'UNKNOWN',source_refs:[]},
  steps:{[sid]:{state:'UNKNOWN',source_refs:[]}}
});
assert.equal(unassignedCanonical.unassigned_sources.length,2);
assert.equal(unassignedCanonical.steps[0].sources.length,0);
assert.equal(unassignedCanonical.oracles[0].approved,false);

// Advanced edits are provisional and MUST NOT create an explicit citation
// without an accepted server report for the current specification.
const provisional=V.project(proposed,null);
assert.equal(provisional.steps[0].sources.length,0);
assert.equal(provisional.case_association.state,'UNKNOWN');
assert.match(provisional.association_diagnostics.join(' '),/PENDING CANONICAL VALIDATION/);

// Reject a malformed/forged report rather than showing unauthorized scopes.
for(const malformed of [
  {...acceptedAssociation,execution_enabled:true},
  {...acceptedAssociation,independent_verification:'VERIFIED'},
  {...acceptedAssociation,oracle_approval:'APPROVED'}
]) {
  assert.equal(V.project(proposed,null,malformed).steps[0].sources.length,0);
  assert.equal(V.project(proposed,null,malformed).case_association.state,'UNKNOWN');
}
const unknownSource=V.project(proposed,null,{
  ...acceptedAssociation,
  steps:{[sid]:{state:'EXPLICIT_CITATION_CLAIM',source_refs:['forged-source']}}
});
assert.equal(unknownSource.steps[0].sources.length,0);
assert.equal(unknownSource.steps[0].association_state,'BLOCKED');
assert.match(unknownSource.association_diagnostics.join(' '),/BLOCKED/);
const unknownStep=V.project(proposed,null,{
  ...acceptedAssociation,case:{state:'UNKNOWN',source_refs:[]},
  steps:{[sid]:{state:'UNKNOWN',source_refs:[]},
    'OBS-CAPTURE-S001':{state:'EXPLICIT_CITATION_CLAIM',source_refs:['SrcOne']}}
});
assert.equal(unknownStep.steps[0].sources.length,0);
assert.equal(unknownStep.case_association.state,'UNKNOWN');
assert.match(unknownStep.association_diagnostics.join(' '),/BLOCKED: stale or invalid/);
const crossDocument=V.project(proposed,null,{
  ...acceptedAssociation,steps:{
    'OTHER-CASE-S01':{state:'EXPLICIT_CITATION_CLAIM',source_refs:['SrcOne']}
  }
});
assert.equal(crossDocument.case_association.state,'UNKNOWN');
assert.equal(crossDocument.steps[0].association_state,'UNKNOWN');
assert.equal(crossDocument.execution_enabled,false);
assert.match(crossDocument.association_diagnostics.join(' '),/BLOCKED/);

const oldV2WithoutAssociations=M.clone(v);
assert.equal(V.project(oldV2WithoutAssociations,null,{
  case:{state:'UNKNOWN',source_refs:[]},steps:{[sid]:{state:'UNKNOWN',source_refs:[]}},
  independent_verification:'NOT_ESTABLISHED',oracle_approval:'NOT_ESTABLISHED',
  execution_enabled:false
}).steps[0].association_state,'UNKNOWN');
console.log('R7 canonical CASE/STEP association helper and fail-closed display: PASS');
