(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const originalLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await originalLoadCategory(key);
    if (key === 'missions-quests') renderQuestState();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout quest catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'quests.lua'} · ${src.path || ''}`;
  }

  function questRow(catalog, areaId, questId) {
    return catalog?.areas?.[String(areaId)]?.[String(questId)] || {id:Number(questId), label:`Quest ${questId}`};
  }

  function renderQuestList(list, rows, stateLabel) {
    list.innerHTML = rows.map(row => `<div class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><span class="ce-readonly-badge">${esc(stateLabel)}</span></div>`).join('') || '<div class="ce-progress-empty">No matching quests.</div>';
  }

  function renderQuestState() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.quests;
    if (!box || !entry?.decoded) return;

    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const shell = document.createElement('div');
    shell.className = 'ce-progression';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Quest State</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(decoded.layout || '')}${pill('read only')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div><div class="ce-progress-grid ce-quest-grid"></div>`;
    box.prepend(shell);

    const grid = shell.querySelector('.ce-quest-grid');
    for (const area of decoded.areas || []) {
      const currentIds = (area.current_ids || []).map(Number);
      const completedIds = (area.completed_ids || []).map(Number);
      const card = document.createElement('div');
      card.className = 'ce-progress-card';
      card.innerHTML = `<h4>${esc(area.name)} ${pill(`${currentIds.length} active`)} ${pill(`${completedIds.length} complete`,'ok')}</h4>
        <div class="ce-muted">Area ${esc(area.area_id)} · IDs 0-255 · 32-byte current + 32-byte completed bitsets</div>
        <input class="ce-quest-filter" type="search" placeholder="Filter quest name or ID" style="width:100%;margin:7px 0">
        <details open><summary>Active / accepted (${currentIds.length})</summary><div class="ce-progress-list ce-quest-current" style="margin-top:6px"></div></details>
        <details style="margin-top:7px"><summary>Completed (${completedIds.length})</summary><div class="ce-progress-list ce-quest-complete" style="margin-top:6px"></div></details>`;
      grid.appendChild(card);

      const filter = card.querySelector('.ce-quest-filter');
      const currentList = card.querySelector('.ce-quest-current');
      const completeList = card.querySelector('.ce-quest-complete');
      const draw = () => {
        const q = String(filter.value || '').toLowerCase();
        const mapRows = ids => ids.map(id => questRow(catalog, area.area_id, id)).filter(row => !q || `${row.label} ${row.symbol || ''} ${row.id}`.toLowerCase().includes(q));
        renderQuestList(currentList, mapRows(currentIds), 'active');
        renderQuestList(completeList, mapRows(completedIds), 'complete');
      };
      filter.addEventListener('input', draw);
      draw();
    }
  }
})();
