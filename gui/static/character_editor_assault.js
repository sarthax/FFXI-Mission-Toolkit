(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const originalLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await originalLoadCategory(key);
    if (key === 'missions-quests') renderAssaultState();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout Assault catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'assault.lua'} · ${src.path || ''}`;
  }

  function assaultRow(catalog, id) {
    return catalog?.missions?.[String(id)] || {id:Number(id), label:`Assault ${id}`};
  }

  function renderAssaultState() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.assaults;
    if (!box || !entry?.decoded) return;

    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const current = Number(decoded.current || 0);
    const completedIds = (decoded.completed_ids || []).map(Number);
    const shell = document.createElement('div');
    shell.className = 'ce-progression';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Assault Progress</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(decoded.layout || '')}${pill('read only')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div>
      <div class="ce-progress-card"><h4>Current Assault</h4><div class="ce-progress-list ce-assault-current"></div></div>
      <div class="ce-progress-card"><h4>Completed ${pill(String(completedIds.length),'ok')}</h4><input class="ce-assault-filter" type="search" placeholder="Filter Assault name or ID" style="width:100%;margin:7px 0"><div class="ce-progress-list ce-assault-completed"></div></div>`;
    box.prepend(shell);

    const currentList = shell.querySelector('.ce-assault-current');
    if (current > 0) {
      const row = assaultRow(catalog, current);
      currentList.innerHTML = `<div class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><span class="ce-readonly-badge">current</span></div>`;
    } else {
      currentList.innerHTML = '<div class="ce-progress-empty">No current Assault.</div>';
    }

    const filter = shell.querySelector('.ce-assault-filter');
    const completeList = shell.querySelector('.ce-assault-completed');
    const draw = () => {
      const q = String(filter.value || '').toLowerCase();
      const rows = completedIds.map(id => assaultRow(catalog, id)).filter(row => !q || `${row.label} ${row.symbol || ''} ${row.id}`.toLowerCase().includes(q));
      completeList.innerHTML = rows.map(row => `<div class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><span class="ce-readonly-badge">complete</span></div>`).join('') || '<div class="ce-progress-empty">No matching completed Assaults.</div>';
    };
    filter.addEventListener('input', draw);
    draw();
  }
})();
