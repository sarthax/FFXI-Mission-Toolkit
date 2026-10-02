(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'missions-quests') renderCampaignEditor();
  };

  function rowFor(catalog, campaignId) {
    return catalog?.items?.[String(campaignId)] || {id:Number(campaignId), label:`Campaign ${campaignId}`};
  }

  async function previewAndApply(operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability:'campaign', operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This Campaign edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability:'campaign', operation,
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

  function renderCampaignEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.campaign;
    if (!box || !entry?.decoded) return;

    box.querySelectorAll(':scope > .ce-campaign-editor').forEach(panel => panel.remove());
    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const offline = editableOnline() && entry.editable === true;
    const catalogRows = Object.values(catalog.items || {})
      .map(row => ({...row, id:Number(row.id)}))
      .filter(row => Number.isInteger(row.id) && row.id >= 0 && row.id <= 511)
      .sort((a,b) => a.id - b.id);

    const options = ['<option value="0">No current Campaign / ID 0</option>']
      .concat(catalogRows.map(row => `<option value="${row.id}" ${Number(decoded.current)===row.id?'selected':''}>${esc(row.label)} · ${row.id}</option>`))
      .join('');

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-campaign-editor';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Campaign Editor</strong>${pill(decoded.family?.toUpperCase() || '')}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
      <div class="ce-progress-card"><h4>Current Campaign</h4><div class="ce-toolbar"><select class="ce-campaign-current-select" ${offline?'':'disabled'}>${options}</select><input class="ce-campaign-current-id" type="number" min="0" max="65535" value="${Number(decoded.current)||0}" style="width:110px;min-width:0" ${offline?'':'disabled'}><button class="ce-campaign-current-set" ${offline?'':'disabled'}>Set current</button></div></div>
      <div class="ce-progress-card"><h4>Completion Flag</h4><div class="ce-muted">Set or clear one completion slot (ID 0-511). Checkout labels are used when present; numeric IDs remain authoritative.</div><div class="ce-toolbar" style="margin-top:7px"><input class="ce-campaign-complete-id" type="number" min="0" max="511" placeholder="0-511" style="width:90px;min-width:0" ${offline?'':'disabled'}><button class="ce-campaign-complete-set" ${offline?'':'disabled'}>Mark complete</button><button class="ce-campaign-complete-clear" ${offline?'':'disabled'}>Clear complete</button></div></div>`;
    box.prepend(shell);

    const select = shell.querySelector('.ce-campaign-current-select');
    const numeric = shell.querySelector('.ce-campaign-current-id');
    select.addEventListener('change', () => { numeric.value = Number(select.value); });
    shell.querySelector('.ce-campaign-current-set').addEventListener('click', async () => {
      const current = Number(numeric.value);
      if (!Number.isInteger(current) || current < 0 || current > 65535) {
        alert('Current Campaign ID must be between 0 and 65535.');
        return;
      }
      const row = rowFor(catalog, current);
      await previewAndApply({current}, `Set current Campaign to ${row.label} (${current})`);
    });

    const completeId = shell.querySelector('.ce-campaign-complete-id');
    const changeCompletion = async desired => {
      const completedId = Number(completeId.value);
      if (!Number.isInteger(completedId) || completedId < 0 || completedId > 511) {
        alert('Campaign completion ID must be between 0 and 511.');
        return;
      }
      const row = rowFor(catalog, completedId);
      await previewAndApply(
        {completed_id:completedId, completed:desired},
        `${desired ? 'Mark' : 'Clear'} ${row.label} (${completedId}) ${desired ? 'complete' : 'completion'}`
      );
    };
    shell.querySelector('.ce-campaign-complete-set').addEventListener('click', () => changeCompletion(true));
    shell.querySelector('.ce-campaign-complete-clear').addEventListener('click', () => changeCompletion(false));
  }
})();
