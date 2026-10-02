(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'spells-abilities') renderBlueSpellEditor();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout spell catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'catalog'} · ${src.path || ''}`;
  }

  function rowFor(catalog, spellId) {
    const row = catalog?.items?.[String(spellId)];
    return row || {id:spellId, label:`Blue Spell ${spellId}`};
  }

  async function previewAndApply(slot, spellId, summary) {
    if (!selectedChar) return false;
    try {
      const operation = {slot, spell_id:spellId};
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability:'blue_spells', operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This blue-spell edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability:'blue_spells', operation,
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

  function renderBlueSpellEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.blue_spells;
    if (!box || !entry?.decoded) return;

    box.querySelectorAll(':scope > .ce-blue-spell-slots').forEach(panel => panel.remove());
    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const offline = editableOnline() && entry.editable === true;
    const catalogRows = Object.values(catalog.items || {})
      .map(row => ({...row, id:Number(row.id)}))
      .filter(row => Number.isInteger(row.id) && row.id >= 0x201 && row.id <= 0x2FF)
      .sort((a,b) => a.id - b.id);

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-blue-spell-editor';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Set Blue Magic</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(`${decoded.set_count || 0} / ${decoded.slot_count || 20} slots`)}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div><div class="ce-progress-card"><div class="ce-progress-list ce-blue-edit-list"></div></div>`;
    box.prepend(shell);

    const list = shell.querySelector('.ce-blue-edit-list');
    list.innerHTML = (decoded.slots || []).map(slot => {
      const current = slot.empty ? null : rowFor(catalog, Number(slot.spell_id));
      const options = ['<option value="0">Empty</option>']
        .concat(catalogRows.map(row => `<option value="${row.id}" ${Number(slot.spell_id)===row.id?'selected':''}>${esc(row.label)} · ${row.id}</option>`))
        .join('');
      return `<div class="ce-progress-row ce-blue-edit-row" data-slot="${slot.slot}">
        <span>Slot ${slot.slot + 1}: ${slot.empty ? 'Empty' : esc(current.label)}<small>${slot.empty ? 'stored 0' : `spell ID ${esc(slot.spell_id)} · stored ${esc(slot.stored_value)}`}</small></span>
        <div class="ce-toolbar"><select class="ce-blue-select" ${offline?'':'disabled'}>${options}</select><input class="ce-blue-id" type="number" min="513" max="767" placeholder="513-767" value="${slot.empty ? '' : Number(slot.spell_id)}" style="width:92px;min-width:0" ${offline?'':'disabled'}><button class="ce-blue-set" ${offline?'':'disabled'}>Set</button><button class="ce-blue-clear" ${offline?'':'disabled'}>Clear</button></div>
      </div>`;
    }).join('');

    list.querySelectorAll('.ce-blue-edit-row').forEach(row => {
      const slot = Number(row.dataset.slot);
      const select = row.querySelector('.ce-blue-select');
      const numeric = row.querySelector('.ce-blue-id');
      select.addEventListener('change', () => { numeric.value = Number(select.value) || ''; });
      row.querySelector('.ce-blue-set').addEventListener('click', async () => {
        const spellId = Number(numeric.value);
        if (!Number.isInteger(spellId) || spellId < 0x201 || spellId > 0x2FF) {
          alert('Blue spell ID must be between 513 (0x201) and 767 (0x2FF).');
          return;
        }
        const spell = rowFor(catalog, spellId);
        await previewAndApply(slot, spellId, `Set slot ${slot + 1} to ${spell.label} (${spellId})`);
      });
      row.querySelector('.ce-blue-clear').addEventListener('click', async () => {
        await previewAndApply(slot, null, `Clear blue spell slot ${slot + 1}`);
      });
    });
  }
})();
