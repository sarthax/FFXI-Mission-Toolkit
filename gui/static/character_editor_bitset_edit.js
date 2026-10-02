(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const EDITABLE_BITSETS = {
    abilities: {label:'Learned Abilities', singular:'Ability'},
    weaponskills: {label:'Learned Weaponskill Unlocks', singular:'Unlock'},
    titles: {label:'Obtained Titles', singular:'Title'},
    visited_zones: {label:'Visited Zones', singular:'Zone'}
  };

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'spells-abilities') renderBitsetEditors(['abilities','weaponskills']);
    if (key === 'unlocks-travel') renderBitsetEditors(['titles','visited_zones']);
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'catalog'} · ${src.path || ''}`;
  }

  function rowFor(catalog, capability, id) {
    const row = catalog?.items?.[String(id)];
    if (row) return row;
    const singular = EDITABLE_BITSETS[capability]?.singular || 'Flag';
    return {id, label:`${singular} ${id}`};
  }

  function removeReadOnlyPackedPanel(box) {
    box.querySelectorAll(':scope > .ce-progression').forEach(panel => {
      const heading = panel.querySelector('.ce-progress-head strong');
      if (heading?.textContent?.trim() === 'Decoded Packed State') panel.remove();
    });
  }

  async function previewAndApplyBit(capability, operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({capability, operation})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This packed edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          capability,
          operation,
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

  function renderBitsetEditors(capabilities) {
    const box = document.getElementById('categoryData');
    if (!box) return;
    const available = capabilities
      .map(capability => [capability, activeCategoryData?.packed?.[capability]])
      .filter(([,entry]) => entry?.decoded);
    if (!available.length) return;

    removeReadOnlyPackedPanel(box);
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-bitset-editors';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Packed Unlock State</strong><span class="ce-progress-source">Single-bit edits use guarded preview + exact before-SHA confirmation.</span></div><div class="ce-progress-grid ce-bitset-grid"></div>`;
    box.prepend(shell);
    const grid = shell.querySelector('.ce-bitset-grid');

    for (const [capability, entry] of available) {
      const decoded = entry.decoded || {};
      const catalog = entry.catalog || {};
      const setIds = new Set((decoded.set_ids || []).map(Number));
      const meaningfulBits = Number(decoded.meaningful_bits || 0);
      const catalogRows = Object.values(catalog.items || {})
        .map(row => ({...row, id:Number(row.id)}))
        .filter(row => Number.isInteger(row.id) && row.id >= 0 && row.id < meaningfulBits)
        .sort((a,b) => a.id - b.id);
      const offline = editableOnline() && entry.editable === true;
      const reserved = (decoded.reserved_set_ids || []).map(Number);
      const meta = EDITABLE_BITSETS[capability] || {label:capability, singular:'Flag'};

      const card = document.createElement('div');
      card.className = 'ce-progress-card';
      card.dataset.capability = capability;
      card.innerHTML = `<h4>${esc(meta.label)} ${pill(`${setIds.size} set`,'ok')}</h4>
        <div class="ce-muted">${esc(decoded.family?.toUpperCase() || '')} · ${esc(decoded.layout || '')} · ${esc(decoded.blob_bytes || 0)} bytes · IDs 0-${Math.max(0, meaningfulBits - 1)}</div>
        <div class="ce-progress-source" style="margin-top:3px">${esc(sourceText(catalog))}</div>
        <div style="margin-top:5px">${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
        ${reserved.length ? `<div class="warn" style="margin:7px 0">Reserved legacy bits are set but remain unwritable: ${reserved.map(esc).join(', ')}</div>` : ''}
        <div class="ce-toolbar" style="margin-top:7px"><input class="ce-bitset-filter" type="search" placeholder="Search name or ID"><label>Numeric ID <input class="ce-bitset-id" type="number" min="0" max="${Math.max(0, meaningfulBits - 1)}" style="width:90px;min-width:0"></label><button class="ce-bitset-show">Show ID</button></div>
        <div class="ce-progress-list ce-bitset-list" style="margin-top:7px"></div>`;
      grid.appendChild(card);

      const filter = card.querySelector('.ce-bitset-filter');
      const numeric = card.querySelector('.ce-bitset-id');
      const list = card.querySelector('.ce-bitset-list');
      let forcedId = null;

      const draw = () => {
        const q = String(filter.value || '').toLowerCase();
        let rows = catalogRows.filter(row => !q || `${row.label} ${row.symbol || ''} ${row.id}`.toLowerCase().includes(q));
        for (const id of setIds) {
          if (!rows.some(row => row.id === id) && (!q || `${rowFor(catalog, capability, id).label} ${id}`.toLowerCase().includes(q))) {
            rows.push(rowFor(catalog, capability, id));
          }
        }
        if (forcedId !== null && !rows.some(row => Number(row.id) === forcedId)) rows.unshift(rowFor(catalog, capability, forcedId));
        rows.sort((a,b) => Number(a.id) - Number(b.id));
        rows = rows.slice(0,300);
        list.innerHTML = rows.map(row => `<label class="ce-progress-row ce-readonly-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><span>${setIds.has(Number(row.id)) ? 'Set' : 'Clear'}</span><input type="checkbox" data-bit-id="${Number(row.id)}" ${setIds.has(Number(row.id)) ? 'checked' : ''} ${offline ? '' : 'disabled'}></label>`).join('') || '<div class="ce-progress-empty">No matching flags. Use Numeric ID for an uncatalogued value.</div>';
        list.querySelectorAll('input[data-bit-id]').forEach(cb => cb.addEventListener('change', async () => {
          const id = Number(cb.dataset.bitId);
          const desired = cb.checked;
          cb.disabled = true;
          const row = rowFor(catalog, capability, id);
          const ok = await previewAndApplyBit(capability, {bit_id:id, enabled:desired}, `${desired ? 'Set' : 'Clear'} ${meta.singular}: ${row.label} (${id})`);
          if (!ok) {
            cb.checked = !desired;
            cb.disabled = !offline;
          }
        }));
      };

      filter.addEventListener('input', () => { forcedId = null; draw(); });
      card.querySelector('.ce-bitset-show').addEventListener('click', () => {
        const id = Number(numeric.value);
        if (!Number.isInteger(id) || id < 0 || id >= meaningfulBits) {
          alert(`ID must be between 0 and ${Math.max(0, meaningfulBits - 1)} for this server layout.`);
          return;
        }
        forcedId = id;
        filter.value = '';
        draw();
      });
      draw();
    }
  }
})();
