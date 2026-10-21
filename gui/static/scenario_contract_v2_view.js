/* R7 #1302: read-only OPTIONAL canonical contract_v2 presentation.
 * No source attestation, identity approval, permissions or execution.
 * This model never rewrites specifications or consumes the noncanonical sidecar.
 */
(function(root,factory) {
  const view=factory();
  if(typeof module!=='undefined' && module.exports)module.exports=view;
  else root.ScenarioContractV2View=view;
})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const array=x=>Array.isArray(x)?x:[];
  const object=x=>x && typeof x==='object'&&!Array.isArray(x)?x:{};
  const value=x=>x===null||x===undefined?'UNKNOWN':String(x);

  function project(spec, compatibility, attributionReport) {
    if(!spec || !Object.prototype.hasOwnProperty.call(spec,'contract_v2'))
      return {present:false,legacy:true,execution_enabled:false,
        message:'Legacy v1 — no contract_v2 metadata; existing canonical behavior unchanged.'};
    const v=object(spec.contract_v2);
    if(v.contract_version!==2) return {present:true,valid:false,execution_enabled:false,
      message:'Unsupported optional contract metadata; canonical validation required.'};
    const sources=array(v.sources).map(s=>({
      ref:value(s.ref),repository:value(s.repository),path:value(s.path),
      revision:value(s.revision),line_range:s.line_start==null?'UNKNOWN':String(s.line_start)+'–'+String(s.line_end),
      classification:value(s.classification),digest:value(s.sha256),
      digest_state:s.sha256&&s.revision?'DECLARED / NOT INDEPENDENTLY REHASHED':'UNKNOWN / UNHASHED',
      attribution:'DECLARED SOURCE REGISTRY — ATTRIBUTION UNASSIGNED (not an explicit case or step citation)'
    }));
    const byRef=new Map(sources.map(s=>[s.ref,s]));
    const sourceRefs=refs=>array(refs).map(r=>byRef.get(r)).filter(Boolean);
    // The only authoritative case/step *citation* scope is Agent C's
    // accepted Python source_attribution_report. Never derive it from
    // v2.source_associations in JavaScript, or from oracle/capture IDs.
    const reportSteps=object(attributionReport && attributionReport.steps);
    const stepIds=array(spec.steps).map(step=>step.id);
    // Structural safety around the accepted *server projection*, not a
    // competing validator for raw source_associations. Cross-document or
    // extra capture-step keys cannot be displayed as canonical citations.
    const acceptedReport=!!attributionReport &&
      attributionReport.execution_enabled===false &&
      attributionReport.independent_verification==='NOT_ESTABLISHED' &&
      attributionReport.oracle_approval==='NOT_ESTABLISHED' &&
      object(attributionReport.steps)===attributionReport.steps &&
      Object.keys(reportSteps).length===stepIds.length &&
      stepIds.every(id=>Object.prototype.hasOwnProperty.call(reportSteps,id));
    const diagnostics=[];
    if(attributionReport && !acceptedReport)
      diagnostics.push('BLOCKED: stale or invalid canonical source-attribution report; validate the current draft again');
    const claim=(entry,scope)=>{
      if(!acceptedReport)return {state:'UNKNOWN',sources:[]};
      const item=object(entry);
      if(item.state==='UNKNOWN' && array(item.source_refs).length===0)
        return {state:'UNKNOWN',sources:[]};
      if(item.state==='EXPLICIT_CITATION_CLAIM' &&
         Array.isArray(item.source_refs) && item.source_refs.length &&
         item.source_refs.every(ref=>byRef.has(ref)))
        return {state:'EXPLICIT_CITATION_CLAIM',sources:sourceRefs(item.source_refs)};
      diagnostics.push('BLOCKED: malformed canonical '+scope+' association report; no sources attributed');
      return {state:'BLOCKED',sources:[]};
    };
    const caseAssociation=claim(acceptedReport?attributionReport.case:null,'case');
    const stepAssociations=new Map(array(spec.steps).map(step=>[
      step.id,claim(acceptedReport?attributionReport.steps[step.id]:null,'step '+step.id)
    ]));
    const scopes=new Map(sources.map(src=>[src.ref,[]]));
    for(const item of caseAssociation.sources)scopes.get(item.ref).push('EXPLICIT CASE CITATION CLAIM');
    for(const [stepId,association] of stepAssociations)
      for(const item of association.sources)
        scopes.get(item.ref).push('EXPLICIT STEP '+stepId+' CITATION CLAIM');
    for(const src of sources){
      const found=scopes.get(src.ref);
      src.attribution=found.length?found.join('; '):
        'DECLARED SOURCE REGISTRY — ATTRIBUTION UNASSIGNED (not an explicit case or step citation)';
    }
    if(!acceptedReport && Object.prototype.hasOwnProperty.call(v,'source_associations'))
      diagnostics.push('PENDING CANONICAL VALIDATION — explicit source associations not displayed as accepted claims');
    if(acceptedReport && attributionReport.case && caseAssociation.state==='BLOCKED')
      diagnostics.push('Source-citation display is blocked until canonical report is valid');
    const bindings=array(v.parameters).map(p=>({
      name:value(p.name),kind:value(p.kind),identity:p.identity==null?'UNRESOLVED':String(p.identity),
      namespace:value(p.namespace),zone_id:value(p.zone_id),state:value(p.binding_state),
      claim:p.binding_state==='independently_source_verified'?
        'DECLARED PINNED SOURCE CLAIM ONLY — not independently reconciled to client/DSP':
        p.binding_state==='ambiguous'?'AMBIGUOUS — no identity selected':
        p.binding_state==='unresolved'?'UNRESOLVED — no identity selected':
        'CANDIDATE — not independently verified',
      sources:sourceRefs(p.source_refs),attribution:'BINDING-LEVEL; no canonical step association',
      approved:false
    }));
    const oracles=array(v.oracles).map(o=>({
      assertion_id:value(o.assertion_id),type:value(o.oracle_type),
      confidence:value(o.confidence),sources:sourceRefs(o.source_refs),
      state:o.oracle_type==='unknown'?'UNKNOWN — no normative oracle':
        'SOURCE CLAIM / REVIEW REQUIRED — not approved by metadata alone',
      approved:false,expected_candidate:o.oracle_type!=='unknown'
    }));
    const oracleById=new Map(oracles.map(x=>[x.assertion_id,x]));
    const requirementByStep=new Map(array(v.step_requirements).map(r=>[r.step_id,r]));
    const steps=array(spec.steps).map(s=>{
      const ids=array(s.assertion_ids), linked=ids.map(x=>oracleById.get(x)).filter(Boolean);
      const scopedSources=[...new Map(linked.flatMap(o=>o.sources).map(x=>[x.ref,x])).values()];
      const req=requirementByStep.get(s.id),associated=stepAssociations.get(s.id);
      return {
        id:value(s.id),oracles:linked,oracle_citations:scopedSources,
        sources:associated.sources,association_state:associated.state,
        attribution:associated.state==='EXPLICIT_CITATION_CLAIM'?
          'EXPLICIT STEP SOURCE CITATION CLAIM — NOT INDEPENDENTLY VERIFIED':
          'STEP-LEVEL SOURCE ATTRIBUTION UNAVAILABLE; oracle-linked expected-value citations are separate from direct step sources',
        capability:req?value(req.capability):'UNASSIGNED',
        operation_class:req?value(req.operation_class):'UNKNOWN',
        permissions:req?array(req.required_permissions):[],
        readbacks:req?array(req.required_readbacks):[],
        readback_state:'REQUIRED CANDIDATES / NOT INDEPENDENTLY OBSERVED',
        approval_required:req?req.approval_required:true,
        execution_gate:'BLOCKED',execution_enabled:false
      };
    });
    // Only the canonical Python compatibility_report can assert MATCHED_PINNED_ONLY.
    const accepted=['UNKNOWN','BLOCKED','MATCHED_PINNED_ONLY'];
    const state=compatibility && accepted.includes(compatibility.state)?
      compatibility.state:'UNKNOWN';
    const reasons=compatibility&&Array.isArray(compatibility.reasons)?
      compatibility.reasons:['Canonical source and engine compatibility not checked on current edit'];
    return {present:true,valid:true,legacy:false,execution_enabled:false,
      independently_verified:false,compatibility:{state,reasons,execution_enabled:false},
      fingerprint_claims:object(v.fingerprints),
      sources,case_association:caseAssociation,association_diagnostics:diagnostics,
      unassigned_sources:sources.filter(src=>scopes.get(src.ref).length===0),
      bindings,oracles,steps,
      message:'Contract v2 metadata is advisory. No capture, source byte, client identity, oracle or permission is independently authenticated.'};
  }
  return {project};
});
