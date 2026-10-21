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
assert.equal(projected.steps[0].sources.length,1);
assert.equal(projected.steps[0].sources[0].ref,'SrcOne');
assert.match(projected.steps[0].attribution,/ORACLE-LINKED/);
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
