/* Guided Scenario Developer: canonical draft JSON only. Never dispatches gameplay actions. */
(function () {
  'use strict';
  const M = window.ScenarioGuidedModel;
  const $ = id => document.getElementById(id);
  let spec = M.fresh(), mode = 'guided', options = {features: [], observations: [], operations: []};
  let drafts = [], baseline = null, sourceDetail = null;
  function updateRevision() {
    const currentRevision = Number($('sd-revision').value) || 0;
    $('sd-revision-state').textContent = M.revisionIndicator(baseline,spec,currentRevision);
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
      const o = el('option', '', name + (values.includes(name) ? '' : ' — UNKNOWN reference'));
      o.value = name; o.selected = (selected || []).includes(name); select.append(o);
    }
    return select;
  }
  const selections = select => [...select.selectedOptions].map(x => x.value);

  function renderAssertions() {
    const host = $('sd-assertions'); host.replaceChildren();
    spec.assertions.forEach((row, i) => {
      const card = el('article','sd-card');
      const h = el('header'); h.append(el('strong','', 'Assertion ' + (i+1) + ' · not verified'));
      const remove = el('button', '', 'Remove assertion'); remove.type = 'button';
      remove.addEventListener('click', () => {
        spec.assertions.splice(i,1); renderAssertions(); renderSteps(); diagnostics();
      }); h.append(remove); card.append(h);
      const grid = el('div','sd-grid');
      const id = input(row.id,64); id.addEventListener('input', () => {
        row.id = id.value; renderSteps(); diagnostics();
      });
      grid.append(field('Stable assertion ID', id));
      const op = el('select');
      for (const value of new Set([...options.operations, row.operation])) {
        const o = el('option','',value);o.value=value;o.selected=value===row.operation;op.append(o);
      }
      op.addEventListener('change', () => {row.operation=op.value;diagnostics();});
      grid.append(field('Canonical operation',op));
      const observed = el('select');
      for (const value of new Set([...options.observations,row.observed])) {
        const o = el('option','',value);o.value=value;o.selected=value===row.observed;observed.append(o);
      }
      observed.addEventListener('change', () => {row.observed=observed.value;diagnostics();});
      grid.append(field('Observed field',observed));
      const expected = input(JSON.stringify(row.expected),500);
      expected.addEventListener('change', () => {
        try {row.expected=JSON.parse(expected.value);expected.setCustomValidity('');}
        catch (e) {expected.setCustomValidity('Enter JSON: string, integer, list or null');}
        diagnostics();
      });
      grid.append(field('Expected contract (JSON literal or quoted reference)',expected));
      card.append(grid);host.append(card);
    });
  }

  function renderSteps() {
    const host = $('sd-steps');host.replaceChildren();
    spec.steps.forEach((step, i) => {
      const li = el('li','sd-card');
      const header=el('header');
      header.append(el('strong','', 'Step ' + (i+1) + ' · UNKNOWN (no independent observation)'));
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
      grid.append(field('Read-only step intent',intent));
      const technical=el('details');
      staticText(technical,'summary','Technical provenance, assertion and observation bindings');
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

  function render() {
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
    for(const name of new Set([...options.observations,...spec.observations])) {
      const opt=el('option','',name+(options.observations.includes(name)?'':' — unsupported'));
      opt.value=name;opt.selected=spec.observations.includes(name);obs.append(opt);
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
  }
  function current() {
    if(mode==='advanced') spec=M.parseAdvanced($('sd-advanced-json').value);
    else readGuidedFields();
    return spec;
  }
  function diagnostics() {
    updateRevision();
    const problems=M.referenceIssues(spec);
    if(problems.length)show('Local reference warnings (validate on server):\n'+problems.join('\n'));
  }
  function switchMode(target) {
    try {current();}
    catch(err){show('Cannot switch mode: '+err.message);return;}
    mode=target;
    $('sd-guided-panel').hidden=target!=='guided';
    $('sd-advanced-panel').hidden=target!=='advanced';
    $('sd-guided').setAttribute('aria-pressed',String(target==='guided'));
    $('sd-advanced').setAttribute('aria-pressed',String(target==='advanced'));
    if(target==='advanced')$('sd-advanced-json').value=JSON.stringify(spec,null,2);
    else render();
  }
  function staticText(parent,tag,value){
    const x=el(tag,'',value);parent.append(x);return x;
  }
  function renderPreview(view, reader) {
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

  async function call(path,method,body,auth) {
    const headers={'X-Requested-With':'toolkit-ui'};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(auth)headers['X-Test-Operator-Token']=$('sd-token').value;
    const response=await fetch(path,{method:method||'GET',headers,credentials:'same-origin',
      body:body===undefined?undefined:JSON.stringify(body)});
    const value=await response.json();
    if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'HTTP '+response.status);
    return value;
  }
  async function validatePreview() {
    const result=await call('/scenario-developer/validate','POST',{specification:current()});
    renderPreview(result.preview,result.reader_view);
    show('Canonical validation accepted — DESIGN_ONLY, unreviewed, not executable.\n'+
      result.warnings.join('\n'));
    return result;
  }

  $('sd-guided').addEventListener('click',()=>switchMode('guided'));
  $('sd-advanced').addEventListener('click',()=>switchMode('advanced'));
  $('sd-apply-json').addEventListener('click',()=>switchMode('guided'));
  $('sd-new').addEventListener('click',()=>{
    spec=M.fresh();mode='guided';baseline=null;setSourceDetail(null,null);$('sd-revision').value=0;
    $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
    render();show('Created a synthetic, design-only canonical draft.');
  });
  $('sd-fork').addEventListener('click',async()=>{
    try{
      const [feature,caseId]=$('sd-seed-select').value.split('/');
      if(!feature||!caseId)throw Error('Choose a published case to fork');
      const x=await call('/scenario-developer/seed/'+encodeURIComponent(feature)+'/'+encodeURIComponent(caseId));
      spec=M.forkPublished(x.specification);mode='guided';baseline=null;setSourceDetail(feature,caseId);
      $('sd-revision').value=0;$('sd-advanced-panel').hidden=true;
      $('sd-guided-panel').hidden=false;render();
      show('Copied as DESIGN_ONLY with a new synthetic case ID. Original published case unchanged.');
    }catch(e){show('Fork refused: '+e.message);}
  });
  $('sd-clone').addEventListener('click',()=>{
    try {
      spec=M.cloneDraft(current());mode='guided';baseline=null;$('sd-revision').value=0;
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
      render();show('Cloned into a new draft case ID. Rename it if a COPY already exists; source identities still require review.');
    } catch(e){show('Clone refused: '+e.message);}
  });
  $('sd-add-assertion').addEventListener('click',()=>{
    readGuidedFields();
    let n=1,id;const ids=new Set(spec.assertions.map(a=>a.id));
    do{id='assertion_'+String(n++).padStart(2,'0');}while(ids.has(id));
    spec.assertions.push({id,operation:'nonempty',observed:spec.observations[0]||'client_bag',expected:null});
    renderAssertions();renderSteps();diagnostics();
  });
  $('sd-add-step').addEventListener('click',()=>{
    readGuidedFields();spec=M.addStep(spec);renderSteps();diagnostics();
  });
  $('sd-feature').addEventListener('change',diagnostics);
  $('sd-observations').addEventListener('change',()=>{readGuidedFields();renderSteps();diagnostics();});
  $('sd-validate').addEventListener('click',async()=>{try{await validatePreview();}
    catch(e){$('sd-preview').hidden=true;show('Canonical validation rejected: '+e.message+'\n'+M.referenceIssues(spec).join('\n'));}});
  $('sd-save').addEventListener('click',async()=>{
    try {
      if(!$('sd-token').value)throw Error('Enter a local operator token; a preview never grants save permission');
      const validated=await validatePreview();
      const rev=Number($('sd-revision').value);
      if(!Number.isInteger(rev)||rev<0)throw Error('Invalid expected revision');
      const saved=await call('/feature-testing/builder/drafts','POST',
        {specification:validated.canonical_specification,expected_revision:rev},true);
      $('sd-revision').value=saved.revision;
      baseline=M.clone(validated.canonical_specification);updateRevision();
      show('Saved DESIGN_ONLY '+saved.feature_id+'/'+saved.case_id+' revision '+saved.revision+
        '. NOT reviewed or executable.');
    }catch(e){show('Draft NOT saved: '+e.message);}
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
      spec=M.parseAdvanced(JSON.stringify(d.specification));mode='guided';
      $('sd-revision').value=d.revision;baseline=M.clone(spec);
      setSourceDetail(null,null);
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;
      render();show('Opened '+d.case_id+' revision '+d.revision+' (design only). Edit and save with this expected revision; an external update will cause a revision conflict.');
    }catch(e){show('Invalid saved draft: '+e.message);}
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
  $('sd-advanced-json').addEventListener('input',()=>{
    if(mode==='advanced')$('sd-revision-state').textContent=
      'Advanced JSON has unsaved edits — validate before saving (design only)';
  });
  // Read-only handoff from the coverage matrix: GET a bounded reference, start an
  // UNSAVED design-only draft. Never saves, forks a published ID or grants capability.
  async function loadContextRef() {
    const raw=new URLSearchParams(location.search).get('context_ref');
    if(raw===null)return;
    const note=$('sd-context-note');
    try{
      const path=M.contextRefPath(raw);
      if(!path)throw Error('only same-origin coverage context references are accepted');
      const ctx=await call(path);
      spec=M.fromContext(ctx,options.features.map(f=>f.id));
      mode='guided';baseline=null;setSourceDetail(null,null);$('sd-revision').value=0;
      $('sd-advanced-panel').hidden=true;$('sd-guided-panel').hidden=false;render();
      note.hidden=false;
      note.textContent='Started from declared source case '+ctx.behavior_ref+' ('+ctx.feature_id+
        ') — context only. Nothing was copied from it except its label; the case ID is a placeholder, '+
        'the draft is unsaved, and you must author expected outcomes yourself.';
      show('Started an unsaved design-only draft from a coverage reference.');
    }catch(e){
      note.hidden=false;
      note.textContent='Context reference ignored: '+e.message+'. A new synthetic draft is shown instead.';
    }
  }

  (async()=> {
    try{
      options=await call('/scenario-developer/options');
      $('sd-catalog').textContent='Catalog identity: '+options.catalog_status+' — '+options.catalog_note;
      render();
    }catch(e){render();show('Canonical catalog options unavailable: '+e.message+'; saving requires server validation.');}
    await loadContextRef();
  })();
})();
