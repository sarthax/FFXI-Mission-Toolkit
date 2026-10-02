(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'missions-quests') renderAssaultEditor();
  };

  function rowFor(catalog, assaultId) {
    return catalog?.missions?.[String(assaultId)] || {id:Number(assaultId), label:`Assault ${assaultId}`};
  }

  async function previewAndApply(operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability:'assaults', operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This Assault edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability:'assaults', operation,
          expected_before_sha256:preview.before_sha256,
          approved:true
        })
      });
      await selectCharacter(selectedChar);
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }

  function renderAssaultEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.assaults;
    if (!box || !entry?.decoded) return;

    box.querySelectorAll(':scope > .ce-assault-editor').forEach(panel => panel.remove());
    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const offline = editableOnline() && entry.editable === true;
    const catalogRows = Object.values(catalog.missions || {})
      .map(row => ({...row, id:Number(row.id)}))
      .filter(row => Number.isInteger(row.id) && row.id >= 0 && row.id <= 127)
      .sort((a,b) => a.id - b.id);

    const options = ['<option value="0">No current Assault / ID 0</option>']
      .concat(catalogRows.map(row => `<option value="${row.id}" ${Number(decoded.current)===row.id?'selected':''}>${esc(row.label)} · ${row.id}</option>`))
      .join('');

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-assault-editor';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Assault Editor</strong>${pill(decoded.family?.toUpperCase() || '')}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
      <div class="ce-progress-card"><h4>Current Assault</h4><div class="ce-toolbar"><select class="ce-assault-current-select" ${offline?'':'disabled'}>${options}</select><input class="ce-assault-current-id" type="number" min="0" max="65535" value="${Number(decoded.current)||0}" style="width:110px;min-width:0" ${offline?'':'disabled'}><button class="ce-assault-current-set" ${offline?'':'disabled'}>Set current</button></div></div>
      <div class="ce-progress-card"><h4>Completion Flag</h4><div class="ce-muted">Set or clear one completion slot (ID 0-127). Checkout labels are used when present; numeric IDs remain authoritative.</div><div class="ce-toolbar" style="margin-top:7px"><input class="ce-assault-complete-id" type="number" min="0" max="127" placeholder="0-127" style="width:90px;min-width:0" ${offline?'':'disabled'}><button class="ce-assault-complete-set" ${offline?'':'disabled'}>Mark complete</button><button class="ce-assault-complete-clear" ${offline?'':'disabled'}>Clear complete</button></div></div>`;
    box.prepend(shell);

    const select = shell.querySelector('.ce-assault-current-select');
    const numeric = shell.querySelector('.ce-assault-current-id');
    select.addEventListener('change', () => { numeric.value = Number(select.value); });
    shell.querySelector('.ce-assault-current-set').addEventListener('click', async () => {
      const current = Number(numeric.value);
      if (!Number.isInteger(current) || current < 0 || current > 65535) {
        alert('Current Assault ID must be between 0 and 65535.');
        return;
      }
      const row = rowFor(catalog, current);
      await previewAndApply({current}, `Set current Assault to ${row.label} (${current})`);
    });

    const completeId = shell.querySelector('.ce-assault-complete-id');
    const changeCompletion = async desired => {
      const completedId = Number(completeId.value);
      if (!Number.isInteger(completedId) || completedId < 0 || completedId > 127) {
        alert('Assault completion ID must be between 0 and 127.');
        return;
      }
      const row = rowFor(catalog, completedId);
      await previewAndApply(
        {completed_id:completedId, completed:desired},
        `${desired ? 'Mark' : 'Clear'} ${row.label} (${completedId}) ${desired ? 'complete' : 'completion'}`
      );
    };
    shell.querySelector('.ce-assault-complete-set').addEventListener('click', () => changeCompletion(true));
    shell.querySelector('.ce-assault-complete-clear').addEventListener('click', () => changeCompletion(false));
  }
})();
