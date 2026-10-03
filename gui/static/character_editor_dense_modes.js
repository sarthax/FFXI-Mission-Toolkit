(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;

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
      const visible = rows.filter(row => !row.hidden).length;
      if (!visible && currentOnly) {
        list.dataset.ceEmptyCurrent = '1';
      } else {
        delete list.dataset.ceEmptyCurrent;
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

  function optimizeKeyItems() {
    const list = document.getElementById('ceKeyItemList');
    if (!list) return;
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
      if (label) label.firstChild && (label.firstChild.textContent = ' Current only ');
      const note = document.createElement('span');
      note.className = 'ce-muted';
      note.textContent = 'Clear Current only to browse and learn new spells.';
      toolbar.appendChild(note);
    });
  }

  function collapseLegacyPackedPanels() {
    document.querySelectorAll('#categoryData > .ce-raw-storage').forEach(details => {
      details.open = false;
    });
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
