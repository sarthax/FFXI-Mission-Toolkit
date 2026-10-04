(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const priorLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await priorLoadCategory(key);
    if (key === 'missions-quests') installStateSurfaceButtons();
  };

  const style = document.createElement('style');
  style.textContent = `
    .ce-state-trace{font-size:.82em;padding:3px 6px}.ce-state-summary{display:flex;gap:5px;flex-wrap:wrap;margin:6px 0}
    .ce-prog-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin:10px 0}.ce-prog-card{border:1px solid var(--border,#444);border-radius:7px;padding:9px;background:rgba(255,255,255,.025)}
    .ce-prog-card h4{margin:0 0 6px}.ce-prog-value{font-size:1.12em;font-weight:700}.ce-prog-vars{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}.ce-prog-var{border:1px solid var(--border,#444);border-radius:10px;padding:2px 7px;font-size:.84em}
    .ce-prog-assessment{border:1px solid var(--border,#444);border-left:4px solid #777;border-radius:7px;padding:9px;margin:8px 0}.ce-prog-assessment.ok{border-left-color:#4a8}.ce-prog-assessment.warn{border-left-color:#b98a32}.ce-prog-assessment.bad{border-left-color:#b44}.ce-prog-assessment-head{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.ce-prog-assessment-actions{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
    .ce-prog-condition{display:flex;gap:7px;align-items:center;padding:4px 0;border-top:1px solid var(--border,#333);font-size:.9em}.ce-prog-condition:first-child{border-top:0}.ce-prog-condition.good{border-left:3px solid #4a8;padding-left:6px}.ce-prog-condition.bad{border-left:3px solid #b44;padding-left:6px}.ce-prog-condition.unknown{border-left:3px solid #b98a32;padding-left:6px}
    .ce-prog-action{border:1px solid var(--border,#444);border-radius:6px;padding:7px;margin-top:6px}.ce-prog-action.primary{border-left:4px solid #4a8}.ce-prog-action.blocked{opacity:.75}.ce-prog-action-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.ce-prog-effects{display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;font-size:.84em}.ce-prog-location{font-size:.86em;opacity:.8;margin-top:3px}
    .ce-prog-bundle{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px;margin-top:8px}.ce-prog-bundle-part{border:1px solid var(--border,#444);border-radius:6px;padding:7px}.ce-prog-bundle-part h5{margin:0 0 5px;font-size:.86em}.ce-prog-bundle-part .ce-muted{font-size:.82em}.ce-prog-outcomes{display:flex;gap:4px;flex-wrap:wrap}.ce-prog-runtime{border-left:3px solid #b98a32}.ce-prog-why{border-left:3px solid #b44}.ce-prog-projection{border-left:3px solid #4a8}.ce-prog-projection-row{padding:3px 0;border-top:1px solid var(--border,#333);font-size:.86em}.ce-prog-projection-row:first-child{border-top:0}
    .ce-prog-blockers{border:1px solid #805050;border-radius:7px;padding:9px;margin:8px 0}.ce-prog-blockers h4{margin:0 0 5px}.ce-state-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:8px}.ce-state-group{border:1px solid var(--border,#444);border-radius:6px;overflow:hidden}
    .ce-state-group>h4{margin:0;padding:6px 8px;border-bottom:1px solid var(--border,#444)}.ce-state-ref{padding:7px 8px;border-bottom:1px solid var(--border,#333)}.ce-state-ref:last-child{border-bottom:0}
    .ce-state-ref-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.ce-state-source{font-size:.8em;opacity:.7;margin-top:3px}.ce-state-mismatch{border-left:4px solid #b44}.ce-state-match{border-left:4px solid #4a8}
    #ceStateSurfaceDialog{width:min(1180px,95vw);max-height:92vh}#ceStateSurfaceBody{max-height:76vh;overflow:auto;clear:both}
  `;
  document.head.appendChild(style);

  function ensureDialog() {
    let dialog = document.getElementById('ceStateSurfaceDialog');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'ceStateSurfaceDialog';
    dialog.innerHTML = `<form method="dialog" style="float:right"><button>Close</button></form><h3 id="ceStateSurfaceTitle">Mission progression</h3><div id="ceStateSurfaceBody"><div class="ce-muted">Loading…</div></div>`;
    document.body.appendChild(dialog);
    return dialog;
  }

  function editHint(ref) {
    if (ref.state_type === 'key_item') return `<button type="button" class="ce-state-jump" data-tab="key-items">Open Key Items</button>`;
    if (ref.state_type === 'charvar' || ref.state_type === 'quest_var' || ref.state_type === 'mission_var') return `<button type="button" class="ce-state-jump" data-tab="variables">Open Variables</button>`;
    if (ref.state_type === 'item') return `<button type="button" class="ce-state-jump" data-tab="inventory">Open Inventory</button>`;
    if (ref.state_type === 'title') return `<button type="button" class="ce-state-jump" data-tab="unlocks-travel">Open Unlocks</button>`;
    return '';
  }

  function editorButton(editor) {
    const tabs = {'Variables':'variables','Key Items':'key-items','Mission Flags':'missions-quests','Inventory':'inventory','Unlocks':'unlocks-travel'};
    const tab = tabs[editor] || '';
    return tab ? `<button type="button" class="ce-state-jump" data-tab="${tab}">Open ${esc(editor)}</button>` : '';
  }

  function formatCurrent(ref) {
    if (!ref.current_resolved) return '<span class="ce-muted">current unknown</span>';
    const value = typeof ref.current_value === 'boolean' ? (ref.current_value ? 'yes' : 'no') : pretty(ref.current_value);
    return `current <strong>${esc(value)}</strong>`;
  }

  function statusText(status) {
    return ({QUEST_ACCEPTED:'Active',QUEST_COMPLETED:'Completed',QUEST_AVAILABLE:'Available',MISSION_CURRENT:'Current',MISSION_COMPLETED:'Completed',MISSION_NOT_CURRENT:'Not current'})[status] || status || 'Unknown';
  }

  function assessmentText(state) {
    return ({READY:'Ready',WAITING_RUNTIME:'Waiting on runtime input',BLOCKED_PERSISTED:'Blocked by persisted state',INCONSISTENT:'Inconsistent state',COMPLETED:'Completed',NO_MODELED_ACTION:'No modeled next action',UNAVAILABLE:'Model unavailable',UNKNOWN:'Assessment unknown'})[state] || String(state || 'Assessment unknown').replaceAll('_',' ').toLowerCase();
  }

  function assessmentHtml(assessment) {
    if (!assessment) return '';
    const tone = ['ok','warn','bad'].includes(assessment.tone) ? assessment.tone : '';
    const targets = (assessment.correction_targets || []).map(editorButton).join('');
    const counts = [];
    if (assessment.persisted_blockers) counts.push(`${assessment.persisted_blockers} persisted blocker${assessment.persisted_blockers === 1 ? '' : 's'}`);
    if (assessment.runtime_requirements) counts.push(`${assessment.runtime_requirements} runtime requirement${assessment.runtime_requirements === 1 ? '' : 's'}`);
    return `<section class="ce-prog-assessment ${tone}"><div class="ce-prog-assessment-head"><strong>${esc(assessmentText(assessment.state))}</strong>${pill(assessment.state || 'UNKNOWN', tone)}</div><div>${esc(assessment.summary || '')}</div>${counts.length ? `<div class="ce-muted">${esc(counts.join(' · '))}</div>` : ''}${targets ? `<div class="ce-prog-assessment-actions">${targets}</div>` : ''}</section>`;
  }

  function conditionHtml(row) {
    const state = row.matches === true ? 'good' : row.matches === false ? 'bad' : 'unknown';
    const mark = row.matches === true ? '✓' : row.matches === false ? '✕' : '?';
    const actual = row.resolved ? pretty(row.actual) : 'unknown';
    return `<div class="ce-prog-condition ${state}"><strong>${mark}</strong><span><strong>${esc(row.subject)}</strong> ${esc(row.operator)} ${esc(pretty(row.expected))} · current ${esc(actual)}</span><span class="sp"></span>${row.matches === false ? editorButton(row.editor) : ''}</div>`;
  }

  function effectText(effect) {
    const names = {SET_VAR:'Set',SET_STATE:'Set',SET_CHANNEL:'Set',GRANT:'Grant',REMOVE:'Remove',CONSUME:'Consume',REISSUE:'Reissue',COMPLETE:'Complete',START:'Start',GRANT_TITLE:'Grant title',COMPLETE_TRADE:'Complete trade',TELEPORT:'Teleport',START_TIMER:'Start timer',CANCEL_TIMER:'Cancel timer',ENTER:'Enter',EXIT:'Exit',CLIENT_TRANSPORT:'Transport'};
    const verb = names[effect.effect] || String(effect.effect || '').replaceAll('_',' ').toLowerCase();
    return `${verb} ${effect.subject || ''}${effect.value !== null && effect.value !== undefined ? ` → ${pretty(effect.value)}` : ''}`;
  }

  function actionHtml(action, primary=false) {
    const event = action.event || {};
    const location = event.zone ? `${event.zone}${event.actor ? ` · ${event.actor}` : ''}${event.event_id !== undefined ? ` · event ${event.event_id}` : ''}` : '';
    const effects = (action.effects || []).map(effect => `<span>${pill(effectText(effect), effect.effect === 'COMPLETE' ? 'ok' : '')}</span>`).join('');
    const blocked = action.eligibility === 'BLOCKED';
    return `<div class="ce-prog-action${primary ? ' primary' : ''}${blocked ? ' blocked' : ''}"><div class="ce-prog-action-head"><strong>${primary ? 'Next progression action' : esc(String(action.trigger || 'Action').replaceAll('_',' '))}</strong>${pill(action.eligibility || 'UNKNOWN', action.eligibility === 'MATCH' || action.eligibility === 'OPEN' ? 'ok' : blocked ? 'bad' : 'warn')}${action.implementation_status && action.implementation_status !== 'PRESENT' ? pill(action.implementation_status,'warn') : ''}</div>${location ? `<div class="ce-prog-location">${esc(location)} · ${esc(String(action.trigger || '').replaceAll('_',' '))}</div>` : ''}<div class="ce-prog-effects">${effects || '<span class="ce-muted">No persistent effect modeled; likely dialogue/reminder/runtime-only action.</span>'}</div></div>`;
  }

  function effectGroup(title, rows, cls='') {
    if (!rows || !rows.length) return '';
    return `<div class="ce-prog-bundle-part ${cls}"><h5>${esc(title)}</h5><div class="ce-prog-outcomes">${rows.map(row => `<span>${pill(effectText(row), row.effect === 'COMPLETE' ? 'ok' : '')}</span>`).join('')}</div></div>`;
  }

  function projectionText(row) {
    const subject = row.subject || String(row.effect || '').replaceAll('_',' ').toLowerCase();
    const before = row.before_known ? pretty(row.before) : 'current unknown';
    return `${subject}: ${before} → ${pretty(row.after)}`;
  }

  function projectionHtml(bundle) {
    const rows = bundle?.projected_changes || [];
    if (!rows.length) return '';
    return `<div class="ce-prog-bundle-part ce-prog-projection"><h5>Expected result if this action completes</h5>${rows.map(row => `<div class="ce-prog-projection-row">${esc(projectionText(row))}</div>`).join('')}<div class="ce-muted">Read-only projection from modeled effects; no character state is changed here.</div></div>`;
  }

  function bundleHtml(bundle) {
    if (!bundle) return '';
    const pre = (bundle.preconditions || []).map(conditionHtml).join('');
    const runtime = (bundle.runtime_requirements || []).map(row => `<div class="ce-prog-condition unknown"><strong>?</strong><span><strong>${esc(row.subject)}</strong> ${esc(row.operator)} ${esc(pretty(row.expected))} · runtime-only requirement</span></div>`).join('');
    const why = (bundle.why_blocked || []).map(row => {
      const persisted = row.kind === 'persisted_condition';
      const detail = persisted ? `expected ${pretty(row.expected)} · current ${pretty(row.actual)}` : `runtime condition ${row.operator || ''} ${pretty(row.expected)}`;
      return `<div class="ce-prog-condition ${persisted ? 'bad' : 'unknown'}"><strong>${persisted ? '✕' : '?'}</strong><span><strong>${esc(row.subject)}</strong> · ${esc(detail)}</span><span class="sp"></span>${persisted ? editorButton(row.editor) : ''}</div>`;
    }).join('');
    const event = bundle.event || {};
    const eventText = event.zone || event.actor || event.event_id !== undefined ? `${event.zone || 'Unknown zone'}${event.actor ? ` · ${event.actor}` : ''}${event.event_id !== undefined ? ` · event ${event.event_id}` : ''}` : '';
    return `<div class="ce-prog-bundle">
      ${eventText ? `<div class="ce-prog-bundle-part"><h5>Trigger / event</h5><strong>${esc(String(bundle.trigger || 'Action').replaceAll('_',' '))}</strong><div class="ce-muted">${esc(eventText)}</div></div>` : ''}
      ${pre ? `<div class="ce-prog-bundle-part"><h5>Persisted preconditions</h5>${pre}</div>` : ''}
      ${runtime ? `<div class="ce-prog-bundle-part ce-prog-runtime"><h5>Runtime requirements</h5>${runtime}</div>` : ''}
      ${effectGroup('State changes', bundle.state_changes)}
      ${effectGroup('Rewards / grants', bundle.rewards)}
      ${effectGroup('Removals / consumption', bundle.removals)}
      ${effectGroup('Completion', bundle.completion)}
      ${effectGroup('Next activation / movement', bundle.next_activation)}
      ${effectGroup('Timers', bundle.timers)}
      ${projectionHtml(bundle)}
      ${why ? `<div class="ce-prog-bundle-part ce-prog-why"><h5>Why blocked</h5>${why}</div>` : ''}
    </div>`;
  }

  function rawEvidenceHtml(payload) {
    const summary = payload.summary || {}, check = payload.consistency || {}, groups = payload.groups || {};
    const groupHtml = Object.entries(groups).map(([type, refs]) => {
      const rows = (refs || []).map(ref => {
        const compared = ref.condition_matches;
        const cls = compared === false ? ' ce-state-mismatch' : compared === true ? ' ce-state-match' : '';
        const expectation = ref.expectation_operator ? ` · expects ${esc(ref.expectation_operator)} ${esc(ref.expectation_value)}` : '';
        const sourceHref = `/behavior?source=${encodeURIComponent(ref.source_path || '')}`;
        return `<div class="ce-state-ref${cls}"><div class="ce-state-ref-head"><strong>${esc(ref.key)}</strong>${pill(ref.operation)}${pill(ref.edit_class || 'derived')}<span>${formatCurrent(ref)}${expectation}</span><span class="sp"></span>${editHint(ref)}</div><div class="ce-state-source"><a href="${sourceHref}">${esc(ref.source_path)}</a>:${esc(ref.source_line)} · ${esc(ref.hook || '')}<br><code>${esc(ref.source_text || '')}</code></div></div>`;
      }).join('');
      return `<section class="ce-state-group"><h4>${esc(type.replaceAll('_',' '))} ${pill((refs||[]).length)}</h4>${rows}</section>`;
    }).join('');
    const limitations = (payload.limitations || []).map(row => `<li>${esc(row)}</li>`).join('');
    return `<details style="margin-top:10px"><summary>Technical evidence & raw State Surface (${summary.reference_count || 0} refs)</summary><div class="ce-state-summary">${pill(`${summary.scripts_matched || 0} scripts`)}${pill(`${check.mismatching || 0} raw mismatches`, check.mismatching ? 'bad' : 'ok')}${pill(check.status || 'PARTIAL', check.status === 'CONSISTENT' ? 'ok' : check.status === 'MISMATCH' ? 'bad' : 'warn')}</div><div class="ce-state-grid">${groupHtml || '<div class="ce-muted">No state references discovered.</div>'}</div><details style="margin-top:8px"><summary>Coverage and limitations</summary><ul>${limitations}</ul></details></details>`;
  }

  function renderSurface(payload) {
    const target = payload.target || {}, progression = payload.progression || {};
    const body = document.getElementById('ceStateSurfaceBody');
    document.getElementById('ceStateSurfaceTitle').textContent = `${target.label || target.symbol || target.kind} — Progression`;

    if (!progression.available) {
      body.innerHTML = `<div class="warn">${esc(progression.reason || 'A structured progression model is not available for this source layout.')}</div>${rawEvidenceHtml(payload)}`;
      bindJumps(body);
      return;
    }

    const step = progression.current_step || {};
    const vars = (progression.feature_vars || []).map(row => `<span class="ce-prog-var"><strong>${esc(row.key)}</strong> = ${esc(pretty(row.value))}</span>`).join('');
    const conditions = (step.conditions || []).map(conditionHtml).join('');
    const primary = progression.primary_action ? actionHtml(progression.primary_action, true) : '<div class="ce-muted">No next persistent progression action was identified for this state.</div>';
    const primaryBundle = bundleHtml(progression.primary_bundle || progression.primary_action?.transition_bundle);
    const otherActions = (progression.current_actions || []).filter(row => !progression.primary_action || row.transition_id !== progression.primary_action.transition_id).slice(0,5).map(row => `${actionHtml(row)}${bundleHtml(row.transition_bundle)}`).join('');
    const blockers = (progression.blockers || []).map(conditionHtml).join('');
    const diagnosisTone = progression.diagnosis === 'CURRENT' || progression.diagnosis === 'COMPLETED' ? 'ok' : 'warn';
    const stepLabel = progression.diagnosis === 'COMPLETED' ? 'Mission/quest complete' : step.section_index ? `Section ${step.section_index}` : 'No matching section';
    const assessment = assessmentHtml(progression.assessment);

    body.innerHTML = `<div class="ce-state-summary">${pill(statusText(progression.status), progression.status?.includes('COMPLETED') ? 'ok' : '')}${pill(progression.diagnosis || 'UNKNOWN', diagnosisTone)}${pill(`${progression.summary?.transition_count || 0} modeled transitions`)}${pill(`${progression.summary?.transition_bundle_count || 0} transition bundles`)}</div>
      ${assessment}
      <div class="ce-prog-overview">
        <section class="ce-prog-card"><h4>Current state</h4><div class="ce-prog-value">${esc(statusText(progression.status))}</div><div class="ce-prog-vars">${vars || '<span class="ce-muted">No persisted feature variables modeled.</span>'}</div></section>
        <section class="ce-prog-card"><h4>Current step</h4><div class="ce-prog-value">${esc(stepLabel)}</div><div class="ce-muted">${step.source_lines ? `Source lines ${esc(step.source_lines.join('–'))}` : 'Structured from the active server mission definition.'}</div></section>
      </div>
      ${conditions ? `<section class="ce-prog-card"><h4>Why this is the current step</h4>${conditions}</section>` : ''}
      <section class="ce-prog-card" style="margin-top:8px"><h4>What happens next</h4>${primary}${primaryBundle}${otherActions ? `<details style="margin-top:7px"><summary>Other actions/reminders available in this state</summary>${otherActions}</details>` : ''}</section>
      ${blockers ? `<section class="ce-prog-blockers"><h4>Blocking / inconsistent conditions</h4><div class="ce-muted">These persisted values do not match the nearest modeled progression state. Review them before changing anything.</div>${blockers}</section>` : ''}
      <div class="ce-muted" style="margin-top:8px">Read-only diagnosis. Persisted blockers can hand off to the guarded Character Editor tab that owns the state. Runtime-only requirements are shown as requirements, not treated as corrupt stored state.</div>
      ${rawEvidenceHtml(payload)}`;
    bindJumps(body);
  }

  function bindJumps(root) {
    root.querySelectorAll('.ce-state-jump').forEach(button => button.addEventListener('click', async () => {
      ensureDialog().close();
      await activateTab(button.dataset.tab);
    }));
  }

  async function openStateSurface(kind, areaId, entryId) {
    if (!selectedChar) return;
    const dialog = ensureDialog();
    dialog.showModal();
    document.getElementById('ceStateSurfaceTitle').textContent = 'Loading progression…';
    document.getElementById('ceStateSurfaceBody').innerHTML = '<div class="ce-muted">Evaluating the character against the active server mission/quest state machine…</div>';
    try {
      const url = `/character-editor/characters/${selectedChar}/state-surface.json?kind=${encodeURIComponent(kind)}&area_id=${Number(areaId)}&entry_id=${Number(entryId)}`;
      renderSurface(await api(url));
    } catch (e) {
      document.getElementById('ceStateSurfaceBody').innerHTML = `<div class="warn">${esc(e.message)}</div>`;
    }
  }

  function traceButton(kind, areaId, entryId, text='Inspect') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ce-state-trace';
    button.textContent = text;
    button.title = 'Show current mission/quest state, progression step, next action and blocking persisted conditions';
    button.addEventListener('click', event => {
      event.preventDefault(); event.stopPropagation();
      openStateSurface(kind, areaId, entryId);
    });
    return button;
  }

  function installMissionButtons() {
    const areas = activeCategoryData?.packed?.missions?.decoded?.areas || [];
    const cards = [...document.querySelectorAll('#ceMissionAreas > .ce-progress-card')];
    cards.forEach((card, index) => {
      if (card.dataset.ceStateSurface === '1') return;
      const area = areas[index];
      if (!area) return;
      card.dataset.ceStateSurface = '1';
      const h4 = card.querySelector(':scope > h4');
      if (h4) h4.append(' ', traceButton('mission', area.area_id, area.current, 'Inspect current'));
      card.querySelectorAll('.ce-mission-list .ce-progress-row').forEach(row => {
        const input = row.querySelector('input[data-mid]');
        if (!input) return;
        row.appendChild(traceButton('mission', area.area_id, Number(input.dataset.mid), 'Inspect'));
      });
    });
  }

  function installQuestButtons() {
    const areas = activeCategoryData?.packed?.quests?.decoded?.areas || [];
    const cards = [...document.querySelectorAll('.ce-quest-grid > .ce-progress-card')];
    cards.forEach((card, index) => {
      const area = areas[index];
      if (!area) return;
      card.querySelectorAll('.ce-quest-list .ce-progress-row').forEach(row => {
        if (row.querySelector('.ce-state-trace')) return;
        const input = row.querySelector('input[data-qid]');
        if (!input) return;
        row.appendChild(traceButton('quest', area.area_id, Number(input.dataset.qid), 'Inspect'));
      });
    });
  }

  function installStateSurfaceButtons() {
    installMissionButtons();
    installQuestButtons();
  }
})();