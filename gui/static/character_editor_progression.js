(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const style = document.createElement('style');
  style.textContent = `
    .ce-progression{display:grid;gap:10px;margin-top:10px}.ce-progress-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
    .ce-progress-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}.ce-progress-card{border:1px solid var(--border,#444);border-radius:6px;padding:9px;background:var(--panel,#181818)}
    .ce-progress-card h4{margin:0 0 7px}.ce-progress-card select,.ce-progress-card input{max-width:100%}.ce-progress-list{max-height:50vh;overflow:auto;border:1px solid var(--border,#333);border-radius:5px}
    .ce-progress-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:6px 8px;border-bottom:1px solid var(--border,#333)}
    .ce-progress-row:last-child{border-bottom:0}.ce-progress-row small{display:block;opacity:.65}.ce-progress-empty{padding:10px;opacity:.7}.ce-progress-source{font-size:.8em;opacity:.65}
    @media(max-width:720px){.ce-progress-row{grid-template-columns:1fr auto}.ce-progress-row .ce-seen{grid-column:2}.ce-progress-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const originalLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await originalLoadCategory(key);
    if (key === 'missions-quests') renderMissionEditor();
    if (key === 'key-items') renderKeyItemEditor();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'catalog'} · ${src.path || ''}`;
  }

  function issueText(preview) {
    return (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
  }

  async function previewAndApply(capability, operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability, operation})
      });
      const issues = issueText(preview);
      if (!preview.ready) {
        alert(issues || 'This packed edit is not write-ready.');
        return false;
      }
      const before = pretty(preview.before), after = pretty(preview.after);
      if (!confirm(`${summary}\n\nBefore: ${before}\nAfter: ${after}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability, operation, expected_before_sha256:preview.before_sha256, approved:true
        })
      });
      await selectCharacter(selectedChar);
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }

  function missionRowsForArea(catalog, areaId) {
    const rows = catalog?.areas?.[String(areaId)] || {};
    return Object.values(rows).sort((a,b) => Number(a.id) - Number(b.id));
  }

  function missionLabel(catalog, areaId, missionId) {
    const row = catalog?.areas?.[String(areaId)]?.[String(missionId)];
    return row?.label || `Mission ${missionId}`;
  }

  function renderMissionEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.missions;
    if (!box || !entry?.decoded) return;
    const decoded = entry.decoded, catalog = entry.catalog || {};
    const offline = editableOnline();
    const shell = document.createElement('div');
    shell.className = 'ce-progression';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Mission Flags</strong>${pill(decoded.family.toUpperCase())}${pill(decoded.layout)}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div><div class="ce-progress-grid" id="ceMissionAreas"></div>`;
    box.prepend(shell);
    const areaBox = shell.querySelector('#ceMissionAreas');
    for (const area of decoded.areas || []) {
      const rows = missionRowsForArea(catalog, area.area_id);
      const currentOptions = rows.map(r => `<option value="${Number(r.id)}" ${Number(r.id)===Number(area.current)?'selected':''}>${esc(r.label)} · ${esc(r.id)}</option>`).join('');
      const completedSet = new Set((area.completed_ids || []).map(Number));
      const completionRows = rows.filter(r => Number(r.id) >= 0 && Number(r.id) < 64);
      const card = document.createElement('div');
      card.className = 'ce-progress-card';
      card.innerHTML = `<h4>${esc(area.name)} ${pill(`${area.completed_count} complete`)}</h4>
        <div class="ce-muted">Area ${area.area_id} · current ${esc(missionLabel(catalog,area.area_id,area.current))} (${esc(area.current)})</div>
        <div class="ce-toolbar" style="margin-top:6px"><select class="ce-mission-current" ${offline?'':'disabled'}>${currentOptions || `<option value="${Number(area.current)}">Mission ${esc(area.current)}</option>`}</select><input class="ce-mission-current-id" type="number" min="0" max="65535" value="${Number(area.current)}" style="width:90px;min-width:0" ${offline?'':'disabled'}><button class="ce-set-current" ${offline?'':'disabled'}>Set current</button></div>
        ${area.status_upper !== null ? `<div class="ce-toolbar" style="margin-top:6px"><label>Status upper <input class="ce-status-upper" type="number" min="0" max="65535" value="${Number(area.status_upper)}" style="width:90px;min-width:0" ${offline?'':'disabled'}></label><label>Status lower <input class="ce-status-lower" type="number" min="0" max="65535" value="${Number(area.status_lower)}" style="width:90px;min-width:0" ${offline?'':'disabled'}></label><button class="ce-set-status" ${offline?'':'disabled'}>Set status</button></div>` : ''}
        <details style="margin-top:7px"><summary>Completed mission flags (${completionRows.length || 64} catalogued)</summary><input class="ce-mission-filter" type="search" placeholder="Filter missions" style="width:100%;margin:6px 0"><div class="ce-progress-list ce-mission-list"></div></details>`;
      areaBox.appendChild(card);
      const select = card.querySelector('.ce-mission-current'), numeric = card.querySelector('.ce-mission-current-id');
      if (select) select.addEventListener('change', () => { numeric.value = select.value; });
      card.querySelector('.ce-set-current')?.addEventListener('click', () => previewAndApply('missions', {area_id:area.area_id,current:Number(numeric.value)}, `Set ${area.name} current mission to ${missionLabel(catalog,area.area_id,Number(numeric.value))} (${numeric.value})`));
      card.querySelector('.ce-set-status')?.addEventListener('click', () => previewAndApply('missions', {area_id:area.area_id,status_upper:Number(card.querySelector('.ce-status-upper').value),status_lower:Number(card.querySelector('.ce-status-lower').value)}, `Update ${area.name} mission status words`));
      const list = card.querySelector('.ce-mission-list'), filter = card.querySelector('.ce-mission-filter');
      const allRows = completionRows.length ? completionRows : Array.from({length:64},(_,id)=>({id,label:`Mission ${id}`}));
      const draw = () => {
        const q = String(filter?.value || '').toLowerCase();
        const visible = allRows.filter(r => !q || `${r.label} ${r.id}`.toLowerCase().includes(q));
        list.innerHTML = visible.map(r => `<label class="ce-progress-row"><span>${esc(r.label)}<small>ID ${esc(r.id)}</small></span><span>Complete</span><input type="checkbox" data-mid="${Number(r.id)}" ${completedSet.has(Number(r.id))?'checked':''} ${offline?'':'disabled'}></label>`).join('') || '<div class="ce-progress-empty">No matching missions.</div>';
        list.querySelectorAll('input[data-mid]').forEach(cb => cb.addEventListener('change', async () => {
          const desired = cb.checked; cb.disabled = true;
          const ok = await previewAndApply('missions', {area_id:area.area_id,completed_id:Number(cb.dataset.mid),completed:desired}, `${desired?'Mark complete':'Clear completion'}: ${missionLabel(catalog,area.area_id,Number(cb.dataset.mid))}`);
          if (!ok) { cb.checked = !desired; cb.disabled = !offline; }
        }));
      };
      filter?.addEventListener('input', draw); draw();
    }
  }

  function renderKeyItemEditor() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.key_items;
    if (!box || !entry?.decoded) return;
    const decoded = entry.decoded, catalog = entry.catalog || {}, items = Object.values(catalog.items || {}).sort((a,b)=>Number(a.id)-Number(b.id));
    const owned = new Set((decoded.owned_ids || []).map(Number)), seen = new Set((decoded.seen_ids || []).map(Number)), offline = editableOnline();
    const shell = document.createElement('div'); shell.className='ce-progression';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Key Items</strong>${pill(decoded.family.toUpperCase())}${pill(`${decoded.owned_count} owned`,'ok')}${pill(`${decoded.seen_count} seen`)}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div>
      <div class="ce-progress-card"><div class="ce-toolbar"><input id="ceKeyItemFilter" type="search" placeholder="Search key item name or ID"><label>Numeric ID <input id="ceKeyItemId" type="number" min="0" max="${decoded.table_count*decoded.bits_per_table-1}" style="width:100px;min-width:0"></label><button id="ceKeyItemLoad">Show ID</button></div><div id="ceKeyItemList" class="ce-progress-list" style="margin-top:7px"></div></div>`;
    box.prepend(shell);
    const filter=shell.querySelector('#ceKeyItemFilter'), list=shell.querySelector('#ceKeyItemList'), numeric=shell.querySelector('#ceKeyItemId');
    let forcedId = null;
    const rowFor = id => catalog.items?.[String(id)] || {id,label:`Key Item ${id}`};
    const draw = () => {
      const q=String(filter.value||'').toLowerCase();
      let rows = items.filter(r=>!q||`${r.label} ${r.symbol||''} ${r.id}`.toLowerCase().includes(q));
      if (forcedId !== null && !rows.some(r=>Number(r.id)===forcedId)) rows.unshift(rowFor(forcedId));
      rows = rows.slice(0,250);
      list.innerHTML = rows.map(r=>`<div class="ce-progress-row"><span>${esc(r.label)}<small>ID ${esc(r.id)}${r.symbol?' · '+esc(r.symbol):''}</small></span><label>Owned <input type="checkbox" data-ki="${Number(r.id)}" data-kind="owned" ${owned.has(Number(r.id))?'checked':''} ${offline?'':'disabled'}></label><label class="ce-seen">Seen <input type="checkbox" data-ki="${Number(r.id)}" data-kind="seen" ${seen.has(Number(r.id))?'checked':''} ${offline?'':'disabled'}></label></div>`).join('') || '<div class="ce-progress-empty">No matching key items.</div>';
      list.querySelectorAll('input[data-ki]').forEach(cb=>cb.addEventListener('change',async()=>{
        const id=Number(cb.dataset.ki), kind=cb.dataset.kind, desired=cb.checked, operation={key_item_id:id}; operation[kind]=desired; cb.disabled=true;
        const ok=await previewAndApply('key_items',operation,`${desired?'Set':'Clear'} ${kind}: ${rowFor(id).label} (${id})`);
        if(!ok){cb.checked=!desired;cb.disabled=!offline;}
      }));
    };
    filter.addEventListener('input',()=>{forcedId=null;draw()});
    shell.querySelector('#ceKeyItemLoad').addEventListener('click',()=>{const id=Number(numeric.value);if(!Number.isInteger(id)||id<0||id>decoded.table_count*decoded.bits_per_table-1){alert('Key item ID is outside this server layout.');return}forcedId=id;filter.value='';draw()});
    draw();
  }
})();
