(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'missions-quests') renderVoidwatch();
  };

  const base = () => `/character-editor/characters/${selectedChar}`;
  const post = (path, body) => api(`${base()}/${path}`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})
  });
  const pretty = n => String(n || '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase()).replace(/\b(Ii|Iii|Iv|Vi|V)\b/g, m => m.toUpperCase());

  async function submit(edits, label) {
    const preview = await post('voidwatch-edit/preview', {edits});
    const issues = (preview.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
    if (!preview.ready) { alert(issues || 'Nothing to change.'); return false; }
    if (!confirm(`${label}\n\n${(preview.changes || []).length} change(s) for character ${selectedChar}.${issues ? '\n\n' + issues : ''}`)) return false;
    await post('voidwatch-edit/apply', {approved:true, edits});
    return true;
  }

  async function renderVoidwatch() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-voidwatch-reset-panel').forEach(panel => panel.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-voidwatch-reset-panel';
    shell.innerHTML = '<div class="ce-progress-head"><strong>Voidwatch</strong></div><div class="ce-progress-empty">Loading…</div>';
    box.append(shell);
    let st;
    try { st = await api(`${base()}/voidwatch.json`); } catch (e) { shell.querySelector('.ce-progress-empty').textContent = e.message; return; }
    const offline = editableOnline();
    const dis = offline ? '' : 'disabled';
    const btn = (cls, text, data) => `<button class="${cls}" ${dis} ${data}>${text}</button>`;

    const pathRows = st.paths.map(p => `<tr><th colspan="5" style="text-align:left">${esc(p.name)} path</th></tr>` + p.tiers.map(t => `<tr>
      <td>${esc(pretty(t.name))}</td>
      <td>${t.owned ? pill('key item','ok') : pill('no key item','warn')}</td>
      <td>${btn('vw-ki', t.owned ? 'Remove KI' : 'Add KI', `data-ki="${t.id}" data-owned="${t.owned ? 0 : 1}"`)}</td>
      <td>${t.done ? pill('tier done','ok') : pill('not done','warn')}</td>
      <td>${btn('vw-tier', t.done ? 'Clear flag' : 'Set flag', `data-path="${p.index}" data-tier="${t.tier}" data-done="${t.done ? 0 : 1}"`)}</td></tr>`).join('')).join('');

    const stoneRows = st.voidstones.map(s => `<tr><td>${esc(pretty(s.name))}</td><td>${s.owned ? pill('owned','ok') : pill('not owned','warn')}</td>
      <td>${btn('vw-ki', s.owned ? 'Remove' : 'Add', `data-ki="${s.id}" data-owned="${s.owned ? 0 : 1}"`)}</td></tr>`).join('');

    const atmaRows = st.atmacites.map(a => `<tr>
      <td>${esc(pretty(a.name.replace('ATMACITE_OF_', 'Atmacite of ')))}</td>
      <td>${a.owned ? pill('owned','ok') : pill('not owned','warn')}</td>
      <td>${btn('vw-ki', a.owned ? 'Remove' : 'Add', `data-ki="${a.id}" data-owned="${a.owned ? 0 : 1}"`)}</td>
      <td><input type="number" min="0" max="15" value="${a.level}" class="vw-level" data-var="VWA${a.idx}" style="width:4rem" ${dis}></td>
      <td><select class="vw-inf" data-idx="${a.idx}" ${dis}>${[0,1,2,3].map(s => `<option value="${s}" ${a.infused_slot === s ? 'selected' : ''}>${s ? 'Slot ' + s : 'Not infused'}</option>`).join('')}</select></td></tr>`).join('');

    shell.innerHTML = `<div class="ce-progress-head"><strong>Voidwatch</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
      <div class="ce-progress-card">
        <div class="ce-progress-empty" style="text-align:left">Key items and the officer/refiner progress flags are separate: a tier's <em>flag</em> (VWO_TIERS bit) decides what the refiner will upgrade;
        removing only the key item does not clear it. Atmacite level 0 means "never enriched" (treated as level 1 in game). Not undoable from the audit log.</div>
        <details open><summary>Stratum Abyssites and tier flags</summary><div style="overflow-x:auto"><table class="ce-table">${pathRows}</table></div></details>
        <details><summary>Voidstones and stock</summary><div style="overflow-x:auto"><table class="ce-table">${stoneRows}</table></div>
          <div class="ce-toolbar">Officer stock: <input type="number" min="0" class="vw-stock" value="${st.stock}" style="width:5rem" ${dis}>
          Stock clock (unix): <input type="number" min="0" class="vw-stock-ts" value="${st.stock_ts}" style="width:9rem" ${dis}>
          ${btn('vw-stock-save', 'Save stock', '')}</div></details>
        <details><summary>Atmacites (key item, level, infusion)</summary><div style="overflow-x:auto"><table class="ce-table"><tr><th>Atmacite</th><th>KI</th><th></th><th>Level</th><th>Infused</th></tr>${atmaRows}</table></div></details>
        <div class="ce-toolbar">${btn('vw-reset', 'Reset ALL Voidwatch progress', '')}</div>
      </div>`;

    const run = async (edits, label) => {
      try { if (await submit(edits, label)) { await selectCharacter(selectedChar); await loadCategory('missions-quests'); } } catch (e) { alert(e.message); }
    };
    shell.querySelectorAll('.vw-ki').forEach(b => b.addEventListener('click', () =>
      run([{op:'ki', key_item_id:Number(b.dataset.ki), owned:b.dataset.owned === '1'}], `${b.dataset.owned === '1' ? 'Add' : 'Remove'} key item ${b.dataset.ki}?`)));
    shell.querySelectorAll('.vw-tier').forEach(b => b.addEventListener('click', () =>
      run([{op:'tier', path:Number(b.dataset.path), tier:Number(b.dataset.tier), done:b.dataset.done === '1'}], `${b.dataset.done === '1' ? 'Set' : 'Clear'} tier flag?`)));
    shell.querySelectorAll('.vw-level').forEach(i => i.addEventListener('change', () =>
      run([{op:'var', name:i.dataset.var, value:Number(i.value) || 0}], `Set ${i.dataset.var} to ${i.value}?`)));
    shell.querySelectorAll('.vw-inf').forEach(s => s.addEventListener('change', () => {
      const idx = Number(s.dataset.idx), slot = Number(s.value), edits = [];
      st.atmacites.forEach(a => { if (a.infused_slot && a.idx !== idx && a.infused_slot === slot) edits.push({op:'var', name:`VWA_INF${slot}`, value:0}); });
      [1, 2, 3].forEach(n => { if (st.atmacites[idx].infused_slot === n) edits.push({op:'var', name:`VWA_INF${n}`, value:0}); });
      if (slot) edits.push({op:'var', name:`VWA_INF${slot}`, value:idx + 1});
      run(edits, `Set infusion of atmacite ${idx} to ${slot ? 'slot ' + slot : 'none'}?`);
    }));
    const save = shell.querySelector('.vw-stock-save');
    if (save) save.addEventListener('click', () => run([
      {op:'var', name:'VWO_STOCK', value:Number(shell.querySelector('.vw-stock').value) || 0},
      {op:'var', name:'VWO_STOCK_TS', value:Number(shell.querySelector('.vw-stock-ts').value) || 0}], 'Save voidstone stock?'));
    shell.querySelector('.vw-reset').addEventListener('click', async () => {
      try {
        const preview = await post('voidwatch-reset/preview');
        const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
        if (!preview.ready) { alert(issues || 'Nothing to reset.'); return; }
        const ki = (preview.key_items || []).map(k => k.name).join(', ') || 'none';
        const vars = (preview.vars || []).map(v => `${v.varname}=${v.value}`).join(', ') || 'none';
        if (!confirm(`Reset ALL Voidwatch progress for character ${selectedChar}?\n\nKey items: ${ki}\n\nVariables: ${vars}${issues ? '\n\n' + issues : ''}`)) return;
        const res = await post('voidwatch-reset/apply', {approved:true});
        alert(`Done: ${res.key_items_cleared} key item(s) cleared, ${res.vars_deleted} variable(s) deleted.`);
        await selectCharacter(selectedChar);
        await loadCategory('missions-quests');
      } catch (e) { alert(e.message); }
    });
  }
})();
