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

  function parseAdvanced(text) {
    const parsed = JSON.parse(text);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object')
      throw Error('Advanced mode must contain a canonical specification object');
    if (parsed.schema_version !== 1 || parsed.runner !== 'unassigned' ||
        parsed.execution_status !== 'design_only')
      throw Error('Only canonical version 1, design-only, unassigned drafts are editable');
    return parsed;
  }

  return {clone, fresh, forkPublished, addStep, moveStep, deleteStep, attachCandidate, cloneDraft, revisionIndicator, referenceIssues, parseAdvanced};
});
