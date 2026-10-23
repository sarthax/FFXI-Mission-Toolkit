/* R7 #1313. Optional evidence-owned read-only viewer, NOT an editor importer.
 * Host attaches only after explicit Agent B/Agent A route ownership agreement.
 * No canonical model access, save, grant, runner, raw packets or HTML injection.
 */
(function(root,factory) {
  const view=factory();
  if(typeof module!=='undefined'&&module.exports)module.exports=view;
  else root.ScenarioReadinessViewer=view;
})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const CONTRACT='read_only_paired_capture_readiness_view_v1_NONCANONICAL';
  const arr=x=>Array.isArray(x)?x:[];
  const string=x=>x===null||x===undefined?'UNKNOWN':String(x);
  const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=string(text);return e;};
  const line=(parent,text)=>{parent.append(node('p',text));};
  function verify(model) {
    if(!model||model.contract!==CONTRACT||
       !Number.isSafeInteger(model.capture_id)||model.capture_id<1||
       model.pair_integrity!=='BOTH_INDEXED_PROJECTIONS_RECOMPUTED_FROM_SELECTED_REVIEW'||
       model.original_capture_authenticated!==false||
       model.parser_decoder_authenticated!==false||
       model.source_bytes_rehashed!==false||
       model.automatic_import!==false||model.save_allowed!==false||
       model.approved_for_execution!==false||model.execution_enabled!==false||
       model.canonical_step_associations!=='UNASSIGNED'||
       model.scenario_specification!==null||model.normative_expected!==null||
       model.verdict!=='UNKNOWN'||!Array.isArray(model.steps)||!model.steps.length||
       !['UNKNOWN','BLOCKED'].includes(model.source_compatibility_state))
      throw Error('Untrusted readiness result cannot be displayed as accepted alignment');
    for(const step of model.steps) {
      if(step.canonical_step_id!==null ||
        step.canonical_source_association?.state!=='UNASSIGNED_REQUIRES_INDEPENDENT_CANONICAL_CROSSWALK'||
        step.canonical_source_association?.scope!==null||
        !Array.isArray(step.canonical_source_association?.source_refs)||
        step.canonical_source_association.source_refs.length||
        step.oracle_approval_state!=='UNAPPROVED'||step.normative_expected!==null||
        step.verdict!=='UNKNOWN'||step.execution_enabled!==false||
        !['UNKNOWN','BLOCKED'].includes(step.readiness_state)||
        !Array.isArray(step.original_evidence_refs)||
        !Array.isArray(step.indexed_evidence_provenance)||
        !Array.isArray(step.identity_confidence)||
        !Array.isArray(step.missing_readbacks))
        throw Error('Readiness step attempted canonical or oracle promotion');
      const refs=step.original_evidence_refs;
      if(refs.length!==new Set(refs).size||
         refs.length!==step.indexed_evidence_provenance.length||
         step.indexed_evidence_provenance.some((source,i)=>
           source.evidence_ref!==refs[i]||
           source.capture_id!==model.capture_id||
           source.independent_source_authentication!==false||
           !Array.isArray(source.source_file_claims)||
           source.source_file_claims.some(loc=>
             loc.indexed_digests_rehashed!==false||
             loc.decoder_version!==null||
             loc.decoder_version_status!=='NOT_INDEPENDENTLY_ATTESTED'))||
         step.identity_confidence.some(binding=>binding.source_identity_verified!==false)||
         step.missing_readbacks.some(gap=>
           gap.status!=='NOT_INDEPENDENTLY_OBSERVED'||
           gap.permission_granted!==false||gap.capability_registered!==false))
        throw Error('Readiness step attempted source, identity or readback verification');
    }
    return model;
  }
  function render(container, result) {
    const model=verify(result);
    const root=node('section');
    root.append(node('h3','Paired capture '+model.capture_id+' · READ ONLY · '+model.source_compatibility_state));
    line(root,'Two independent JSON projection scopes recomputed: '+model.pair_integrity);
    line(root,'Original handoff projection SHA-256: '+model.original_handoff_projection_sha256);
    line(root,'Indexed observation projection SHA-256: '+model.indexed_observation_projection_sha256);
    line(root,'Physical capture, decoder, source bytes, DSP/client and gameplay NOT AUTHENTICATED.');
    line(root,'UNKNOWN is not PASS. BLOCKED is source/provenance incompatibility, NOT gameplay FAIL.');
    line(root,model.security_notice);
    for(const p of arr(model.source_provenance_issues))
      line(root,'Source '+string(p.severity)+' · '+string(p.code)+': '+string(p.reason));
    for(const step of model.steps) {
      const card=node('article');
      card.append(node('h4','Captured observation '+step.step_id+' · '+step.readiness_state));
      line(card,'Original observation: '+step.observed_summary_original);
      line(card,'Original indexed step review (observation only): '+
        string(step.reviewer_step_decision_original?.decision)+
        ' · '+string(step.reviewer_step_decision_original?.note));
      line(card,'Selected reviewed-decision export CHOICE (not an oracle): '+
        string(step.reviewer_step_decision_selected?.decision)+
        ' · '+string(step.reviewer_step_decision_selected?.note));
      line(card,'Canonical step association: UNASSIGNED; capture step is NOT a canonical step.');
      line(card,'Original evidence: '+arr(step.original_evidence_refs).map(string).join(', '));
      for(const source of arr(step.indexed_evidence_provenance)) {
        const info=node('details');info.append(node('summary','Indexed capture ref '+source.evidence_ref));
        line(info,'Capture '+source.capture_id+' · '+source.source_table+
          ' · row '+JSON.stringify(source.original_row_key));
        line(info,'Timestamp '+string(source.native_timestamp)+' · time basis '+source.time_basis);
        line(info,'File locator '+source.capture_file_locator_state+
          '; '+string(source.source_locator_status));
        for(const loc of arr(source.source_file_claims)) {
          const span=loc.source_span||{};
          line(info,'Indexed source filename CLAIM: '+string(loc.source_filename)+
            ' · line '+string(span.start_line)+'–'+string(span.end_line)+
            ' · offsets '+string(span.start_offset)+'–'+string(span.end_offset));
          line(info,'Parser DECLARATION: '+string(loc.parser_name_claim)+' / '+
            string(loc.parser_version_claim)+' · '+string(loc.parser_support));
          line(info,'Locator SHA-256 CLAIM: '+string(loc.locator_sha256_claim)+
            '; manifest SHA-256 CLAIM: '+string(loc.manifest_sha256_claim));
          line(info,'Decoder: '+string(loc.decoder_version_status)+'; bytes NOT independently rehashed.');
        }
        for(const issue of arr(source.provenance_issues))
          line(info,string(issue.severity)+' · '+string(issue.code)+': '+string(issue.reason));
        card.append(info);
      }
      for(const b of arr(step.identity_confidence))
        line(card,'Identity '+string(b.binding_id)+' ('+string(b.capture_identity_kind)+
          ') OBSERVED '+string(b.observed_value)+' · '+string(b.classification)+
          ' · original reviewer '+string(b.review_decision_original?.decision)+
          ' · selected reviewer CHOICE '+string(b.review_decision_selected?.decision)+
          ' · VERIFIED: NO; canonical identity UNASSIGNED');
      line(card,'Source-backed expected candidate, NOT approved: '+string(step.expected_candidate));
      line(card,'Oracle approval: UNAPPROVED · normative expected: UNKNOWN · execution DISABLED');
      for(const gap of arr(step.missing_readbacks))
        line(card,'MISSING '+string(gap.importance)+' '+string(gap.expected_observation_type)+
          ' · '+string(gap.reason_for_gap)+' · suggested (not granted): '+
          string(gap.suggested_read_only_capability));
      for(const issue of arr(step.provenance_issues))
        line(card,'Readiness '+string(issue.severity)+' · '+string(issue.code)+': '+string(issue.reason));
      root.append(card);
    }
    container.replaceChildren(root);
    return root;
  }

  // Selected local JSON is untrusted. Do not expose engine-specific parse
  // offsets, source fragments or raw SyntaxError text to the operator.
  function parseSelectedJson(raw, label) {
    try {return JSON.parse(raw);}
    catch(error) {
      if(error instanceof SyntaxError)throw Error(label+' is not valid JSON');
      throw error;
    }
  }
  // Diagnostic only: the backend independently checks the full original
  // review, sidecar, both digests and every authorization/provenance gate.
  function checkOriginalCaptureIdentity(reviewFile) {
    const original=reviewFile?.observed_handoff;
    if(Number.isSafeInteger(reviewFile?.capture_id)&&reviewFile.capture_id>0&&
       Number.isSafeInteger(original?.capture_id)&&original.capture_id>0&&
       reviewFile.capture_id!==original.capture_id)
      throw Error('Original review capture identity mismatch');
  }

  function mount(container, inspect) {
    if(typeof inspect!=='function')throw Error('A trusted read-only pair inspector must be supplied');
    const section=node('section');
    section.append(node('h3','Optional readiness advisory — separate from canonical Evidence import'));
    line(section,'Select TWO local JSON files exported from the SAME original offline Evidence Reviewer. '+ 
      'Their matching hashes do not authenticate original capture bytes.');
    const review=node('input');review.type='file';review.accept='.json,application/json';
    const advisory=node('input');advisory.type='file';advisory.accept='.json,application/json';
    const inspectButton=node('button','Inspect selected pair (read only)');inspectButton.type='button';
    const status=node('p','No pair inspected; nothing imported or saved.');
    const output=node('div');
    section.append(node('label','Original reviewed-decision JSON'),review,
      node('label','Separate readiness sidecar JSON'),advisory,inspectButton,status,output);
    container.replaceChildren(section);
    let generation=0,pending=false,closed=false;
    function invalidate() {
      if(closed)return;
      generation++;
      output.replaceChildren();
      status.textContent='Selection changed. Reinspect the two current files; no draft was modified.';
    }
    review.addEventListener('change',invalidate);
    advisory.addEventListener('change',invalidate);
    inspectButton.addEventListener('click',async()=>{
      if(closed||pending)return;
      const stamp=++generation,a=review.files?.[0],b=advisory.files?.[0];
      output.replaceChildren();
      try{
        if(!a||!b||a.size<1||b.size<1||a.size>4_500_000||b.size>4_500_000)
          throw Error('Choose two nonempty JSON files under 4.5 MB each');
        pending=true;inspectButton.disabled=true;
        status.textContent='Inspecting both original selections; no canonical import.';
        const [original,sidecar]=await Promise.all([a.text(),b.text()]);
        if(stamp!==generation||review.files?.[0]!==a||advisory.files?.[0]!==b)
          throw Error('Selected files changed during inspection');
        const reviewFile=parseSelectedJson(original,'Original reviewed-decision file');
        const sidecarFile=parseSelectedJson(sidecar,'Readiness sidecar file');
        checkOriginalCaptureIdentity(reviewFile);
        const model=await inspect(reviewFile,sidecarFile);
        if(stamp!==generation||review.files?.[0]!==a||advisory.files?.[0]!==b)
          throw Error('Selected files changed during inspection');
        render(output,model);
        status.textContent='Matched INDEXED JSON scopes only. UNVERIFIED READ-ONLY advisory; no draft change.';
      }catch(error){
        if(stamp===generation){
          output.replaceChildren();
          status.textContent='Pair NOT accepted: '+string(error.message)+
            '. No evidence imported; preserve original files.';
        }
      }finally{
        pending=false;
        if(!closed)inspectButton.disabled=false;
      }
    });
    function dispose(){
      closed=true;
      generation++;
      output.replaceChildren();
      inspectButton.disabled=true;
      status.textContent='Viewer closed. No retained readiness evidence or draft changes.';
    }
    return {review,advisory,inspectButton,status,output,dispose};
  }
  return {verify,render,mount};
});
