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
    .ce-state-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:8px}.ce-state-group{border:1px solid var(--border,#444);border-radius:6px;overflow:hidden}
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
    dialog.innerHTML = `<form method="dialog" style="float:right"><button>Close</button></form><h3 id="ceStateSurfaceTitle">Mission state surface</h3><div id="ceStateSurfaceBody"><div class="ce-muted">Loading…</div></div>`;
    document.body.appendChild(dialog);
    return dialog;
  }

  function editHint(ref) {
    if (ref.state_type === 'key_item') return `<button type="button" class="ce-state-jump" data-tab="key-items">Open Key Items</button>`;
    if (ref.state_type === 'charvar') return `<button type="button" class="ce-state-jump" data-tab="variables">Open Variables</button>`;
    if (ref.state_type === 'item') return `<button type="button" class="ce-state-jump" data-tab="inventory">Open Inventory</button>`;
    if (ref.state_type === 'title') return `<button type="button" class="ce-state-jump" data-tab="unlocks-travel">Open Unlocks</button>`;
    return '';
  }

  function formatCurrent(ref) {
    if (!ref.current_resolved) return '<span class="ce-muted">current unknown</span>';
    const value = typeof ref.current_value === 'boolean' ? (ref.current_value ? 'yes' : 'no') : pretty(ref.current_value);
    return `current <strong>${esc(value)}</strong>`;
  }

  function renderSurface(payload) {
    const target = payload.target || {}, summary = payload.summary || {}, check = payload.consistency || {};
    const body = document.getElementById('ceStateSurfaceBody');
    document.getElementById('ceStateSurfaceTitle').textContent = `${target.label || target.symbol || target.kind} — State Surface`;
    const targetState = payload.character?.target_state || {};
    const targetBits = Object.entries(targetState).filter(([k]) => k !== 'resolved').map(([k,v]) => `${esc(k)} ${esc(v)}`).join(' · ');
    const groups = payload.groups || {};
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
    body.innerHTML = `<div class="ce-state-summary">${pill(`${summary.scripts_matched || 0} scripts`)}${pill(`${summary.reference_count || 0} state/API refs`)}${pill(`${check.mismatching || 0} mismatches`, check.mismatching ? 'bad' : 'ok')}${pill(check.status || 'PARTIAL', check.status === 'CONSISTENT' ? 'ok' : check.status === 'MISMATCH' ? 'bad' : 'warn')}</div>
      <div class="ce-muted">Target state: ${targetBits || 'not resolved'} · Static source evidence; runtime ordering is not inferred.</div>
      <div class="ce-state-grid" style="margin-top:8px">${groupHtml || '<div class="ce-muted">No state references were discovered in matching scripts.</div>'}</div>
      <details style="margin-top:8px"><summary>Coverage and limitations</summary><div class="ce-muted">Scanned ${esc(summary.scripts_scanned || 0)} Lua files; matched ${esc(summary.scripts_matched || 0)}.${summary.truncated ? ' Result file set truncated.' : ''}</div><ul>${limitations}</ul></details>`;
    body.querySelectorAll('.ce-state-jump').forEach(button => button.addEventListener('click', async () => {
      ensureDialog().close();
      await activateTab(button.dataset.tab);
    }));
  }

  async function openStateSurface(kind, areaId, entryId) {
    if (!selectedChar) return;
    const dialog = ensureDialog();
    dialog.showModal();
    document.getElementById('ceStateSurfaceTitle').textContent = 'Loading state surface…';
    document.getElementById('ceStateSurfaceBody').innerHTML = '<div class="ce-muted">Scanning the active server checkout for explicit mission/quest references…</div>';
    try {
      const url = `/character-editor/characters/${selectedChar}/state-surface.json?kind=${encodeURIComponent(kind)}&area_id=${Number(areaId)}&entry_id=${Number(entryId)}`;
      renderSurface(await api(url));
    } catch (e) {
      document.getElementById('ceStateSurfaceBody').innerHTML = `<div class="warn">${esc(e.message)}</div>`;
    }
  }

  function traceButton(kind, areaId, entryId, text='Trace state') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ce-state-trace';
    button.textContent = text;
    button.title = 'Discover script-owned variables, key items, events, rewards and progression transitions for this entry';
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
      if (h4) h4.append(' ', traceButton('mission', area.area_id, area.current, 'Trace current'));
      card.querySelectorAll('.ce-mission-list .ce-progress-row').forEach(row => {
        const input = row.querySelector('input[data-mid]');
        if (!input) return;
        row.appendChild(traceButton('mission', area.area_id, Number(input.dataset.mid), 'Trace'));
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
        row.appendChild(traceButton('quest', area.area_id, Number(input.dataset.qid), 'Trace'));
      });
    });
  }

  function installStateSurfaceButtons() {
    installMissionButtons();
    installQuestButtons();
  }
})();
