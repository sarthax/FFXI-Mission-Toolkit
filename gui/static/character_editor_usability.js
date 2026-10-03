(() => {
  if (!document.querySelector('.character-editor-page')) return;

  const style = document.createElement('style');
  style.textContent = `
    .character-editor-page #characterWorkspace>.ce-toolbar:first-child{position:sticky;top:0;z-index:20;background:var(--panel,#181818);padding:6px 0;border-bottom:1px solid var(--border,#444)}
    .character-editor-page #categoryTabs{position:sticky;top:44px;z-index:19;background:var(--panel,#181818);padding:4px 0;margin:0 0 4px}
    .character-editor-page .ce-tab-count{opacity:.65;font-size:10px;margin-left:3px}
    .character-editor-page .ce-tab-sep{align-self:center;opacity:.4;padding:0 4px}
    .character-editor-page .ce-tab.ce-secondary{opacity:.75}
    .character-editor-page #ceFilterBar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0}
    .character-editor-page #ceFilterBar input[type=search]{min-width:220px}
    .character-editor-page #ceApplyBar{position:sticky;bottom:0;z-index:20;display:none;gap:10px;align-items:center;flex-wrap:wrap;padding:7px 10px;background:var(--panel,#181818);border:1px solid #8a6500;border-radius:6px;margin-top:6px}
    .character-editor-page #ceApplyBar.has-changes{display:flex}
    .character-editor-page #ceApplyBar .ce-changed-list{font-size:11px;opacity:.85;flex:1;min-width:0}
    .character-editor-page .ce-pager{display:flex;gap:6px;align-items:center;margin:4px 0;font-size:11px}
    .character-editor-page .ce-field-cell.ce-hidden,.character-editor-page .ce-dense-row-card.ce-hidden{display:none}
    .character-editor-page .ce-field-cell select.ce-edit-input{width:100%}
  `;
  document.head.appendChild(style);

  // ---- friendly labels / units ----------------------------------------------------------------
  const ACRONYMS = {hp:'HP', mp:'MP', tp:'TP', str:'STR', dex:'DEX', vit:'VIT', agi:'AGI', int:'INT', mnd:'MND', chr:'CHR', id:'ID', xp:'XP', exp:'EXP', gil:'Gil', zoneid:'Zone ID', mjob:'Main Job', sjob:'Sub Job', charid:'Char ID', accid:'Account ID', lvl:'Level', mlvl:'Main Level', slvl:'Sub Level'};
  const UNITS = {playtime:'sec', pos_x:'yalms', pos_y:'yalms', pos_z:'yalms', rotation:'0-255'};
  const friendly = key => ACRONYMS[key] || String(key).replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\b(\w)/g, c => c.toUpperCase());

  // ---- enumerated fields -> dropdowns -----------------------------------------------------------
  const JOBS = ['NON','WAR','MNK','WHM','BLM','RDM','THF','PLD','DRK','BST','BRD','RNG','SAM','NIN','DRG','SMN','BLU','COR','PUP','DNC','SCH','GEO','RUN'];
  const ENUMS = {
    nation: ["San d'Oria", 'Bastok', 'Windurst'],
    race: [null, 'Hume (M)', 'Hume (F)', 'Elvaan (M)', 'Elvaan (F)', 'Tarutaru (M)', 'Tarutaru (F)', 'Mithra', 'Galka'],
    mjob: JOBS, sjob: JOBS,
  };
  const ENUM_TABLES = new Set(['chars', 'char_stats', 'char_jobs', 'char_profile']);

  function enhanceCell(cell) {
    if (cell.dataset.ceEnhanced) return;
    cell.dataset.ceEnhanced = '1';
    const label = cell.querySelector('.ce-field-label');
    const input = cell.querySelector('.ce-edit-input');
    const raw = (label?.textContent || '').trim();
    if (label && raw) {
      const unit = UNITS[raw];
      label.title = raw + (label.title && !label.title.startsWith(raw) ? ' · ' + label.title : '');
      label.textContent = friendly(raw) + (unit ? ' (' + unit + ')' : '');
    }
    if (input && input.tagName === 'INPUT' && ENUMS[raw] && ENUM_TABLES.has(input.dataset.table)) {
      const values = ENUMS[raw], current = Number(input.value);
      if (!Number.isInteger(current) || current < 0 || current >= values.length) return;
      const select = document.createElement('select');
      select.className = input.className;
      for (const name of ['table', 'row', 'field', 'original']) select.dataset[name] = input.dataset[name];
      select.innerHTML = values.map((name, i) => name === null ? '' : `<option value="${i}" ${i === current ? 'selected' : ''}>${name} (${i})</option>`).join('');
      input.replaceWith(select);
    }
  }

  // ---- changed-fields summary + sticky apply bar ------------------------------------------------
  function ensureApplyBar() {
    let bar = document.getElementById('ceApplyBar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'ceApplyBar';
      bar.innerHTML = '<strong id="ceChangedCount"></strong><span class="ce-changed-list" id="ceChangedList"></span><button type="button" id="ceRevertAll">Revert all</button><button type="button" id="cePreviewFirst">Preview first changed row</button>';
      document.getElementById('pane-category')?.appendChild(bar);
      bar.querySelector('#ceRevertAll').addEventListener('click', () => {
        document.querySelectorAll('.ce-edit-input.ce-changed').forEach(el => { el.value = el.dataset.original ?? ''; el.classList.remove('ce-changed'); });
        refreshApplyBar();
      });
      bar.querySelector('#cePreviewFirst').addEventListener('click', () => {
        const el = document.querySelector('.ce-edit-input.ce-changed');
        el?.closest('.ce-dense-row-card, .ce-card')?.querySelector('.ce-edit-actions button')?.click();
      });
    }
    return bar;
  }
  function refreshApplyBar() {
    const bar = ensureApplyBar();
    const changed = [...document.querySelectorAll('#categoryData .ce-edit-input')].filter(el => el.value !== (el.dataset.original ?? ''));
    changed.forEach(el => el.classList.add('ce-changed'));
    bar.classList.toggle('has-changes', changed.length > 0);
    document.getElementById('ceChangedCount').textContent = changed.length + ' unsaved change' + (changed.length === 1 ? '' : 's');
    document.getElementById('ceChangedList').textContent = changed.slice(0, 8).map(el => `${el.dataset.table}.${el.dataset.field}: ${el.dataset.original ?? ''} → ${el.value}`).join(' · ') + (changed.length > 8 ? ` · +${changed.length - 8} more` : '');
  }
  document.addEventListener('input', e => { if (e.target.classList?.contains('ce-edit-input')) refreshApplyBar(); });
  document.addEventListener('change', e => { if (e.target.classList?.contains('ce-edit-input')) refreshApplyBar(); });

  // ---- search / filter / pagination -------------------------------------------------------------
  const PAGE = 25;
  function ensureFilterBar(box) {
    let bar = document.getElementById('ceFilterBar');
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = 'ceFilterBar';
    bar.innerHTML = '<input type="search" id="ceFieldSearch" placeholder="Filter fields / rows…"><label><input type="checkbox" id="ceHideZero"> hide zero/empty</label><label><input type="checkbox" id="ceChangedOnly"> changed only</label><label><input type="checkbox" id="ceShowRaw"> show raw storage</label><span class="ce-muted" id="ceFilterCount"></span>';
    box.parentNode.insertBefore(bar, box);
    bar.addEventListener('input', applyFilters);
    return bar;
  }
  function applyFilters() {
    const q = (document.getElementById('ceFieldSearch')?.value || '').trim().toLowerCase();
    const hideZero = document.getElementById('ceHideZero')?.checked;
    const changedOnly = document.getElementById('ceChangedOnly')?.checked;
    const showRaw = document.getElementById('ceShowRaw')?.checked;
    document.querySelectorAll('#categoryData details.ce-raw-storage').forEach(d => { d.style.display = showRaw ? '' : 'none'; });
    let shown = 0, total = 0;
    document.querySelectorAll('#categoryData details.ce-data-block').forEach(block => {
      const cards = [...block.querySelectorAll('.ce-dense-row-card')];
      block.querySelectorAll('.ce-pager').forEach(p => p.remove());
      cards.forEach(card => {
        card.classList.remove('ce-hidden');
        const head = (card.querySelector('.ce-dense-row-head')?.textContent || '').toLowerCase();
        const cells = [...card.querySelectorAll('.ce-field-cell')];
        let match = 0;
        cells.forEach(cell => {
          const input = cell.querySelector('.ce-edit-input');
          const text = (cell.textContent + ' ' + (cell.querySelector('.ce-field-label')?.title || '')).toLowerCase();
          const value = input ? input.value : (cell.querySelector('.ce-field-value')?.textContent || '');
          const hit = (!q || text.includes(q) || head.includes(q))
            && !(hideZero && (value === '' || /^0(\.0+)?$/.test(String(value).trim())))
            && !(changedOnly && !(input && input.classList.contains('ce-changed')));
          cell.classList.toggle('ce-hidden', !hit);
          if (hit) match++;
        });
        card.dataset.ceMatch = cells.length ? String(match) : '1';
        if (card.dataset.ceMatch === '0') card.classList.add('ce-hidden');
      });
      const matching = cards.filter(c => c.dataset.ceMatch !== '0');
      total += cards.length; shown += matching.length;
      if (matching.length > PAGE) paginate(block, matching);
    });
    const count = document.getElementById('ceFilterCount');
    if (count) count.textContent = total ? shown + '/' + total + ' rows' : '';
  }
  function paginate(block, rows) {
    let page = 0;
    const pager = document.createElement('div');
    pager.className = 'ce-pager';
    const render = () => {
      rows.forEach((r, i) => r.classList.toggle('ce-hidden', i < page * PAGE || i >= (page + 1) * PAGE));
      pager.innerHTML = `<button type="button" ${page ? '' : 'disabled'}>‹ Prev</button><span>${page * PAGE + 1}–${Math.min(rows.length, (page + 1) * PAGE)} of ${rows.length}</span><button type="button" ${(page + 1) * PAGE < rows.length ? '' : 'disabled'}>Next ›</button>`;
      pager.children[0].onclick = () => { page--; render(); };
      pager.children[2].onclick = () => { page++; render(); };
    };
    block.insertBefore(pager, block.querySelector('summary').nextSibling);
    render();
  }

  // ---- tabs: counts and primary/secondary grouping ----------------------------------------------
  const SECONDARY = new Set(['variables', 'pets-effects', 'advanced', 'unlocks-travel']);
  const originalRenderTabs = window.renderTabs;
  if (typeof originalRenderTabs === 'function') {
    window.renderTabs = function (tabs) {
      originalRenderTabs(tabs);
      const box = document.getElementById('categoryTabs');
      if (!box) return;
      const byKey = Object.fromEntries((tabs || []).map(t => [t.key, t]));
      let sepAdded = false;
      box.querySelectorAll('.ce-tab').forEach(btn => {
        const t = byKey[btn.dataset.key] || {};
        const n = t.supported_capabilities ? t.supported_capabilities.length : null;
        if (n !== undefined && n !== null) btn.insertAdjacentHTML('beforeend', `<span class="ce-tab-count">${n}</span>`);
        if (SECONDARY.has(btn.dataset.key)) {
          btn.classList.add('ce-secondary');
          if (!sepAdded) { btn.insertAdjacentHTML('beforebegin', '<span class="ce-tab-sep">|</span>'); sepAdded = true; }
        }
      });
    };
  }

  // ---- hook category loading --------------------------------------------------------------------
  const originalLoadCategory = window.loadCategory;
  window.loadCategory = async function (key) {
    await originalLoadCategory(key);
    const box = document.getElementById('categoryData');
    if (!box) return;
    ensureFilterBar(box);
    ensureApplyBar();
    box.querySelectorAll('.ce-field-cell').forEach(enhanceCell);
    box.querySelectorAll('details.ce-data-block').forEach(block => {
      const vals = [...block.querySelectorAll('.ce-field-cell .ce-edit-input, .ce-field-cell .ce-field-value')].map(el => el.value ?? el.textContent);
      if (vals.length && vals.every(v => v === '' || /^0$/.test(String(v).trim()))) block.open = false;
    });
    applyFilters();
    refreshApplyBar();
  };
})();
