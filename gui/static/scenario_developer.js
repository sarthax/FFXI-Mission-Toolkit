/* Guided Scenario Developer: canonical draft JSON only. Never dispatches gameplay actions. */
(function () {
  'use strict';
  const M = window.ScenarioGuidedModel, V = window.ScenarioContractV2View;
  const Feedback = window.ScenarioValidationFeedback;
  const L = window.ScenarioLabels || {observation:String,observationHint:()=>'',operation:String,
    operationHint:()=>'',groupOf:()=>'Other',sentence:()=>'',noExpected:()=>false,groups:()=>[]};
  const $ = id => document.getElementById(id);
  let spec = M.fresh(), mode = 'guided', options = {features: [], observations: [], operations: []};
  let drafts = [], baseline = null, sourceDetail = null;
  let readinessViewer = null;
  let draftGuard = null, editorReady = false;
  function updateRevision() {
    const currentRevision = Number($('sd-revision').value) || 0;
    if(draftGuard){draftGuard.refresh();return;}
    $('sd-revision-state').textContent = M.revisionIndicator(baseline,spec,currentRevision);
  }
  function updateAdvancedRevision() {
    if(mode!=='advanced')return; // hidden scripted events must not change Guided state
    if(draftGuard){draftGuard.refresh();return;}
    $('sd-revision-state').textContent=M.advancedRevisionIndicator(
      baseline,$('sd-advanced-json').value,Number($('sd-revision').value)||0);
  }
  // Only after a confirmed replacement; never from render(): it would
  // overwrite uncommitted Advanced JSON text before discard confirmation.
  function syncAdvancedAfterReplacement() {
    if(typeof Feedback!=='undefined'&&Feedback)Feedback.clear();
    $('sd-advanced-json').value=JSON.stringify(spec,null,2);
    $('sd-guided').setAttribute('aria-pressed','true');
    $('sd-advanced').setAttribute('aria-pressed','false');
  }
  function renderCatalogSteps() {
    const select = $('sd-catalog-step'), selected = select.value;
    select.replaceChildren();
    for (const step of spec.steps) {
      const opt = el('option','',step.id+' — '+step.title);
      opt.value=step.id; opt.selected=step.id===selected; select.append(opt);
    }
  }
  function setSourceDetail(feature, caseId) {
    const link=$('sd-source-detail');
    if(feature&&caseId&&/^[a-zA-Z0-9_-]+$/.test(feature)&&/^[a-zA-Z0-9_-]+$/.test(caseId)) {
      sourceDetail={feature,caseId};
      link.href='/feature-testing/scenario/'+encodeURIComponent(feature)+'/'+encodeURIComponent(caseId);
      link.textContent='Open source Scenario Detail ('+caseId+')';link.hidden=false;
    } else {sourceDetail=null;link.hidden=true;}
  }

  const lineItems = value => value.split('\n').map(s => s.trim()).filter(Boolean);
  const show = text => { $('sd-result').textContent = text; };
  const el = (tag, cls, text) => {
    const x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text !== undefined) x.textContent = text;
    return x;
  };
  const field = (label, control) => {
    const f = el('label','sd-field');
    f.append(document.createTextNode(label), control);
    return f;
  };
  function input(value, maxlength=500) {
    const e = el('input');
    e.type = 'text'; e.maxLength = maxlength; e.value = value == null ? '' : String(value);
    return e;
  }
  function textarea(value) {
    const e = el('textarea'); e.rows = 2; e.maxLength = 1000; e.value = value || ''; return e;
  }
  function pickList(values, selected) {
    const select = el('select');
    select.multiple = true; select.size = Math.min(6, Math.max(3, values.length));
    const choices = [...new Set([...values, ...(selected || [])])];
    for (const name of choices) {
      const o = el('option', '', L.observation(name) + (values.includes(name) ? '' : ' — UNKNOWN reference'));
      o.title = L.observationHint(name);
      o.value = name; o.selected = (selected || []).includes(name); select.append(o);
    }
    return select;
  }
  const selections = select => [...select.selectedOptions].map(x => x.value);

  function renderAssertions() {
    const host = $('sd-assertions'); host.replaceChildren();
    spec.assertions.forEach((row, i) => {
      const card = el('article','sd-card');
      const h = el('header'); h.append(el('strong','', 'Check ' + (i+1) + ' · not yet run'));
      const remove = el('button', '', 'Remove this check'); remove.type = 'button';
      remove.addEventListener('click', () => {
        spec.assertions.splice(i,1); renderAssertions(); renderSteps(); diagnostics();
      }); h.append(remove); card.append(h);
      const grid = el('div','sd-grid');
      const id = input(row.id,64); id.addEventListener('input', () => {
        row.id = id.value; renderSteps(); diagnostics();
      });
      grid.append(field('Check name (short ID, used to link it to a step)', id));
      const op = el('select');
      for (const value of new Set([...options.operations, row.operation])) {
        const o = el('option','',L.operation(value));o.value=value;o.title=L.operationHint(value);o.selected=value===row.operation;op.append(o);
      }
      const summary = el('p','sd-muted');
      const refresh = () => {summary.textContent=L.sentence(row);expected.disabled=L.noExpected(row.operation);};
      op.addEventListener('change', () => {row.operation=op.value;refresh();diagnostics();});
      const opField=field('Must be (how to compare)',op);
      const observed = el('select');
      for (const value of new Set([...options.observations,row.observed])) {
        const o = el('option','',L.observation(value));o.value=value;o.title=L.observationHint(value);o.selected=value===row.observed;observed.append(o);
      }
      observed.addEventListener('change', () => {row.observed=observed.value;refresh();diagnostics();});
      grid.append(field('What to look at',observed));grid.append(opField);
      const expected = input(JSON.stringify(row.expected),500);
      expected.addEventListener('change', () => {
        try {row.expected=JSON.parse(expected.value);expected.setCustomValidity('');}
        catch (e) {expected.setCustomValidity('Enter a value like "text", 3, [1,2] or null');}
        refresh();diagnostics();
      });
      grid.append(field('Expected value ("text", 3, [1,2] or null; unused by is-not-empty / all-zeros)',expected));
      refresh();
      card.append(grid,summary);host.append(card);
    });
  }

  function renderSteps() {
    const host = $('sd-steps');host.replaceChildren();
    spec.steps.forEach((step, i) => {
      const li = el('li','sd-card');
      const header=el('header');
      header.append(el('strong','', 'Step ' + (i+1) + ' · expected result not yet source-backed'));
      const toolbar=el('div','sd-controls');
      for (const [label, offset] of [['↑ Up',-1], ['↓ Down',1]]) {
        const b=el('button','',label);b.type='button';
        b.disabled = i+offset < 0 || i+offset >= spec.steps.length;
        b.addEventListener('click',()=>{readGuidedFields();spec=M.moveStep(spec,i,offset);renderSteps();diagnostics();});
        toolbar.append(b);
      }
      const remove=el('button','','Remove');
      remove.type='button';remove.addEventListener('click',()=>{
        spec=M.deleteStep(spec,i);renderSteps();diagnostics();
      });
      toolbar.append(remove);header.append(toolbar);li.append(header);
      const grid=el('div','sd-grid');
      const fields=[
        ['Stable step ID','id',input(step.id,120)],
        ['Step title','title',input(step.title,500)],
        ['Expected outcome (UNKNOWN until source-backed)','expected',textarea(step.expected)],
      ];
      for (const [caption,key,control] of fields) {
        control.addEventListener('input',()=>{step[key]=control.value;diagnostics();});
        grid.append(field(caption,control));
      }
      const intent=el('select');
      for(const x of ['observation','read_only_comparison','read_only_gm_diagnostic']) {
        const opt=el('option','',x);opt.value=x;opt.selected=x===step.intent;intent.append(opt);
      }
      if (![...intent.options].some(o=>o.value===step.intent)) {
        const opt=el('option','','UNSUPPORTED: '+step.intent);opt.value=step.intent;opt.selected=true;intent.append(opt);
      }
      intent.addEventListener('change',()=>{step.intent=intent.value;diagnostics();});
      grid.append(field('What kind of step (all are read-only)',intent));
      const technical=el('details');
      staticText(technical,'summary','Link observations and assertions to this step (technical)');
      const confidence=textarea(step.confidence_note);
      confidence.addEventListener('input',()=>{step.confidence_note=confidence.value;diagnostics();});
      technical.append(field('Evidence limitations and unverified catalog candidates',confidence));
      const assertionIds=pickList(spec.assertions.map(a=>a.id),step.assertion_ids);
      assertionIds.addEventListener('change',()=>{step.assertion_ids=selections(assertionIds);diagnostics();});
      technical.append(field('Linked assertion IDs',assertionIds));
      const refs=pickList(spec.observations,step.evidence_refs);
      refs.addEventListener('change',()=>{step.evidence_refs=selections(refs);diagnostics();});
      technical.append(field('Required canonical observations',refs));
      li.append(grid,technical);
      host.append(li);
    });
    renderCatalogSteps();
  }

  // The typed builder is read-only exactly while Advanced JSON is the document, whichever path got us here.
  function syncTypedLock() {
    const locked=mode==='advanced';
    const panel=document.getElementById&&document.getElementById('sd-typed-steps');if(panel)panel.inert=locked;
    if(window.ScenarioTypedSteps&&window.ScenarioTypedSteps.bridge)window.ScenarioTypedSteps.bridge.setLocked(locked);
  }
  function render() {
    syncTypedLock();
    if(window.ScenarioTypedSteps&&window.ScenarioTypedSteps.bridge)window.ScenarioTypedSteps.bridge.sync(spec.native_steps);
    $('sd-case').value=spec.case_id;
    $('sd-title').value=spec.name;
    $('sd-purpose').value=spec.purpose||'';
    $('sd-rationale').value=spec.rationale||'';
    for(const phase of ['given','when','then'])
      $('sd-'+phase).value=((spec.behavior||{})[phase]||[]).join('\n');
    $('sd-preconditions').value=spec.preconditions.join('\n');
    $('sd-cleanup').value=spec.cleanup.join('\n');
    $('sd-gaps').value=((spec.authoring||{}).blocking_gaps||[]).join('\n');
    const feature=$('sd-feature'); feature.replaceChildren();
    const configured=options.features.map(x=>x.id);
    for(const item of options.features) {
      const opt=el('option','',item.name+' ('+item.id+')');
      opt.value=item.id;opt.selected=spec.feature_id===item.id;feature.append(opt);
    }
    if(!configured.includes(spec.feature_id)) {
      const opt=el('option','','UNRESOLVED: '+spec.feature_id);opt.value=spec.feature_id;opt.selected=true;feature.append(opt);
    }
    const obs=$('sd-observations');obs.replaceChildren();
    const names=[...new Set([...options.observations,...spec.observations])];
    const rank=n=>{const i=L.groups().indexOf(L.groupOf(n));return i<0?99:i;};
    names.sort((x,y)=>rank(x)-rank(y));
    for(const name of names) {
      const opt=el('option','',L.observation(name)+(options.observations.includes(name)?'':' — unsupported'));
      opt.value=name;opt.title=L.groupOf(name)+' — '+L.observationHint(name);opt.selected=spec.observations.includes(name);
      opt.dataset.search=(L.observation(name)+' '+name+' '+L.observationHint(name)+' '+L.groupOf(name)).toLowerCase();
      obs.append(opt);
    }
    renderAssertions();renderSteps();diagnostics();updateRevision();
  }

  function readGuidedFields() {
    spec.feature_id=$('sd-feature').value;
    spec.case_id=$('sd-case').value.trim();
    spec.name=$('sd-title').value.trim();
    spec.purpose=$('sd-purpose').value.trim();
    spec.rationale=$('sd-rationale').value.trim();
    spec.behavior=spec.behavior||{};
    for(const phase of ['given','when','then'])
      spec.behavior[phase]=lineItems($('sd-'+phase).value);
    spec.preconditions=lineItems($('sd-preconditions').value);
    spec.cleanup=lineItems($('sd-cleanup').value);
    spec.observations=selections($('sd-observations'));
    spec.authoring=spec.authoring||{};
    spec.authoring.blocking_gaps=lineItems($('sd-gaps').value);
    // Typed builder steps live in spec.native_steps. A null answer means the builder is not showing the draft's
    // steps (still loading, unavailable, or unable to display them); then the saved steps are left exactly as they are.
    const bridge=window.ScenarioTypedSteps&&window.ScenarioTypedSteps.bridge;
    const typed=bridge&&bridge.get();
    if(typed&&!bridge.sameSteps(typed.native,spec.native_steps||null)){
      if(typed.native)spec.native_steps=typed.native;else delete spec.native_steps;
    }
  }
  function current() {
    if(mode==='advanced') spec=M.parseAdvanced($('sd-advanced-json').value);
    else readGuidedFields();
    return spec;
  }
  function diagnostics() {
    updateRevision();
    renderContractV2(null);
    const problems=M.referenceIssues(spec);
    if(problems.length)show('Local reference warnings (validate on server):\n'+problems.join('\n'));
  }
  function switchMode(target) {
    try {current();}
    catch(err){show('Cannot switch mode: '+err.message);return;}
    if(mode!==target)resetReadinessViewer();
    mode=target;
    // In Advanced the JSON text is the document, so the builder is read-only until Guided returns.
    syncTypedLock();
    $('sd-guided-panel').hidden=target!=='guided';
    $('sd-advanced-panel').hidden=target!=='advanced';
    $('sd-guided').setAttribute('aria-pressed',String(target==='guided'));
    $('sd-advanced').setAttribute('aria-pressed',String(target==='advanced'));
    if(target==='advanced'){
      $('sd-advanced-json').value=JSON.stringify(spec,null,2);
      updateAdvancedRevision();
    }else render();
  }
  function staticText(parent,tag,value){
    const x=el(tag,'',value);parent.append(x);return x;
  }
  // The existing editor owns all draft mutations; this panel is display-only.
  // Show only explicit canonical source relationships. No client-side verification.
  function renderContractV2(compatibility, draft=spec, associationReport=null) {
    const host=$('sd-contract-v2');
    if(!host || !V)return;
    const open=new Set([...host.querySelectorAll('details[open]')].map(d=>d.dataset.key));
    host.replaceChildren();
    let projection;
    try{projection=V.project(draft,compatibility,associationReport);}
    catch(e){staticText(host,'p','Optional metadata cannot be projected; canonical validation required: '+e.message);return;}
    if(!projection.present){staticText(host,'p',projection.message);return;}
    if(!projection.valid){staticText(host,'p',projection.message);return;}
    const detail=(key,title)=>{
      const d=el('details');d.dataset.key=key;d.open=open.has(key);
      staticText(d,'summary',title);host.append(d);return d;
    };
    staticText(host,'p',projection.message);
    staticText(host,'p','Compatibility: '+projection.compatibility.state+
      ' · NON-EXECUTABLE · independent verification NOT ESTABLISHED');
    for(const reason of projection.compatibility.reasons)staticText(host,'p','Compatibility reason: '+reason);
    for(const diagnostic of projection.association_diagnostics)
      staticText(host,'p','Source association diagnostic: '+diagnostic);
    const caseScope=detail('case-citations','Explicit CASE-level citations — '+projection.case_association.state);
    if(!projection.case_association.sources.length)
      staticText(caseScope,'p','UNKNOWN / UNASSIGNED — declared registry entries are not case citations');
    for(const src of projection.case_association.sources){
      staticText(caseScope,'p',src.ref+' · '+src.repository+'/'+src.path+':'+src.line_range+
        ' · revision '+src.revision+' · SHA-256 '+src.digest+
        ' · '+src.digest_state+' · citation claim ONLY; not authenticated');
    }
    const pins=detail('fingerprints','Engine and base-spec fingerprint claims');
    for(const [key,v] of Object.entries(projection.fingerprint_claims))
      staticText(pins,'p',key+': '+(v===null?'UNKNOWN':String(v))+' (declared only)');
    const cases=detail('sources','Declared source registry and explicit scopes ('+projection.sources.length+')');
    if(!projection.sources.length)staticText(cases,'p','UNKNOWN — no pinned source records');
    for(const src of projection.sources) {
      const d=el('div','sd-preview-step');
      staticText(d,'strong',src.ref+' — '+src.classification);
      staticText(d,'p',src.repository+'/'+src.path+':'+src.line_range);
      staticText(d,'p','Revision: '+src.revision+' · SHA-256: '+src.digest);
      staticText(d,'p',src.digest_state+' · '+src.attribution);cases.append(d);
    }
    const unassigned=detail('unassigned','UNASSIGNED declared sources ('+projection.unassigned_sources.length+')');
    if(!projection.unassigned_sources.length)staticText(unassigned,'p','No unassigned source records');
    for(const src of projection.unassigned_sources)
      staticText(unassigned,'p',src.ref+' · '+src.repository+'/'+src.path+':'+src.line_range+
        ' · '+src.digest_state+' · NO EXPLICIT CASE/STEP CITATION');
    const bindings=detail('bindings','Typed identity candidates ('+projection.bindings.length+')');
    if(!projection.bindings.length)staticText(bindings,'p','No canonical v2 parameters declared');
    for(const b of projection.bindings) {
      const d=el('div','sd-preview-step');
      staticText(d,'strong',b.name+' — '+b.kind+' / '+b.state);
      staticText(d,'p','Identity: '+b.identity+' · namespace: '+b.namespace+' · zone: '+b.zone_id);
      staticText(d,'p',b.claim+' · '+b.attribution);
      staticText(d,'p','Source refs: '+(b.sources.map(x=>x.ref).join(', ')||'NONE'));
      bindings.append(d);
    }
    const oracles=detail('oracles','Oracle claims / expected-value candidates ('+projection.oracles.length+')');
    if(!projection.oracles.length)staticText(oracles,'p','UNKNOWN — no accepted oracle metadata');
    for(const o of projection.oracles) {
      staticText(oracles,'p',o.assertion_id+': '+o.type+' / '+o.confidence+' — '+o.state+
        '; source refs: '+(o.sources.map(x=>x.ref).join(', ')||'NONE'));
    }
    for(const step of projection.steps) {
      const d=detail('step:'+step.id,'Step '+step.id+' — '+step.attribution);
      staticText(d,'p','Canonical direct STEP citations — '+step.association_state+': '+
        (step.sources.map(x=>x.repository+'/'+x.path+':'+x.line_range).join(' | ')||'UNKNOWN / UNASSIGNED'));
      staticText(d,'p','Oracle-linked expected-value candidate sources (NOT step attribution or approval): '+
        (step.oracle_citations.map(x=>x.repository+'/'+x.path+':'+x.line_range).join(' | ')||'NONE'));
      staticText(d,'p','Candidate capability: '+step.capability+'; operation class: '+step.operation_class);
      staticText(d,'p','Required permissions (NOT GRANTED): '+
        (step.permissions.join(', ')||'NONE DECLARED')+
        '; operator approval required: '+String(step.approval_required));
      staticText(d,'p','Missing client/server readbacks: '+(step.readbacks.join(', ')||'NONE DECLARED'));
      staticText(d,'p',step.readback_state+'; execution: '+step.execution_gate);
    }
  }

  function renderPreview(view, reader, compatibility, associationReport) {
    renderContractV2(compatibility,spec,associationReport);
    const root=$('sd-preview');root.replaceChildren();root.hidden=false;
    staticText(root,'h2',view.title+' — Scenario detail preview');
    staticText(root,'p',view.purpose);
    staticText(root,'p','Maturity: '+view.maturity+' · independently verified: '+view.independent_verification);
    staticText(root,'p','Recorded verdict: UNKNOWN · Recalculated verdict: UNKNOWN · Catalog identity: '+view.catalog_identity);
    for(const phase of ['given','when','then']){
      staticText(root,'h3',phase[0].toUpperCase()+phase.slice(1));
      const list=el('ul');
      for(const note of view.behavior[phase])staticText(list,'li',note);
      root.append(list);
    }
    staticText(root,'h3','Ordered steps — expected vs observed');
    for(const step of view.steps){
      const card=el('section','sd-preview-step');
      staticText(card,'h4',step.id+' · '+step.title+' · '+step.verdict);
      const pair=el('div','sd-pair');
      const a=el('div'),b=el('div');
      staticText(a,'strong','Expected');staticText(a,'p',step.expected);
      staticText(b,'strong','Observed');staticText(b,'p',step.observed);
      pair.append(a,b);card.append(pair);
      const details=el('details');staticText(details,'summary','Assertion mapping and provenance');
      staticText(details,'p','Assertion IDs: '+step.assertion_ids.join(', '));
      staticText(details,'p','Required observations: '+step.evidence_refs.join(', '));
      staticText(details,'p','Source identity: UNRESOLVED; '+(step.confidence_note||'not supplied'));
      card.append(details);root.append(card);
    }
    if(reader && reader.available) {
      staticText(root,'p','Scenario Detail presentation: '+reader.mapped_assertion_count+' of '+reader.assertion_count+' assertion contracts mapped; independent verification '+reader.independent_verification);
      for(const step of reader.steps) {
        const detail=el('details');
        staticText(detail,'summary','Scenario Detail step '+step.number+': '+step.id+' — '+step.status);
        for(const a of step.assertions)staticText(detail,'p',a.id+' — '+a.status+'; '+a.reason+' (no independent observation)');
        for(const ref of step.provenance)staticText(detail,'p',ref.field+': UNKNOWN — no authenticated source evidence');
        root.append(detail);
      }
    }
    if(view.unmapped_assertions.length)staticText(root,'p','Unmapped assertions: '+view.unmapped_assertions.join(', '));
    if(view.unresolved_expected_steps.length)staticText(root,'p','UNKNOWN source oracles: '+view.unresolved_expected_steps.join(', '));
    for(const gap of view.blocking_gaps)staticText(root,'p','BLOCKED / needs review: '+gap);
  }

  function renderIncompletePreview() {
    renderContractV2(null);
    // A planning preview is not canonical acceptance; it never runs the
    // assertions, reads a capture or promotes a proposed expectation.
    const root=$('sd-preview');root.replaceChildren();root.hidden=false;
    staticText(root,'h2','Incomplete authoring preview — DESIGN_ONLY / NOT VALIDATED');
    staticText(root,'p','Source provenance (UNVERIFIED): '+(spec.rationale||'NONE'));
    staticText(root,'p','New case ID: '+(spec.case_id||'NOT PROVIDED — choose a unique ID'));
    staticText(root,'p','Normative expected results: UNKNOWN until independently sourced');
    for(const step of spec.steps) {
      const card=el('article','sd-preview-step');
      staticText(card,'h3',step.title+' — UNKNOWN');
      const pair=el('div','sd-pair'),observed=el('div'),expected=el('div');
      staticText(observed,'strong','OBSERVED / provisional');
      staticText(observed,'p',step.title);
      staticText(expected,'strong','EXPECTED / normative');
      staticText(expected,'p',step.expected);
      pair.append(observed,expected);card.append(pair);
      staticText(card,'p','Indexed source notes: '+(step.confidence_note||'UNKNOWN'));
      root.append(card);
    }
    staticText(root,'p','Assertions and canonical observations must be authored separately. Preview does NOT save, verify or execute.');
  }
  $('sd-preview-incomplete').addEventListener('click',()=>{
    try {current();renderIncompletePreview();show('Provisional design preview only — no canonical validation, saving or execution.');}
    catch(e){show('Draft preview unavailable: '+e.message);}
  });

  async function call(path,method,body,auth) {
    const headers={'X-Requested-With':'toolkit-ui'};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(auth)headers['X-Test-Operator-Token']=$('sd-token').value;
    const response=await fetch(path,{method:method||'GET',headers,credentials:'same-origin',
      body:body===undefined?undefined:JSON.stringify(body)});
    const value=await response.json();
    if(!response.ok) {
      const detail=value.detail;
      const error=new Error(typeof detail==='string'?detail:
        (detail && typeof detail.message==='string'?detail.message+
          ': '+(typeof detail.canonical_error==='string'?detail.canonical_error:'invalid fields'):
         'HTTP '+response.status));
      // Only the validation endpoint owns this non-authoritative advisory shape.
      if(path==='/scenario-developer/validate' && detail &&
         Array.isArray(detail.errors))error.validationErrors=detail.errors;
      throw error;
    }
    return value;
  }
  // Only the latest Validate/Save request owns preview, status and field errors.
  // A stale response must be a complete UI no-op, including clear/hide/show.
  let validationUiRequest = 0;
  // A failed asynchronous validation must not paint errors on another draft
  // or on Guided/Advanced edits made after the request was sent.
  function validationRequestCurrent(generation, snapshot, revision=null) {
    if(generation!==editorGeneration ||
       (revision!==null && Number($('sd-revision').value)!==revision))return false;
    try{return JSON.stringify(current())===JSON.stringify(snapshot);}
    catch(e){return false;} // Invalid Advanced JSON is preserved, never repaired.
  }
  async function validatePreview() {
    const uiRequest=validationUiRequest;
    const generation=editorGeneration, input=M.clone(current());
    let result;
    try{result=await call('/scenario-developer/validate','POST',{specification:input});}
    catch(e){
      if(uiRequest!==validationUiRequest || generation!==editorGeneration ||
         !validationRequestCurrent(generation,input))return; // Preview is stale: no UI mutation or outer catch dispatch
      throw e;
    }
    if(uiRequest!==validationUiRequest || generation!==editorGeneration ||
       !validationRequestCurrent(generation,input))return; // obsolete success must not overwrite a newer preview
    if(Feedback)Feedback.clear();
    renderPreview(result.preview,result.reader_view,result.contract_v2_compatibility,result.contract_v2_source_attribution);
    show('Canonical validation accepted — DESIGN_ONLY, unreviewed, not executable.\n'+
      result.warnings.join('\n'));
    return result;
  }

  let editorGeneration=0, forkPending=false;
  function confirmDocumentReplacement(action) {
    if (savePending) throw Error('A save is in progress. Finish that request before replacing this draft.');
    current(); // Read unsaved Guided fields or validate Advanced JSON first.
    const reason=M.replacementConfirmationReason(spec,baseline,Number($('sd-revision').value),activeHandoff);
    return !reason || window.confirm(action+' will replace '+reason+'. Discard that context and continue?');
  }
  $('sd-guided').addEventListener('click',()=>switchMode('guided'));
  $('sd-advanced').addEventListener('click',()=>switchMode('advanced'));
  $('sd-advanced-json').addEventListener('input',()=>{
    // Unapplied Advanced edits are *displayed as provisional*, not silently
    // copied to spec, validated, saved, or promoted into verified metadata.
    try{renderContractV2(null,M.parseAdvanced($('sd-advanced-json').value));}
    catch(e){$('sd-contract-v2').textContent='Advanced JSON pending canonical validation: '+e.message;}
  });
  $('sd-apply-json').addEventListener('click',()=>switchMode('guided'));
  $('sd-new').addEventListener('click',()=>{
    try {
      if(!confirmDocumentReplacement('New scenario'))return;
      editorGeneration++;resetReadinessViewer();clearValidationSummary();
      activeHandoff=null;spec=M.fresh();mode='guided';baseline=null;draftGuard.start('new',spec);setSourceDetail(null,null);$('sd-revision').value=0;
      $('sd-context-use').disabled=!coverageContext;
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
      syncAdvancedAfterReplacement();render();show('Created a synthetic, design-only canonical draft.');
    }catch(e){show('New scenario refused: '+e.message);}
  });
  $('sd-fork').addEventListener('click',async()=>{
    if(forkPending)return;
    forkPending=true;$('sd-fork').disabled=true;
    const startedGeneration=editorGeneration;
    try{
      if(savePending)throw Error('Save in progress; cannot switch drafts');
      const [feature,caseId]=$('sd-seed-select').value.split('/');
      if(!feature||!caseId)throw Error('Choose a published case to fork');
      const x=await call('/scenario-developer/seed/'+encodeURIComponent(feature)+'/'+encodeURIComponent(caseId));
      if(startedGeneration!==editorGeneration)
        throw Error('Editor changed while loading the published case; retry');
      const draft=M.forkPublished(x.specification);
      if(!confirmDocumentReplacement('Fork published case'))return;
      editorGeneration++;resetReadinessViewer();clearValidationSummary();
      activeHandoff=null;spec=draft;mode='guided';baseline=null;draftGuard.start('fork',spec);setSourceDetail(feature,caseId);
      $('sd-revision').value=0;$('sd-advanced-panel').hidden=true;
      $('sd-guided-panel').hidden=false;syncAdvancedAfterReplacement();render();
      show('Copied as DESIGN_ONLY with a new synthetic case ID. Original published case unchanged.');
    }catch(e){show('Fork refused: '+e.message);}
    finally{forkPending=false;$('sd-fork').disabled=false;}
  });
  $('sd-clone').addEventListener('click',()=>{
    try {
      const draft=M.cloneDraft(current());
      if(!confirmDocumentReplacement('Clone current draft'))return;
      editorGeneration++;resetReadinessViewer();clearValidationSummary();
      activeHandoff=null;spec=draft;mode='guided';baseline=null;draftGuard.start('clone',spec);$('sd-revision').value=0;
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
      syncAdvancedAfterReplacement();render();show('Cloned into a new draft case ID. Rename it if a COPY already exists; source identities still require review.');
    } catch(e){show('Clone refused: '+e.message);}
  });
  $('sd-add-assertion').addEventListener('click',()=>{
    readGuidedFields();
    let n=1,id;const ids=new Set(spec.assertions.map(a=>a.id));
    do{id='assertion_'+String(n++).padStart(2,'0');}while(ids.has(id));
    spec.assertions.push({id,operation:'nonempty',observed:spec.observations[0]||'client_bag',expected:null});
    renderAssertions();renderSteps();diagnostics();
  });
  const ST=window.ScenarioStepTemplates;
  const tplSelect=$('sd-template');
  if(ST&&tplSelect&&tplSelect.append){
    for(const t of ST.list()){const o=el('option','',t.label);o.value=t.key;o.dataset.subject=t.subject;tplSelect.append(o);}
    const syncSubject=()=>{
      const sel=tplSelect.selectedOptions&&tplSelect.selectedOptions[0];
      const subj=sel?sel.dataset.subject:'';
      $('sd-template-subject-label').hidden=!subj;
      if(subj)$('sd-template-subject-label').firstChild.textContent=subj+' (optional)';
    };
    tplSelect.addEventListener('change',syncSubject);syncSubject();
    $('sd-add-template').addEventListener('click',()=>{
      try{
        readGuidedFields();
        const before=spec.steps.length;
        spec=ST.apply(spec,tplSelect.value,$('sd-template-subject').value);
        render();
        show('Added step '+(before+1)+' from template with its checks. Review the wording; nothing was run.');
      }catch(e){show('Template refused: '+e.message);}
    });
  }
  $('sd-add-step').addEventListener('click',()=>{
    readGuidedFields();spec=M.addStep(spec);renderSteps();diagnostics();
  });
  $('sd-feature').addEventListener('change',diagnostics);
  $('sd-observations').addEventListener('change',()=>{readGuidedFields();renderSteps();diagnostics();});
  const obsFilter=$('sd-observation-filter');
  if(obsFilter&&obsFilter.addEventListener)obsFilter.addEventListener('input',()=>{
    const q=obsFilter.value.trim().toLowerCase();
    for(const o of $('sd-observations').querySelectorAll('option'))
      o.hidden=!!q&&!o.selected&&!(o.dataset.search||'').includes(q);
  });
  $('sd-validate').addEventListener('click',async()=>{
    const uiRequest=++validationUiRequest;
    try{await validatePreview();}
    catch(e){
      if(uiRequest!==validationUiRequest)return; // previous request cannot hide/clear newer UI
      $('sd-preview').hidden=true;
      if(Feedback)Feedback.show(e.validationErrors);
      show('Canonical validation rejected: '+e.message+'\n'+M.referenceIssues(spec).join('\n'));
    }
  });
  let savePending=false;
  $('sd-save').addEventListener('click',async()=>{
    if(savePending)return;
    const uiRequest=++validationUiRequest;
    savePending=true;$('sd-save').disabled=true;
    const generation=editorGeneration;
    let submitted=null, submittedRevision=null;
    try {
      if(!$('sd-token').value)throw Error('Enter a local operator token; a preview never grants save permission');
      // Keep an immutable copy of exactly what the operator asked to save.
      // The validation round-trip is async, and Guided/Advanced may be edited
      // while either response is in flight.
      const input=M.clone(current()),rev=Number($('sd-revision').value);
      submitted=input;submittedRevision=rev;
      if(!Number.isInteger(rev)||rev<0)throw Error('Invalid expected revision');
      const validated=await call('/scenario-developer/validate','POST',{specification:input});
      if(uiRequest!==validationUiRequest || !validationRequestCurrent(generation,input,rev))
        return; // superseded preflight must not dispatch a draft Save or change newer UI
      if(Feedback)Feedback.clear();
      renderPreview(validated.preview,validated.reader_view,validated.contract_v2_compatibility,validated.contract_v2_source_attribution);
      if(validated.contract_v2_compatibility?.state==='BLOCKED')
        throw Error('Contract v2 source/base-spec fingerprint conflict: '+validated.contract_v2_compatibility.reasons.join('; ')+'. Reconcile metadata in Advanced JSON; never silently repin.');
      const toSave=M.clone(validated.canonical_specification);
      if(toSave.feature_id!==input.feature_id||toSave.case_id!==input.case_id)
        throw Error('Canonical validation returned an unexpected draft identity');
      const saved=await call('/feature-testing/builder/drafts','POST',
        {specification:toSave,expected_revision:rev},true);
      // Do not attach a previously saved revision to a different document
      // just because the async response arrived after an editor change.
      let latest=null;
      try {latest=current();} catch(e) { /* Invalid Advanced draft remains untouched. */ }
      const disposition=M.saveResponseDisposition(toSave,latest,saved,
        generation!==editorGeneration);
      if(!disposition.apply_revision) {
        if(uiRequest===validationUiRequest)
          show('Saved '+saved.feature_id+'/'+saved.case_id+' revision '+saved.revision+
            ', but '+disposition.reason+'; reopen saved draft before the next save.');
        return;
      }
      $('sd-revision').value=saved.revision;
      baseline=M.clone(toSave);updateRevision();
      if(uiRequest===validationUiRequest)
        show('Saved DESIGN_ONLY '+saved.feature_id+'/'+saved.case_id+' revision '+saved.revision+
          (disposition.unsaved_edits?
            '. Newer editor changes remain UNSAVED; review before the next revision.':
            '. NOT reviewed or executable.'));
    }catch(e){
      const isCurrent=submitted!==null &&
        validationRequestCurrent(generation,submitted,submittedRevision);
      if(uiRequest!==validationUiRequest || (submitted!==null && !isCurrent))
        return; // do not erase newer Validate results or another draft's status
      if(Feedback && isCurrent && Array.isArray(e.validationErrors))
        Feedback.show(e.validationErrors);
      show('Draft NOT saved / revision may require refresh: '+e.message);
    }
    finally {savePending=false;$('sd-save').disabled=false;draftGuard.refresh();}
  });
  $('sd-load-drafts').addEventListener('click',async()=>{
    try {
      drafts=(await call('/feature-testing/builder/drafts','GET',undefined,true)).drafts;
      const select=$('sd-drafts');select.replaceChildren();
      for(let i=0;i<drafts.length;i++){
        const d=drafts[i], opt=el('option','',d.feature_id+'/'+d.case_id+' · revision '+d.revision);
        opt.value=String(i);select.append(opt);
      }
      show('Read '+drafts.length+' operator-protected drafts; no changes made.');
    }catch(e){show('Draft list refused: '+e.message);}
  });
  $('sd-open-draft').addEventListener('click',()=>{
    const d=drafts[Number($('sd-drafts').value)];
    if(!d){show('Select an existing draft');return;}
    try{
      const loaded=M.parseAdvanced(JSON.stringify(d.specification));
      if(!confirmDocumentReplacement('Open saved draft'))return;
      editorGeneration++;resetReadinessViewer();clearValidationSummary();
      activeHandoff=null;spec=loaded;mode='guided';
      $('sd-revision').value=d.revision;baseline=M.clone(spec);draftGuard.start('saved',spec);
      setSourceDetail(null,null);
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
      syncAdvancedAfterReplacement();render();show('Opened '+d.case_id+' revision '+d.revision+' (design only). Edit and save with this expected revision; an external update will cause a revision conflict.');
    }catch(e){show('Open draft refused: '+e.message);}
  });
  function paintCandidates(result) {
    const host=$('sd-catalog-results');host.replaceChildren();
    const choices=Array.isArray(result.choices)?result.choices:[];
    $('sd-catalog-feedback').textContent=choices.length
      ? choices.length+' DSP source candidate(s), NOT verified. Bounded result; inspect duplicate IDs and source.'
      : 'No matching entries in this bounded query. The configured source may still contain other values.';
    for(const choice of choices) {
      const card=el('article','sd-selection'), identity=choice.kind==='gm'?choice.name:choice.id+' — '+choice.name;
      card.append(el('strong','',identity),el('small','','Source: '+choice.source_path),
        el('small','','Identity: '+choice.identity_status+
          (choice.duplicate_id_in_results?' · AMBIGUOUS: duplicate ID':'')),
        el('small','','Confidence: unreconciled DSP source only · source commit UNKNOWN'),
        el('small','','Capability: non-executable; operator review required'));
      if(choice.kind==='gm')card.append(el('small','','Metadata classification: '+choice.catalog_classification+
        ' · declared permission '+choice.permission_declared+' (not authorization)'));
      const select=el('button','','Attach unverified candidate to chosen step');
      select.type='button';
      select.addEventListener('click',()=>{
        try{
          readGuidedFields();
          spec=M.attachCandidate(spec,$('sd-catalog-step').value,choice);
          render();
          $('sd-catalog-feedback').textContent='Added '+identity+' as UNVERIFIED source context on the chosen step. Review matching and oracle still required.';
        }catch(e){$('sd-catalog-feedback').textContent='Could not attach: '+e.message;}
      });
      card.append(select);host.append(card);
    }
  }
  $('sd-search-catalog').addEventListener('click',async()=>{
    const kind=$('sd-catalog-kind').value, q=$('sd-catalog-query').value.trim();
    const host=$('sd-catalog-results');host.replaceChildren();
    if(!q || q.length>64){$('sd-catalog-feedback').textContent='Enter a name or ID (1–64 characters).';return;}
    $('sd-catalog-feedback').textContent='Searching local DSP metadata (read-only)…';
    try{
      const response=await call('/scenario-developer/catalog/search?kind='+encodeURIComponent(kind)+
        '&query='+encodeURIComponent(q)+'&limit=12');
      if(response.binding_verified!==false||response.execution_enabled!==false)
        throw Error('Catalog contract is not explicitly unverified and non-executable');
      paintCandidates(response);
    }catch(e){$('sd-catalog-feedback').textContent='Catalog unavailable: '+e.message+
      ' Check configured DSP source. Do not substitute a guessed ID.';}
  });
  for(const id of ['sd-case','sd-title','sd-purpose','sd-rationale','sd-given','sd-when','sd-then',
                    'sd-preconditions','sd-cleanup','sd-gaps']) {
    $(id).addEventListener('input',()=>{if(mode==='guided'){readGuidedFields();updateRevision();}});
  }
  $('sd-advanced-json').addEventListener('input',updateAdvancedRevision);
  let coverageContext = null, evidenceSuggestions = null, activeHandoff = null;
  function installIncompleteDraft(draft, feedback, key) {
    if(savePending)throw Error('A draft save is in progress; handoff cannot replace the editor');
    // Inspect the actual Guided or Advanced editor before touching it. A
    // loaded revision, any edit to the initial synthetic example, or another
    // source handoff requires an explicit New action first.
    current();
    const issue=M.handoffReplacementIssue(spec,baseline,Number($('sd-revision').value),activeHandoff);
    if (issue) throw Error(issue);
    editorGeneration++;resetReadinessViewer();clearValidationSummary();
    activeHandoff=key;
    spec=draft;mode='guided';baseline=null;draftGuard.start('handoff',spec);$('sd-revision').value=0;
    $('sd-guided-panel').hidden=false;$('sd-advanced-panel').hidden=true;
    $('sd-guided').setAttribute('aria-pressed','true');
    $('sd-advanced').setAttribute('aria-pressed','false');
    $('sd-preview').hidden=true;
    syncAdvancedAfterReplacement();render();renderIncompletePreview();
    show(feedback+' This draft is intentionally INCOMPLETE and cannot be validated or saved until you supply real observations, assertions, preconditions, cleanup and a new case ID. Nothing was executed.');
  }
  async function resolveCoverageContext() {
    const ref=new URLSearchParams(window.location.search).get('context_ref');
    if(!ref)return;
    const info=$('sd-context-feedback');
    try {
      if (!M.contextRefPath(ref))
        throw Error('Reference rejected: only an exact local Coverage Matrix behavior URL is allowed');
      // The existing endpoint is the owner of the source-declared reference.
      const response=await call(ref,'GET');
      const checked=await call('/scenario-developer/handoff/coverage/inspect','POST',
        {context_ref:ref,source:response});
      if(checked.context_only!==true||checked.execution_enabled!==false)
        throw Error('Coverage reference did not remain context-only');
      if (!options.features.some(f=>f.id===checked.feature_id)) throw Error('Source feature is not an accepted editor domain');
      coverageContext=checked;
      const root=$('sd-context-detail');root.replaceChildren();
      const b=el('section','sd-card');
      staticText(b,'strong','Declared source test intent, not a verified Behavior Trace identity');
      staticText(b,'p','Feature: '+checked.feature_id+' · declared behavior/case: '+checked.behavior_ref);
      staticText(b,'p','Title from readiness catalog: '+checked.label+' · category '+checked.category);
      staticText(b,'p','Provenance: '+checked.source+' / '+checked.source_pointer+
        ' · revision '+checked.source_revision+' · expected oracle UNKNOWN');
      root.append(b);
      info.textContent='Source reference resolved and checked. Review it before creating a draft; no assertions or requirements transferred.';
      $('sd-context-use').disabled=false;
      $('sd-context-note').hidden=false;
      $('sd-context-note').textContent='Source context ready for review; no draft has been created. Select Begin authoring to continue.';
    }catch(e) {
      coverageContext=null;$('sd-context-use').disabled=true;
      $('sd-context-note').hidden=false;
      $('sd-context-note').textContent='Coverage context not applied: '+e.message;
      info.textContent='Coverage context unavailable, stale or incompatible: '+e.message+
        '. Return to the Coverage Matrix and request a fresh declared intent; nothing was created.';
    }
  }
  let coverageBeginPending=false;
  $('sd-context-use').addEventListener('click',async()=>{
    if(coverageBeginPending)return;
    coverageBeginPending=true;$('sd-context-use').disabled=true;
    try {
      if (!coverageContext)throw Error('Resolve and inspect the Coverage Matrix context first');
      const ref=new URLSearchParams(window.location.search).get('context_ref');
      if(!M.contextRefPath(ref))throw Error('Original bounded source reference missing');
      const original=coverageContext;
      // The source revision is unpinned; require a new owner-endpoint lookup
      // instead of silently applying a previously inspected description.
      const latest=await call(ref,'GET');
      const checked=await call('/scenario-developer/handoff/coverage/inspect','POST',
        {context_ref:ref,source:latest});
      if(M.coverageContextChanged(original,checked))
        throw Error('Declared coverage intent changed during review; reopen the Coverage Matrix and inspect it again');
      installIncompleteDraft(M.fromContext(checked,options.features.map(f=>f.id)),
        'Created design-only authoring context from declared source case '+checked.behavior_ref+'.',
        'coverage:'+checked.feature_id+'/'+checked.behavior_ref);
      // Coverage declares a test *intent*, not necessarily a published
      // canonical scenario. Do not invent a Scenario Detail destination.
      setSourceDetail(null,null);
      $('sd-context-note').textContent='Manually opened draft from rechecked declared intent. No assertions or expected outcomes were imported. Return through the Coverage Matrix link above.';
    }catch(e){show('Coverage context not applied: '+e.message);}
    finally {
      coverageBeginPending=false;
      $('sd-context-use').disabled=Boolean(activeHandoff);
    }
  });
  function renderEvidenceSuggestions(result) {
    const root=$('sd-evidence-suggestions');root.replaceChildren();
    const summary=el('section','sd-card');
    staticText(summary,'strong','OBSERVED ONLY · capture '+result.capture_id+
      ' · checksum matches embedded indexed projection: '+result.projection_matches_embedded_evidence);
    staticText(summary,'p','Projection SHA-256: '+result.projection_sha256);
    staticText(summary,'p','Physical source authenticated: NO; fingerprints '+result.source_fingerprints_status);
    staticText(summary,'p','Unresolved bindings: '+result.unresolved_bindings+
      '; reviewer decisions complete in downloaded file: '+result.review_complete_in_file);
    root.append(summary);
    for(const item of result.steps) {
      const article=el('article','sd-card');
      staticText(article,'h3',item.step_id+' · '+item.decision+' (proposal, not normative)');
      staticText(article,'p','Originally observed: '+item.observed_summary);
      staticText(article,'p','Original indexed refs: '+item.evidence_refs.join(', '));
      const sourceDetail=el('details');
      staticText(sourceDetail,'summary','Indexed source file hashes and parser versions (not rehashed)');
      for(const pointer of item.source_fingerprints||[])staticText(sourceDetail,'p',
        pointer.ref_id+' · SHA-256 '+pointer.sha256+' · parser version '+pointer.parser_version+
        ' · '+pointer.verification);
      article.append(sourceDetail);
      const details=el('details');staticText(details,'summary','Candidate identities (UNVERIFIED)');
      for(const b of item.bindings) {
        const edited=b.suggested_identity && b.suggested_identity!==b.identity ?
          ' · reviewer-proposed '+b.suggested_identity+' (NOT source identity)' : '';
        const label=b.kind+' originally observed '+b.identity+edited+' · '+b.classification+
          ' · '+b.confidence+' · reviewer '+b.review_decision;
        const picker=el('select');picker.className='sd-binding-decision';
        picker.dataset.bindingId=b.binding_id;
        const empty=el('option','','Review candidate (required if step selected)');
        empty.value='';picker.append(empty);
        if (['ACCEPT','EDIT'].includes(b.review_decision) && b.classification!=='UNSUPPORTED') {
          const include=el('option','','Include as UNVERIFIED source note (not an approved binding)');
          include.value='INCLUDE_UNVERIFIED';picker.append(include);
        }
        const exclude=el('option','','Exclude this candidate from authored provenance');
        exclude.value='EXCLUDE';picker.append(exclude);
        details.append(field(label,picker));
      }
      article.append(details);
      const editable=el('textarea');editable.rows=2;editable.maxLength=500;
      editable.value=item.suggested_title;
      article.append(field('Edit proposed observation/action description before accepting',editable));
      staticText(article,'p','Originally OBSERVED: '+item.observed_summary);
      staticText(article,'p','Normative EXPECTED: UNKNOWN — independently sourced oracle required');
      const confirm=el('input');confirm.type='checkbox';
      confirm.className='sd-evidence-confirm';confirm.dataset.stepId=item.step_id;
      confirm.disabled=item.decision==='PENDING'||item.decision==='REJECT';
      const label=el('label','sd-field');
      label.append(confirm,document.createTextNode('I have reviewed this suggested step against the indexed evidence and choose to copy it as provisional text'));
      article.append(label);
      if(confirm.disabled)staticText(article,'p','Cannot select a rejected/pending source-review step.');
      root.append(article);
    }
    const notice=el('p','sd-warning');
    notice.textContent='No independent source lookup was made. Accepting a step only copies text and a projection fingerprint into an incomplete canonical design-only draft. You must manually author every oracle and assertion.';
    root.append(notice);
  }
  // Inspections are read-only, but a slow JSON read/POST must never publish
  // a stale file after the operator selects a different evidence export.
  let evidenceInspectionGeneration=0, evidenceInspectPending=false;
  $('sd-evidence-file').addEventListener('change',()=>{
    evidenceInspectionGeneration++;
    evidenceSuggestions=null;$('sd-evidence-use').disabled=true;
    $('sd-evidence-suggestions').replaceChildren();
    $('sd-evidence-feedback').textContent='New evidence file selected. Inspect this exact file before accepting any suggestions.';
  });
  $('sd-evidence-inspect').addEventListener('click',async()=>{
    if(evidenceInspectPending)return;
    const info=$('sd-evidence-feedback'), generation=++evidenceInspectionGeneration;
    const file=$('sd-evidence-file').files[0];
    evidenceInspectPending=true;$('sd-evidence-inspect').disabled=true;
    evidenceSuggestions=null;$('sd-evidence-use').disabled=true;
    $('sd-evidence-suggestions').replaceChildren();
    try {
      if(!file||file.size<1||file.size>4_500_000)throw Error('Choose a nonempty offline review JSON export under 4.5 MB');
      const raw=JSON.parse(await file.text());
      if(generation!==evidenceInspectionGeneration || $('sd-evidence-file').files[0]!==file)
        throw Error('Selected evidence file changed during inspection; inspect the new file');
      const result=await call('/scenario-developer/handoff/evidence/inspect','POST',{review:raw});
      if(generation!==evidenceInspectionGeneration || $('sd-evidence-file').files[0]!==file)
        throw Error('Selected evidence file changed during inspection; inspect the new file');
      if(result.contract!=='editor_evidence_suggestions_v1'||result.execution_enabled!==false||
        result.original_capture_authenticated!==false)throw Error('Unsupported review confirmation contract');
      evidenceSuggestions=result;
      renderEvidenceSuggestions(result);
      $('sd-evidence-use').disabled=false;
      info.textContent='Inspected untrusted review; '+result.steps.length+' candidate steps. Confirm each wanted proposal below. No draft created or saved.';
    }catch(e){
      if(generation===evidenceInspectionGeneration)
        info.textContent='Evidence file rejected or unavailable: '+e.message+'. Preserve the original and re-export from the trusted offline reviewer.';
    }finally{
      evidenceInspectPending=false;$('sd-evidence-inspect').disabled=false;
    }
  });
  $('sd-evidence-use').addEventListener('click',()=>{
    try {
      if(!evidenceSuggestions)throw Error('Inspect a compatible review file first');
      const selected=[];
      for(const node of $('sd-evidence-suggestions').querySelectorAll('article.sd-card')){
        const check=node.querySelector('input.sd-evidence-confirm');
        if(check&&check.checked) {
          const title=node.querySelector('textarea').value;
          const bindings=[...node.querySelectorAll('select.sd-binding-decision')].map(select=>({
            id:select.dataset.bindingId,choice:select.value,confirmed:Boolean(select.value)
          }));
          selected.push({id:check.dataset.stepId,title,confirmed:true,bindings});
        }
      }
      installIncompleteDraft(M.draftFromEvidence(evidenceSuggestions,selected),
        'Copied '+selected.length+' explicitly confirmed OBSERVED-only proposals from capture '+evidenceSuggestions.capture_id+'.',
        'evidence:'+evidenceSuggestions.capture_id+'/'+evidenceSuggestions.projection_sha256);
      setSourceDetail(null,null);
    }catch(e){show('Evidence suggestions not applied: '+e.message);}
  });
  // This advisory remains separate from canonical evidence import and draft state.
  // A field-error summary belongs to the document it was produced for.
  function clearValidationSummary() {if(Feedback)Feedback.clear();}
  function resetReadinessViewer() {
    if(readinessViewer)readinessViewer.dispose();
    readinessViewer=window.ScenarioReadinessViewer.mount($('sd-readiness-viewer'),async(review,sidecar)=>{
      return call('/scenario-developer/handoff/readiness/inspect','POST',{review,sidecar});
    });
  }
  window.addEventListener('pagehide',()=>{
    if(readinessViewer)readinessViewer.dispose();
    readinessViewer=null;
  });
  // A page restored from the back/forward cache keeps its DOM, including the two file inputs, but pagehide
  // closed the viewer. Mount a fresh one so no stale selection is shown beside a dead Inspect button.
  window.addEventListener('pageshow',event=>{
    if(event.persisted)resetReadinessViewer();
  });
  resetReadinessViewer();
  draftGuard=window.ScenarioDraftGuard.create({
    win:window,
    getCurrent:()=>{
      // Never parse Advanced JSON into the canonical draft just to check dirty.
      if(mode==='advanced')return M.parseAdvanced($('sd-advanced-json').value);
      if(editorReady)readGuidedFields();
      return spec;
    },
    getBaseline:()=>baseline,
    getRevision:()=>Number($('sd-revision').value)||0,
    isSavePending:()=>savePending,
    onStatus:state=>{
      $('sd-revision-state').textContent=state.detail;
      $('sd-work-state').textContent=state.banner;
      $('sd-work-state').dataset.state=state.state;
    }
  });
  draftGuard.start('new',spec);
  // Add a saved draft to the Test catalog (#1410): the server reads the stored draft, so only what was saved is added.
  let catalogAddPending=false;
  $('sd-add-to-catalog').addEventListener('click',async()=>{
    if(catalogAddPending)return;
    const out=$('sd-catalog-result');
    const d=drafts[Number($('sd-drafts').value)];
    if(!d){out.textContent='List the local drafts and select one first; only a saved draft can be added.';return;}
    const tags=$('sd-catalog-tags').value.split(',').map(t=>t.trim()).filter(Boolean);
    catalogAddPending=true;$('sd-add-to-catalog').disabled=true;
    try{
      const added=await call('/feature-testing/test-catalog/from-draft','POST',
        {feature_id:d.feature_id,case_id:d.case_id,draft_revision:d.revision,tags},true);
      out.replaceChildren(document.createTextNode('Added '+added.feature_id+'/'+added.case_id+' as catalog revision r'+added.revision+
        ' (DRAFT, from saved draft revision '+d.revision+'). It is not reviewed or runnable. '));
      const link=el('a','','Open the catalog entry');
      link.href='/feature-testing/catalog-entry/'+encodeURIComponent(added.feature_id)+'/'+encodeURIComponent(added.case_id);
      out.append(link);
    }catch(e){out.textContent='Not added to the catalog: '+e.message;}
    finally{catalogAddPending=false;$('sd-add-to-catalog').disabled=false;}
  });
  if(document.addEventListener)document.addEventListener('sd-typed-change',()=>{if(mode==='guided'){readGuidedFields();updateRevision();}});
  (async()=> {
    try{
      options=await call('/scenario-developer/options');
      $('sd-catalog').textContent='Catalog identity: '+options.catalog_status+' — '+options.catalog_note;
      render();editorReady=true;draftGuard.refresh();
      await resolveCoverageContext();
    }catch(e){render();editorReady=true;draftGuard.refresh();show('Canonical catalog options unavailable: '+e.message+'; saving requires server validation.');}
  })();
})();
