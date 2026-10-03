(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'advanced') renderBlacklist();
  };

  function renderBlacklist() {
    const box = document.getElementById('categoryData');
    if (!box) return;
    box.querySelectorAll(':scope > .ce-blacklist-panel').forEach(panel => panel.remove());
    const rows = activeCategoryData?.tables?.char_blacklist || [];
    if (!rows.length && !activeCategoryData?.tab?.supported_capabilities?.includes('blacklist')) return;

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-blacklist-panel';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Blacklist</strong>${pill(`${rows.length} entries`)}${pill('read only')}</div>
      <div class="ce-progress-card"><input class="ce-blacklist-filter" type="search" placeholder="Filter target character ID" style="width:100%;margin:7px 0"><div class="ce-progress-list ce-blacklist-list"></div></div>`;
    box.prepend(shell);

    const filter = shell.querySelector('.ce-blacklist-filter');
    const list = shell.querySelector('.ce-blacklist-list');
    const draw = () => {
      const q = String(filter.value || '').trim().toLowerCase();
      const visible = rows.filter(row => `${row.charid_target ?? ''}`.toLowerCase().includes(q));
      list.innerHTML = visible.map(row => `<div class="ce-progress-row ce-readonly-row"><span>Character ${esc(row.charid_target)}<small>owner ${esc(row.charid_owner)}</small></span><span class="ce-readonly-badge">blocked</span></div>`).join('') || '<div class="ce-progress-empty">No matching blacklist entries.</div>';
    };
    filter.addEventListener('input', draw);
    draw();
  }
})();
