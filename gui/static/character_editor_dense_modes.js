(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;

  async function applyPacked(capability, operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability, operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) { alert(issues || 'This change is not write-ready.'); return false; }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability, operation, expected_before_sha256:preview.before_sha256, approved:true})
      });
      await selectCharacter(selectedChar);
      return true;
    } catch (e) { alert(e.message); return false; }
  }

  function installCurrentOnlyMode(card, listSelector, checkedSelector, label) {
    if (!card || card.dataset.ceCurrentModeInstalled === '1') return;
    card.dataset.ceCurrentModeInstalled = '1';
    const list = card.querySelector(listSelector);
    if (!list) return;

    let currentOnly = true;
    const toolbar = card.querySelector('.ce-toolbar');
    if (!toolbar) return;
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'ce-current-mode-toggle';
    toggle.textContent = 'Browse all';
    toggle.title = `Showing ${label} currently set on this character. Browse all to add new entries.`;
    const note = document.createElement('span');
    note.className = 'ce-muted ce-current-mode-note';
    note.textContent = `Current ${label} shown · toggle a checkbox to add/remove`;
    toolbar.append(toggle, note);

    const apply = () => {
      const rows = [...list.querySelectorAll('.ce-progress-row')];
      for (const row of rows) {
        const checked = row.querySelector(checkedSelector)?.checked === true;
        row.hidden = currentOnly && !checked;
      }
      toggle.textContent = currentOnly ? 'Browse all' : 'Current only';
      note.textContent = currentOnly
        ? `Current ${label} shown · toggle a checkbox to remove`
        : `All catalogued ${label} shown · toggle a checkbox to add/remove`;
    };

    toggle.addEventListener('click', () => {
      currentOnly = !currentOnly;
      apply();
    });

    const observer = new MutationObserver(apply);
    observer.observe(list, {childList:true, subtree:true});
    apply();
  }

  function ensureOwnedKeyItemRows(list) {
    const entry = activeCategoryData?.packed?.key_items;
    const decoded = entry?.decoded || {};
    const catalog = entry?.catalog || {};
    const owned = new Set((decoded.owned_ids || []).map(Number));
    const seen = new Set((decoded.seen_ids || []).map(Number));
    const present = new Set([...list.querySelectorAll('input[data-ki]')].map(input => Number(input.dataset.ki)));
    const offline = editableOnline() && entry?.editable === true;

    for (const id of owned) {
      if (present.has(id)) continue;
      const row = catalog.items?.[String(id)] || {id, label:`Key Item ${id}`};
      const node = document.createElement('div');
      node.className = 'ce-progress-row';
      node.innerHTML = `<span>${esc(row.label)}<small>ID ${esc(id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><label>Owned <input type="checkbox" data-ki="${id}" data-kind="owned" checked ${offline?'':'disabled'}></label><label class="ce-seen">Seen <input type="checkbox" data-ki="${id}" data-kind="seen" ${seen.has(id)?'checked':''} ${offline?'':'disabled'}></label>`;
      node.querySelectorAll('input[data-ki]').forEach(cb => cb.addEventListener('change', async () => {
        const kind = cb.dataset.kind, desired = cb.checked, operation = {key_item_id:id};
        operation[kind] = desired;
        cb.disabled = true;
        const ok = await applyPacked('key_items', operation, `${desired?'Set':'Clear'} ${kind}: ${row.label} (${id})`);
        if (!ok) { cb.checked = !desired; cb.disabled = !offline; }
      }));
      list.appendChild(node);
    }
  }

  function optimizeKeyItems() {
    const list = document.getElementById('ceKeyItemList');
    if (!list) return;
    ensureOwnedKeyItemRows(list);
    const card = list.closest('.ce-progress-card');
    installCurrentOnlyMode(card, '#ceKeyItemList', 'input[data-kind="owned"]', 'owned key items');
  }

  function optimizeBitsets() {
    document.querySelectorAll('.ce-bitset-editors .ce-progress-card').forEach(card => {
      const capability = card.dataset.capability || 'flags';
      const label = capability === 'abilities' ? 'learned abilities'
        : capability === 'weaponskills' ? 'weapon-skill unlocks'
        : capability === 'titles' ? 'titles'
        : capability === 'visited_zones' ? 'visited zones'
        : 'flags';
      installCurrentOnlyMode(card, '.ce-bitset-list', 'input[data-bit-id]', label);
    });
  }

  function optimizeSpells() {
    document.querySelectorAll('.ce-spell-manager').forEach(shell => {
      if (shell.dataset.ceDenseSpellMode === '1') return;
      shell.dataset.ceDenseSpellMode = '1';
      const learnedOnly = shell.querySelector('.ce-spell-learned-only');
      const toolbar = shell.querySelector('.ce-toolbar');
      if (!learnedOnly || !toolbar) return;
      learnedOnly.checked = true;
      learnedOnly.dispatchEvent(new Event('change', {bubbles:true}));
      const label = learnedOnly.closest('label');
      if (label?.lastChild?.nodeType === Node.TEXT_NODE) label.lastChild.textContent = ' Current only';
      const note = document.createElement('span');
      note.className = 'ce-muted';
      note.textContent = 'Clear Current only to browse and learn new spells.';
      toolbar.appendChild(note);
    });
  }

  function collapseLegacyPackedPanels() {
    document.querySelectorAll('#categoryData > .ce-raw-storage').forEach(details => { details.open = false; });
    document.querySelectorAll('#categoryData > .ce-data-block').forEach(details => {
      const text = details.querySelector(':scope > summary')?.textContent || '';
      if (/char_vars|char_effects|char_recast|char_pet/i.test(text)) details.open = false;
    });
  }

  loadCategory = async function(key) {
    await previousLoadCategory(key);
    optimizeKeyItems();
    optimizeBitsets();
    optimizeSpells();
    collapseLegacyPackedPanels();
  };
})();
