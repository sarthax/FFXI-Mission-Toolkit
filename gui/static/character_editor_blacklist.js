(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'advanced') await renderBlacklist();
  };

  async function previewAndApply(targetId, action, presentBefore) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/blacklist/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({target_id:Number(targetId), action})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This blacklist change is not write-ready.');
        return false;
      }
      const name = preview?.target?.charname || `Character ${targetId}`;
      const verb = action === 'add' ? 'Add' : 'Remove';
      if (!confirm(`${verb} ${name} (ID ${targetId}) ${action === 'add' ? 'to' : 'from'} the blacklist?${issues ? '\n\n' + issues : ''}`)) return false;
      await api(`/character-editor/characters/${selectedChar}/blacklist/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({target_id:Number(targetId), action, expected_present_before:Boolean(presentBefore), approved:true})
      });
      await selectCharacter(selectedChar);
      await loadCategory('advanced');
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }

  async function renderBlacklist() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-blacklist-panel').forEach(panel => panel.remove());
    if (!activeCategoryData?.tab?.supported_capabilities?.includes('blacklist')) return;

    const offline = editableOnline();
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-blacklist-panel';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Blacklist</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-blacklist-count"></span></div>
      <div class="ce-progress-card">
        <div class="ce-toolbar"><input class="ce-blacklist-add-search" type="search" placeholder="Find character by name or ID" style="flex:1"><button class="ce-blacklist-find" ${offline ? '' : 'disabled'}>Find</button></div>
        <div class="ce-blacklist-results"></div>
        <input class="ce-blacklist-filter" type="search" placeholder="Filter current blacklist" style="width:100%;margin:7px 0">
        <div class="ce-progress-list ce-blacklist-list"></div>
      </div>`;
    box.prepend(shell);

    const filter = shell.querySelector('.ce-blacklist-filter');
    const list = shell.querySelector('.ce-blacklist-list');
    const count = shell.querySelector('.ce-blacklist-count');
    const addSearch = shell.querySelector('.ce-blacklist-add-search');
    const findButton = shell.querySelector('.ce-blacklist-find');
    const results = shell.querySelector('.ce-blacklist-results');

    let rows = [];
    const draw = () => {
      const q = String(filter.value || '').trim().toLowerCase();
      const visible = rows.filter(row => `${row.charname || ''} ${row.charid_target ?? ''}`.toLowerCase().includes(q));
      count.innerHTML = pill(`${rows.length} entries`);
      list.innerHTML = visible.map(row => `<div class="ce-progress-row"><span>${esc(row.charname || `Character ${row.charid_target}`)}<small>ID ${esc(row.charid_target)}</small></span><span>${pill('blacklisted')} <button class="ce-blacklist-remove" data-id="${row.charid_target}" ${offline ? '' : 'disabled'}>Remove</button></span></div>`).join('') || '<div class="ce-progress-empty">No matching blacklist entries.</div>';
      list.querySelectorAll('.ce-blacklist-remove').forEach(button => button.addEventListener('click', () => previewAndApply(Number(button.dataset.id), 'remove', true)));
    };

    try {
      const payload = await api(`/character-editor/characters/${selectedChar}/blacklist.json`);
      rows = payload?.rows || [];
      draw();
    } catch (e) {
      list.innerHTML = `<div class="ce-progress-empty">${esc(e.message)}</div>`;
    }

    filter.addEventListener('input', draw);
    findButton.addEventListener('click', async () => {
      const q = String(addSearch.value || '').trim();
      if (!q || !offline) return;
      try {
        const payload = await api(`/character-editor/characters.json?q=${encodeURIComponent(q)}&limit=20`);
        const existing = new Set(rows.map(row => Number(row.charid_target)));
        const candidates = (payload?.rows || []).filter(row => Number(row.charid) !== Number(selectedChar));
        results.innerHTML = candidates.map(row => {
          const id = Number(row.charid);
          const present = existing.has(id);
          return `<div class="ce-progress-row"><span>${esc(row.charname || `Character ${id}`)}<small>ID ${id}</small></span><button class="ce-blacklist-add" data-id="${id}" ${present || !offline ? 'disabled' : ''}>${present ? 'Already blacklisted' : 'Add'}</button></div>`;
        }).join('') || '<div class="ce-progress-empty">No matching characters.</div>';
        results.querySelectorAll('.ce-blacklist-add:not([disabled])').forEach(button => button.addEventListener('click', () => previewAndApply(Number(button.dataset.id), 'add', false)));
      } catch (e) {
        results.innerHTML = `<div class="ce-progress-empty">${esc(e.message)}</div>`;
      }
    });
  }
})();
