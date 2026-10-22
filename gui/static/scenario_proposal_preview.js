/* #1325 ASI-2 proposal-only display prototype. NONCANONICAL and detached.
 * Only explicitly selected local JSON files; no fetch, editor, storage or runner.
 * Agent C #1200 shape coordination is required before editor attachment.
 */
(function(root, factory) {
  const api=factory();
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ScenarioProposalPreview=api;
})(typeof window!=='undefined'?window:this,function(){
  'use strict';
  const CONTRACT='scenario_revision_proposal_preview_v1_NONCANONICAL';
  const BASE='scenario_revision_baseline_snapshot_v1_NONCANONICAL';
  const PATHS=new Set(['/name','/purpose','/rationale']);
  const SAFE=/^[A-Za-z0-9][A-Za-z0-9_.:\/-]{0,159}$/;
  const exact=(obj,allowed,required=allowed)=>{
    if(!obj||typeof obj!=='object'||Array.isArray(obj))throw Error('Expected bounded JSON object');
    if(Object.keys(obj).some(k=>!allowed.includes(k))||
       required.some(k=>!Object.prototype.hasOwnProperty.call(obj,k)))
      throw Error('Unexpected or missing proposal contract field');
  };
  const text=(x,max=6000)=>typeof x==='string'&&x.length<=max;
  const required=(x,max=6000)=>text(x,max)&&x.trim().length>0;
  function refs(value,name) {
    if(!Array.isArray(value)||value.length>30||
       value.some(v=>!required(v,160)||!SAFE.test(v))||
       new Set(value).size!==value.length)
      throw Error('Invalid or duplicate '+name);
    return value;
  }
  function check(input,proposal,knownProposalIds=[]) {
    exact(input,['contract','revision','spec_digest_claim','specification']);
    if(input.contract!==BASE||!Number.isSafeInteger(input.revision)||input.revision<0)
      throw Error('Invalid selected baseline revision');
    if(input.spec_digest_claim!==null&&
      !(typeof input.spec_digest_claim==='string'&&/^[a-f0-9]{64}$/.test(input.spec_digest_claim)))
      throw Error('Invalid baseline digest claim');
    const spec=input.specification;
    if(!spec||spec.schema_version!==1||!required(spec.feature_id,120)||
       !required(spec.case_id,120)||typeof spec.runner!=='string')
      throw Error('Selected baseline is not a canonical v1 scenario identity');
    exact(proposal,['contract','proposal_id','idempotency_key','scenario','base',
      'changes','reason','feature_trace_refs','source_refs','failure_evidence_refs',
      'coverage_gap_refs','duplicate_scenario_ids','missing_observations',
      'execution_dependencies','expected_candidates','approved_expected','execution_enabled']);
    if(proposal.contract!==CONTRACT||!required(proposal.proposal_id,160)||
       !SAFE.test(proposal.proposal_id)||!required(proposal.idempotency_key,160)||
       !SAFE.test(proposal.idempotency_key))
      throw Error('Unsupported proposal or idempotency identity');
    if(!Array.isArray(knownProposalIds)||
       knownProposalIds.some(v=>!required(v,160))||
       new Set(knownProposalIds).size!==knownProposalIds.length||
       knownProposalIds.includes(proposal.proposal_id))
      throw Error('Duplicate proposal identity');
    exact(proposal.scenario,['feature_id','case_id','schema_version']);
    if(proposal.scenario.schema_version!==1||
       proposal.scenario.feature_id!==spec.feature_id||
       proposal.scenario.case_id!==spec.case_id)
      throw Error('Proposal targets a different canonical case');
    exact(proposal.base,['revision','spec_digest_claim']);
    if(!Number.isSafeInteger(proposal.base.revision)||proposal.base.revision!==input.revision)
      throw Error('STALE_BASE_REVISION: proposal must match operator-selected revision');
    if(proposal.base.spec_digest_claim!==input.spec_digest_claim)
      throw Error('CONFLICTING_BASE_DIGEST_CLAIM: selected snapshots disagree');
    if(!required(proposal.reason,1000)||proposal.approved_expected!==false||
       proposal.execution_enabled!==false)
      throw Error('Proposal cannot claim oracle approval or execution permission');
    for(const name of ['feature_trace_refs','source_refs','failure_evidence_refs',
       'coverage_gap_refs','duplicate_scenario_ids','missing_observations',
       'execution_dependencies'])refs(proposal[name],name);
    if(!Array.isArray(proposal.expected_candidates)||
       proposal.expected_candidates.length>20||
       proposal.expected_candidates.some(x=>!required(x,600)))
      throw Error('Invalid unapproved expected candidates');
    if(!Array.isArray(proposal.changes)||proposal.changes.length<1||
       proposal.changes.length>12)throw Error('Choose 1–12 bounded proposed changes');
    const paths=new Set();
    for(const change of proposal.changes) {
      exact(change,['path','before','after']);
      if(!PATHS.has(change.path))throw Error('Unsupported or protected canonical change path');
      if(paths.has(change.path))throw Error('Conflicting or duplicated proposal changes');
      paths.add(change.path);
      const key=change.path.slice(1);
      if(!text(change.before,2000)||!text(change.after,2000)||
         typeof spec[key]!=='string'||change.before!==spec[key])
        throw Error('CONFLICTING_BEFORE_VALUE: selected baseline differs from proposal');
      if(change.before===change.after)throw Error('No-op change is not a revision proposal');
    }
    const blockers=[];
    if(!proposal.source_refs.length)blockers.push('UNKNOWN: no independently referenced source');
    if(!proposal.feature_trace_refs.length)blockers.push('UNKNOWN: no Feature Trace citations supplied');
    if(proposal.duplicate_scenario_ids.length)
      blockers.push('DUPLICATE_CANDIDATE: manually reconcile referenced cases');
    if(proposal.missing_observations.length)
      blockers.push('UNKNOWN: proposed observations are missing, not verified');
    if(proposal.execution_dependencies.length)
      blockers.push('BLOCKED: dependencies are not granted or executable');
    if(proposal.expected_candidates.length)
      blockers.push('UNAPPROVED: expected outcomes are candidates only');
    if(input.spec_digest_claim===null)
      blockers.push('UNKNOWN: saved spec digest was not supplied');
    // Deliberately return only a human-readable advisory, not a canonical spec
    // or a patch function that could be imported/saved.
    return {contract:CONTRACT,proposal_id:proposal.proposal_id,
      idempotency_key:proposal.idempotency_key,scenario:proposal.scenario,
      base_revision:input.revision,base_digest_claim:input.spec_digest_claim,
      reason:proposal.reason,changes:proposal.changes,
      feature_trace_refs:proposal.feature_trace_refs,source_refs:proposal.source_refs,
      failure_evidence_refs:proposal.failure_evidence_refs,
      coverage_gap_refs:proposal.coverage_gap_refs,
      duplicate_scenario_ids:proposal.duplicate_scenario_ids,
      missing_observations:proposal.missing_observations,
      execution_dependencies:proposal.execution_dependencies,
      expected_candidates:proposal.expected_candidates,blockers,
      source_authenticated:false,base_revision_authenticated:false,canonical_schema_validated:false,
      canonical_case_step_approval:'UNASSIGNED',normative_expected:null,
      reviewer_action_enabled:false,save_allowed:false,
      approved_expected:false,execution_enabled:false};
  }
  const el=(tag,content)=>{
    const e=document.createElement(tag);
    if(content!==undefined)e.textContent=String(content);
    return e;
  };
  const line=(host,s)=>host.append(el('p',s));
  function render(host,view){
    if(!view||view.contract!==CONTRACT||view.save_allowed!==false||
       view.execution_enabled!==false||view.approved_expected!==false||
       view.reviewer_action_enabled!==false||view.normative_expected!==null)
      throw Error('Untrusted proposal cannot become an approved editor state');
    const root=el('section');
    root.append(el('h3','Untrusted candidate '+view.proposal_id+' — READ ONLY / NOT APPROVED'));
    line(root,'Case '+view.scenario.feature_id+'/'+view.scenario.case_id+
      ' · operator-declared baseline revision '+view.base_revision);
    line(root,'Spec digest CLAIM '+(view.base_digest_claim||'UNKNOWN / NOT VERIFIED'));
    line(root,'Baseline schema/revision NOT independently validated; supplied local JSON is not a persisted draft record.');
    line(root,'Reason: '+view.reason);
    line(root,'Before / after are proposals only, NOT saved changes:');
    for(const c of view.changes) {
      const row=el('article');row.append(el('h4',c.path));
      line(row,'BEFORE (selected baseline): '+c.before);
      line(row,'AFTER (unapproved candidate): '+c.after);
      root.append(row);
    }
    for(const name of ['feature_trace_refs','source_refs','failure_evidence_refs',
       'coverage_gap_refs','duplicate_scenario_ids','missing_observations',
       'execution_dependencies','expected_candidates']) {
      const labels={source_refs:'Source declarations',feature_trace_refs:'Feature Trace claims',
        failure_evidence_refs:'Failure evidence claims',coverage_gap_refs:'Coverage-gap claims',
        duplicate_scenario_ids:'Possible duplicates',
        missing_observations:'Missing observations',execution_dependencies:'Blocked dependencies',
        expected_candidates:'UNAPPROVED expected-value candidates'};
      line(root,labels[name]+': '+(view[name].length?view[name].join(' | '):'NONE / UNKNOWN'));
    }
    view.blockers.forEach(v=>line(root,v));
    line(root,'No approval, authenticated source, canonical CASE/STEP attribution, import, save or execution.');
    host.replaceChildren(root);return root;
  }
  function mount(host) {
    const section=el('section');
    section.append(el('h3','Optional ASI candidate revision — synthetic-only preview'));
    line(section,'Select a baseline snapshot JSON and an independently supplied proposal JSON. These are untrusted declarations; nothing is applied to the Scenario Developer.');
    const baseline=el('input'),proposal=el('input'),go=el('button','Inspect proposed diff (read only)');
    baseline.type='file';proposal.type='file';baseline.accept=proposal.accept='.json,application/json';go.type='button';
    const status=el('p','No proposal inspected; no draft changed'),output=el('div');
    section.append(el('label','Baseline snapshot JSON'),baseline,
      el('label','Unapproved proposal JSON'),proposal,go,status,output);
    host.replaceChildren(section);
    let seq=0,disposed=false,pending=false;
    function invalidate() {
      ++seq;output.replaceChildren();
      status.textContent='Selected inputs changed; inspect current pair again.';
    }
    baseline.addEventListener('change',invalidate);
    proposal.addEventListener('change',invalidate);
    go.addEventListener('click',async()=>{
      if(disposed||pending)return;
      const generation=++seq,a=baseline.files?.[0],b=proposal.files?.[0];
      output.replaceChildren();
      try {
        if(!a||!b||a.size<1||b.size<1||a.size>131072||b.size>131072)
          throw Error('Choose two nonempty JSON files, maximum 128 KiB each');
        pending=true;go.disabled=true;
        const [original,claim]=await Promise.all([a.text(),b.text()]);
        if(disposed||generation!==seq||baseline.files?.[0]!==a||proposal.files?.[0]!==b)return;
        const result=check(JSON.parse(original),JSON.parse(claim));
        if(disposed||generation!==seq||baseline.files?.[0]!==a||proposal.files?.[0]!==b)return;
        render(output,result);
        status.textContent='Untrusted read-only proposal preview; not imported or approved.';
      } catch(error) {
        if(!disposed&&generation===seq){
          output.replaceChildren();status.textContent='Proposal refused: '+error.message;
        }
      } finally {pending=false;go.disabled=disposed;}
    });
    function dispose(){
      disposed=true;++seq;output.replaceChildren();
      baseline.disabled=proposal.disabled=go.disabled=true;
      status.textContent='Proposal preview closed; no editor state changed.';
    }
    return {baseline,proposal,go,status,output,dispose};
  }
  return {check,render,mount,CONTRACT,BASE};
});
