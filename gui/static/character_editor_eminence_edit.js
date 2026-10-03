(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'missions-quests') renderEminenceEditor();
  };

  function rowFor(catalog, recordId) {
    return catalog?.items?.[String(recordId)] || {id:Number(recordId), label:`Record ${recordId}`};
  }

  async function previewAndApply(operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability:'eminence', operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This Eminence edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability:'eminence', operation,
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

  function renderEminenceEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.eminence;
    if (!box || !entry?.decoded) return;

    box.querySelectorAll(':scope > .ce-eminence-editor').forEach(panel => panel.remove());
    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const offline = editableOnline() && entry.editable === true;
    const catalogRows = Object.values(catalog.items || {})
      .map(row => ({...row, id:Number(row.id)}))
      .filter(row => Number.isInteger(row.id) && row.id >= 0 && row.id <= 4095)
      .sort((a,b) => a.id - b.id);

    const recordOptions = ['<option value="0">Empty / record 0</option>']
      .concat(catalogRows.map(row => `<option value="${row.id}">${esc(row.label)} · ${row.id}</option>`))
      .join('');
    const slotOptions = Array.from({length:31}, (_,slot) => `<option value="${slot}">Slot ${slot+1}${slot===30?' · time-limited':''}</option>`).join('');

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-eminence-editor';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Records of Eminence Editor</strong>${pill(decoded.family?.toUpperCase() || '')}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
      <div class="ce-progress-card"><h4>Active Slot</h4><div class="ce-muted">Record ID and progress are written together. Clearing a slot sets both to zero.</div><div class="ce-toolbar" style="margin-top:7px"><select class="ce-roe-slot" ${offline?'':'disabled'}>${slotOptions}</select><select class="ce-roe-record-select" ${offline?'':'disabled'}>${recordOptions}</select><input class="ce-roe-record-id" type="number" min="0" max="65535" placeholder="record ID" style="width:105px;min-width:0" ${offline?'':'disabled'}><input class="ce-roe-progress" type="number" min="0" max="4294967295" placeholder="progress" style="width:125px;min-width:0" ${offline?'':'disabled'}><button class="ce-roe-slot-set" ${offline?'':'disabled'}>Set slot</button><button class="ce-roe-slot-clear" ${offline?'':'disabled'}>Clear slot</button></div></div>
      <div class="ce-progress-card"><h4>Completion Flag</h4><div class="ce-muted">Set or clear exactly one completion record (ID 0-4095).</div><div class="ce-toolbar" style="margin-top:7px"><input class="ce-roe-complete-id" type="number" min="0" max="4095" placeholder="0-4095" style="width:95px;min-width:0" ${offline?'':'disabled'}><button class="ce-roe-complete-set" ${offline?'':'disabled'}>Mark complete</button><button class="ce-roe-complete-clear" ${offline?'':'disabled'}>Clear complete</button></div></div>`;
    box.prepend(shell);

    const slotSelect = shell.querySelector('.ce-roe-slot');
    const recordSelect = shell.querySelector('.ce-roe-record-select');
    const recordId = shell.querySelector('.ce-roe-record-id');
    const progress = shell.querySelector('.ce-roe-progress');
    const syncSlot = () => {
      const slot = Number(slotSelect.value);
      const row = (decoded.active || [])[slot] || {record_id:0, progress:0};
      recordId.value = Number(row.record_id || 0);
      progress.value = Number(row.progress || 0);
      recordSelect.value = catalog.items?.[String(row.record_id)] ? String(row.record_id) : '0';
    };
    slotSelect.addEventListener('change', syncSlot);
    recordSelect.addEventListener('change', () => { recordId.value = Number(recordSelect.value); });
    syncSlot();

    shell.querySelector('.ce-roe-slot-set').addEventListener('click', async () => {
      const slot = Number(slotSelect.value);
      const id = Number(recordId.value);
      const value = Number(progress.value);
      if (!Number.isInteger(slot) || slot < 0 || slot > 30) {
        alert('Eminence active slot must be between 0 and 30.');
        return;
      }
      if (!Number.isInteger(id) || id < 0 || id > 65535) {
        alert('Eminence record ID must be between 0 and 65535.');
        return;
      }
      if (!Number.isInteger(value) || value < 0 || value > 4294967295) {
        alert('Eminence progress must be between 0 and 4294967295.');
        return;
      }
      if (id === 0 && value !== 0) {
        alert('An empty Eminence slot must also have progress 0.');
        return;
      }
      const row = rowFor(catalog, id);
      await previewAndApply({kind:'active_slot', slot, record_id:id, progress:value}, `Set Eminence slot ${slot+1} to ${row.label} (${id}), progress ${value}`);
    });
    shell.querySelector('.ce-roe-slot-clear').addEventListener('click', async () => {
      const slot = Number(slotSelect.value);
      await previewAndApply({kind:'active_slot', slot, record_id:0, progress:0}, `Clear Eminence slot ${slot+1}`);
    });

    const completedId = shell.querySelector('.ce-roe-complete-id');
    const changeCompletion = async desired => {
      const id = Number(completedId.value);
      if (!Number.isInteger(id) || id < 0 || id > 4095) {
        alert('Eminence completion record ID must be between 0 and 4095.');
        return;
      }
      const row = rowFor(catalog, id);
      await previewAndApply({kind:'completion', record_id:id, completed:desired}, `${desired ? 'Mark' : 'Clear'} ${row.label} (${id}) ${desired ? 'complete' : 'completion'}`);
    };
    shell.querySelector('.ce-roe-complete-set').addEventListener('click', () => changeCompletion(true));
    shell.querySelector('.ce-roe-complete-clear').addEventListener('click', () => changeCompletion(false));
  }
})();
