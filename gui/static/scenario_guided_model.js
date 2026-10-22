/* Canonical v1 + optional #1263 BDD model. No runtime commands, storage or network. */
(function(root, factory) {
  const model = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = model;
  else root.ScenarioGuidedModel = model;
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';
  const clone = obj => JSON.parse(JSON.stringify(obj));

  function fresh() {
    return {
      schema_version: 1, feature_id: 'inventory_observation', case_id: 'SYNTH-EDITOR-01',
      name: 'Synthetic inventory observation draft', runner: 'unassigned',
      execution_status: 'design_only',
      preconditions: ['Synthetic observation context only'],
      observations: ['client_bag'],
      assertions: [{id: 'bag_observed', operation: 'nonempty', observed: 'client_bag', expected: null}],
      cleanup: ['No mutation; no execution'],
      purpose: 'UNKNOWN — enter a source-backed purpose',
      rationale: 'Synthetic draft example; no gameplay fact established',
      behavior: {
        given: ['Synthetic fixture; source identities unresolved'],
        when: ['Human operator reviews observation requirements (no execution)'],
        then: ['UNKNOWN — independent oracle and readback required']
      },
      steps: [{
        id: 'SYNTH-EDITOR-01-S01', title: 'Inspect desired observation',
        intent: 'observation', expected: 'UNKNOWN — source oracle required',
        assertion_ids: ['bag_observed'], evidence_refs: ['client_bag'],
        confidence_note: 'Synthetic only; not independently verified'
      }],
      authoring: {
        state: 'draft', execution_policy: 'read_only',
        evidence_provenance: 'synthetic_not_a_run',
        blocking_gaps: ['Expected oracle and observation source not independently verified'],
        review_required: true
      }
    };
  }

  function forkPublished(original) {
    const spec = clone(original);
    spec.case_id = 'SYNTH-' + spec.case_id + '-DRAFT';
    spec.runner = 'unassigned';
    spec.execution_status = 'design_only';
    const authoring = spec.authoring || {};
    spec.authoring = {
      state: 'draft', execution_policy: 'read_only',
      evidence_provenance: 'not_observed_design_only',
      blocking_gaps: [...(Array.isArray(authoring.blocking_gaps) ? authoring.blocking_gaps : []),
        'Forked source-backed specifications require new human review'],
      review_required: true
    };
    // A fork preserves every canonical assertion ID and step ID unless edited.
    return spec;
  }

  function addStep(spec) {
    const next = clone(spec);
    const existing = new Set((next.steps || []).map(s => s.id));
    let n = 1, id;
    do { id = next.case_id + '-S' + String(n++).padStart(2, '0'); } while (existing.has(id));
    if (!Array.isArray(next.steps)) next.steps = [];
    next.steps.push({
      id, title: 'New observation step', intent: 'observation',
      expected: 'UNKNOWN — source oracle required',
      assertion_ids: next.assertions.length ? [next.assertions[0].id] : [],
      evidence_refs: next.observations.length ? [next.observations[0]] : [],
      confidence_note: 'Not independently verified'
    });
    return next;
  }

  function moveStep(spec, index, offset) {
    const next = clone(spec);
    const destination = index + offset;
    if (index < 0 || destination < 0 || destination >= next.steps.length) return next;
    const [step] = next.steps.splice(index, 1);
    next.steps.splice(destination, 0, step);
    return next;
  }

  function deleteStep(spec, index) {
    const next = clone(spec);
    next.steps.splice(index, 1);
    return next;
  }

  function referenceIssues(spec) {
    const issues = [];
    const assertions = (spec.assertions || []).map(a => a.id);
    const observations = spec.observations || [];
    const steps = spec.steps || [];
    const duplicates = values => values.filter((v, i) => values.indexOf(v) !== i);
    for (const id of new Set(duplicates(assertions))) issues.push('Duplicate assertion ID: ' + id);
    for (const id of new Set(duplicates(steps.map(s => s.id)))) issues.push('Duplicate step ID: ' + id);
    for (const step of steps) {
      for (const id of step.assertion_ids || []) {
        if (!assertions.includes(id)) issues.push('Step ' + step.id + ' references unknown assertion ' + id);
      }
      for (const id of step.evidence_refs || []) {
        if (!observations.includes(id)) issues.push('Step ' + step.id + ' references unknown observation ' + id);
      }
    }
    return issues;
  }

  // This is human-readable provenance inside the existing canonical
  // confidence_note field, NOT a verified reference or independent format.
  function attachCandidate(source, stepId, choice) {
    const next = clone(source), step = next.steps.find(x => x.id === stepId);
    if (!step) throw Error('Choose a step before attaching a catalog candidate');
    if (!choice || !['item','keyitem','npc','mob','zone','gm'].includes(choice.kind) ||
        typeof choice.name !== 'string' || typeof choice.source_path !== 'string' ||
        !choice.source_path || !choice.name ||
        (choice.kind !== 'gm' && (!Number.isSafeInteger(choice.id) || choice.id < 0)))
      throw Error('Invalid catalog candidate; choose a returned source entry');
    if (choice.binding_verified !== false || choice.execution_enabled !== false ||
        choice.operator_review_required !== true ||
        choice.identity_status !== 'unreconciled_source_candidate')
      throw Error('Catalog candidate must be unverified, review-required and non-executable');
    const identity = choice.kind === 'gm' ? choice.name : String(choice.id) + ' (' + choice.name + ')';
    const duplicate = choice.duplicate_id_in_results ? '; DUPLICATE ID — ambiguous' : '';
    const note = '[UNVERIFIED catalog candidate] ' + choice.kind + ': ' + identity +
      '; DSP source: ' + choice.source_path + '; source commit UNKNOWN' + duplicate +
      '; review required before binding or execution';
    if (note.length > 800) throw Error('Catalog candidate description too long');
    const base = (step.confidence_note || '').split('\n').filter(x => !x.startsWith('[UNVERIFIED catalog candidate]'));
    const combined = [...base, note].filter(Boolean).join('\n');
    if (combined.length > 1000) throw Error('Step provenance note exceeds canonical limit');
    step.confidence_note = combined;
    const gap = 'Selected catalog candidate is unreconciled; verify DSP/client identity, source revision and oracle';
    next.authoring.blocking_gaps = [...new Set([...(next.authoring.blocking_gaps || []),gap])];
    if (next.authoring.blocking_gaps.length > 30) throw Error('Too many blocking gaps for canonical draft');
    return next;
  }

  function cloneDraft(source) {
    const next = clone(source);
    const suffix = '-COPY';
    next.case_id = source.case_id.slice(0,120-suffix.length) + suffix;
    next.runner = 'unassigned';
    next.execution_status = 'design_only';
    next.authoring = {...next.authoring, state: 'draft', execution_policy: 'read_only',
      review_required: true, evidence_provenance: 'design_only_not_observed'};
    next.authoring.blocking_gaps = [...new Set([
      ...(next.authoring.blocking_gaps || []),
      'Cloned scenario needs independent source, oracle and identity review'
    ])];
    return next;
  }

  function revisionIndicator(baseline, current, revision) {
    if (baseline === null) return 'New draft — unsaved; revision 0';
    const dirty = JSON.stringify(baseline) !== JSON.stringify(current);
    return 'Loaded revision ' + revision + (dirty ? ' · unsaved changes' : ' · no changes');
  }

  // Inspect the Advanced buffer without replacing the canonical editor state.
  // Invalid JSON is itself unsaved text, never equivalent to the saved baseline.
  function advancedRevisionIndicator(baseline, raw, revision) {
    try { return revisionIndicator(baseline, parseAdvanced(raw), revision); }
    catch (_error) { return 'Advanced JSON invalid — unsaved text; correct before saving'; }
  }

  function emptyHandoffDraft() {
    return {
      schema_version: 1, feature_id:'', case_id:'', name:'',
      runner:'unassigned', execution_status:'design_only',
      purpose:'UNKNOWN — author a source-backed purpose',
      rationale:'UNKNOWN — source context requires independent review',
      preconditions:[], observations:[], assertions:[], cleanup:[],
      behavior:{given:[],when:[],then:['UNKNOWN — no independent normative oracle']},
      steps:[],
      authoring:{state:'draft',execution_policy:'read_only',
        evidence_provenance:'unverified_manual_authoring',
        blocking_gaps:['No reviewed oracle, complete observations or independent readback supplied'],
        review_required:true}
    };
  }
  function draftFromCoverage(context) {
    if (!context || context.contract !== 'coverage_behavior_reference_v1' ||
        context.context_only !== true || context.execution_enabled !== false ||
        context.review_required !== true || context.expected_oracle !== 'UNKNOWN' ||
        context.design_only !== true || context.auto_populate_allowed !== false ||
        context.auto_save_allowed !== false || context.proposed_case_id !== null ||
        !Array.isArray(context.assertions) || context.assertions.length !== 0 ||
        !Array.isArray(context.observations) || context.observations.length !== 0 ||
        !Array.isArray(context.capability_bindings) || context.capability_bindings.length !== 0 ||
        !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(context.feature_id) ||
        !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(context.behavior_ref))
      throw Error('Unsupported or untrusted coverage context');
    const next=emptyHandoffDraft();
    next.feature_id=context.feature_id;
    next.name=('DRAFT — '+context.label).slice(0,120);
    next.rationale=('UNVERIFIED declared test intent: '+context.feature_id+'/'+context.behavior_ref+
      '; '+context.source_pointer+'; source revision UNPINNED; NOT a validated requirement').slice(0,1000);
    next.authoring.blocking_gaps.push('Coverage reference '+context.behavior_ref+
      ' is a declared case intent only; source and normative oracle UNKNOWN');
    return next;
  }
  // All destructive document switches share this same policy. A loaded
  // revision remains an explicit context even if unchanged; a source handoff
  // and any edits to the default synthetic draft must never disappear without
  // an operator discard decision. Pure, browser-independent for tests.
  function replacementConfirmationReason(current, baseline, revision, activeSource) {
    if (baseline !== null || revision !== 0)
      return 'a loaded revision and any unsaved edits';
    if (activeSource)
      return 'the current source-derived authoring context and any edits';
    if (JSON.stringify(current) !== JSON.stringify(fresh()))
      return 'unsaved draft edits';
    return null;
  }

  // A delayed response is tied to the saved snapshot and active document,
  // never to whichever identity happens to be in the editor afterward.
  function saveResponseDisposition(snapshot, latest, saved, changedDocument) {
    if (changedDocument)
      return {apply_revision:false, reason:'editor document changed during save'};
    if (!snapshot || !saved || saved.feature_id!==snapshot.feature_id ||
        saved.case_id!==snapshot.case_id)
      return {apply_revision:false, reason:'unexpected saved document identity'};
    if (!latest || latest.feature_id!==snapshot.feature_id ||
        latest.case_id!==snapshot.case_id)
      return {apply_revision:false, reason:'editor identity changed during save'};
    return {apply_revision:true,
      unsaved_edits:JSON.stringify(latest)!==JSON.stringify(snapshot)};
  }

  // Re-resolve the exact declared intent immediately before beginning
  // authoring. A source label/category or safety flag change invalidates the
  // displayed review even though its revision is still UNPINNED.
  function coverageContextChanged(before, after) {
    if (!before || !after) return true;
    const fields=['contract','feature_id','behavior_ref','label','category','source',
      'source_pointer','source_revision','reference_kind','expected_oracle',
      'context_only','design_only','review_required','auto_populate_allowed',
      'auto_save_allowed','execution_enabled','return_url'];
    return fields.some(field=>before[field] !== after[field]) ||
      JSON.stringify(before.assertions)!==JSON.stringify(after.assertions) ||
      JSON.stringify(before.observations)!==JSON.stringify(after.observations) ||
      JSON.stringify(before.capability_bindings)!==JSON.stringify(after.capability_bindings);
  }

  // Explicit handoff entry must not silently replace an edited, loaded or
  // already source-derived draft. Return a human-readable blocker, not a
  // permission to save; all authoring still uses canonical validation.
  function handoffReplacementIssue(current, baseline, revision, activeSource) {
    if (activeSource)
      return 'A source handoff is already open; continue editing it or explicitly start a new scenario.';
    if (baseline !== null || revision !== 0)
      return 'A saved draft is open; explicitly start a new scenario before importing source context.';
    if (JSON.stringify(current) !== JSON.stringify(fresh()))
      return 'There are unsaved editor changes; explicitly start a new scenario before importing source context.';
    return null;
  }

  function draftFromEvidence(review, selected) {
    if (!review || review.contract!=='editor_evidence_suggestions_v1' ||
        review.required_confirmation!==true || review.original_capture_authenticated!==false ||
        review.execution_enabled!==false ||
        !/^[a-f0-9]{64}$/.test(review.projection_sha256) ||
        !Array.isArray(selected) || !Array.isArray(review.steps))
      throw Error('Unreviewed or unsupported evidence suggestion');
    const next=emptyHandoffDraft();
    next.name='DRAFT — captured observations (unverified)';
    next.rationale=('Unverified indexed capture '+review.capture_id+
      '; projection SHA-256 '+review.projection_sha256+
      '; original capture bytes NOT independently authenticated.').slice(0,1000);
    next.authoring.evidence_provenance='unverified_indexed_capture';
    next.authoring.blocking_gaps.push('Captured behavior is OBSERVED ONLY; source fingerprints are indexed, not independently authenticated');
    const ids=new Set();
    for(const entry of selected){
      if (!entry || typeof entry.id!=='string' || ids.has(entry.id) ||
          !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(entry.id))
        throw Error('Duplicate or invalid selected evidence step');
      ids.add(entry.id);
      const original=review.steps.find(x=>x.step_id===entry.id);
      if(!original || original.decision==='REJECT' || original.decision==='PENDING' ||
          entry.confirmed!==true || typeof entry.title!=='string' || !entry.title.trim())
        throw Error('Each chosen evidence proposal requires explicit confirmation and review');
      if (!Array.isArray(entry.bindings) ||
          entry.bindings.length !== (original.bindings||[]).length)
        throw Error('Explicit review of every candidate binding is required');
      const seenBindings=new Set(), included=[];
      for (const selectedBinding of entry.bindings) {
        const candidate=(original.bindings||[]).find(b=>b.binding_id===selectedBinding.id);
        if (!candidate || seenBindings.has(selectedBinding.id) ||
            selectedBinding.confirmed !== true ||
            !['INCLUDE_UNVERIFIED','EXCLUDE'].includes(selectedBinding.choice))
          throw Error('Unknown, duplicate or unreviewed evidence binding');
        seenBindings.add(selectedBinding.id);
        if (selectedBinding.choice === 'INCLUDE_UNVERIFIED') {
          if (!['ACCEPT','EDIT'].includes(candidate.review_decision) ||
              candidate.classification === 'UNSUPPORTED')
            throw Error('Unsupported, rejected or pending source identity cannot be included');
          included.push(candidate.kind+' source='+candidate.identity+
            (candidate.suggested_identity && candidate.suggested_identity!==candidate.identity ?
              ' reviewer-proposal='+candidate.suggested_identity : '')+
            ' ['+candidate.classification+' / UNVERIFIED; source '+candidate.binding_id+']');
        }
      }
      const indexedHashes=[...new Set((original.source_fingerprints||[])
        .map(x=>x.sha256).filter(x=>/^[a-f0-9]{64}$/.test(x)))].slice(0,3);
      const note='UNVERIFIED indexed capture '+review.capture_id+' SHA-256 '+review.projection_sha256+
        '; source step '+original.step_id+'; observed refs '+original.evidence_refs.join(', ')+
        '; indexed source SHA-256 '+(indexedHashes.join(', ')||'UNKNOWN')+
        ' (NOT independently rehashed; first '+indexedHashes.length+' unique indexed hashes shown)'+
        '; selected source identities: '+
        (included.join(' | ')||'NONE (excluded/rejected)')+
        '; all candidates UNVERIFIED; no normative oracle';
      if (note.length>1000)
        throw Error('Selected evidence provenance exceeds the canonical 1000-character step note; reduce selected bindings or retain original review outside the draft. No source refs were silently truncated.');
      next.steps.push({
        id:original.step_id,title:entry.title.trim().slice(0,500),
        intent:'observation',expected:'UNKNOWN — independently sourced expected outcome required',
        assertion_ids:[], evidence_refs:[],confidence_note:note
      });
    }
    if(!next.steps.length)throw Error('Confirm at least one supported, reviewed observation');
    return next;
  }

  function parseAdvanced(text) {
    const parsed = JSON.parse(text);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object')
      throw Error('Advanced mode must contain a canonical specification object');
    if (parsed.schema_version !== 1 || parsed.runner !== 'unassigned' ||
        parsed.execution_status !== 'design_only')
      throw Error('Only canonical version 1, design-only, unassigned drafts are editable');
    return parsed;
  }

  const CONTEXT_PATH = /^\/feature-testing\/coverage\/context\/([A-Za-z0-9][A-Za-z0-9_-]{0,119})\/([A-Za-z0-9][A-Za-z0-9_-]{0,119})$/;

  // Accept only the same-origin, read-only coverage reference path; anything else is ignored.
  function contextRefPath(raw) {
    return typeof raw === 'string' && CONTEXT_PATH.test(raw) ? raw : null;
  }

  // Compatibility with merged #1288; called only after the user's explicit action.
  // Never copy the synthetic assertion, observation or fabricated case identity.
  function fromContext(ctx, featureIds) {
    if (!ctx || !Array.isArray(featureIds) || !featureIds.includes(ctx.feature_id))
      throw Error('Context reference refused: unknown editor feature');
    return draftFromCoverage(ctx);
  }

  return {clone, fresh, forkPublished, addStep, moveStep, deleteStep, attachCandidate, cloneDraft, revisionIndicator, advancedRevisionIndicator, emptyHandoffDraft, draftFromCoverage, draftFromEvidence, handoffReplacementIssue, replacementConfirmationReason, saveResponseDisposition, coverageContextChanged, referenceIssues, parseAdvanced, contextRefPath, fromContext};
});
