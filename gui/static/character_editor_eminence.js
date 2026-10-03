(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const originalLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await originalLoadCategory(key);
    if (key === 'missions-quests') renderEminenceState();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout RoE catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'roe_records.lua'} · ${src.path || ''}`;
  }

  function recordRow(catalog, id) {
    return catalog?.items?.[String(id)] || {id:Number(id), label:`Record ${id}`};
  }

  function renderEminenceState() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.eminence;
    if (!box || !entry?.decoded) return;

    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const active = (decoded.active || []).filter(row => !row.empty);
    const completedIds = (decoded.completed_ids || []).map(Number);
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-eminence-state';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Records of Eminence</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(decoded.layout || '')}${pill('read only')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div>
      <div class="ce-progress-card"><h4>Active ${pill(String(active.length),'ok')}</h4><div class="ce-progress-list ce-eminence-active"></div></div>
      <div class="ce-progress-card"><h4>Completed ${pill(String(completedIds.length),'ok')}</h4><input class="ce-eminence-filter" type="search" placeholder="Filter RoE record name or ID" style="width:100%;margin:7px 0"><div class="ce-progress-list ce-eminence-completed"></div></div>`;
    box.prepend(shell);

    const activeList = shell.querySelector('.ce-eminence-active');
    activeList.innerHTML = active.map(slot => {
      const row = recordRow(catalog, Number(slot.record_id));
      return `<div class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)} · slot ${Number(slot.slot)+1}${slot.time_limited ? ' · time-limited slot' : ''}</small></span><span class="ce-readonly-badge">progress ${esc(slot.progress)}</span></div>`;
    }).join('') || '<div class="ce-progress-empty">No active Records of Eminence.</div>';

    const filter = shell.querySelector('.ce-eminence-filter');
    const completeList = shell.querySelector('.ce-eminence-completed');
    const draw = () => {
      const q = String(filter.value || '').toLowerCase();
      const rows = completedIds.map(id => recordRow(catalog, id)).filter(row => !q || `${row.label} ${row.id}`.toLowerCase().includes(q));
      completeList.innerHTML = rows.map(row => `<div class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}</small></span><span class="ce-readonly-badge">complete</span></div>`).join('') || '<div class="ce-progress-empty">No matching completed RoE records.</div>';
    };
    filter.addEventListener('input', draw);
    draw();
  }
})();
