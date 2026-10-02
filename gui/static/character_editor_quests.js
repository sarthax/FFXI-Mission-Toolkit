(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const originalLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await originalLoadCategory(key);
    if (key === 'missions-quests') renderQuestState();
  };

  function sourceText(catalog) {
    const src = catalog?.source || {};
    if (!src.available) return 'checkout quest catalog unavailable · numeric IDs remain available';
    return `${src.kind || 'quests.lua'} · ${src.path || ''}`;
  }

  function questRow(catalog, areaId, questId) {
    return catalog?.areas?.[String(areaId)]?.[String(questId)] || {id:Number(questId), label:`Quest ${questId}`};
  }

  function issueText(preview) {
    return (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
  }

  async function previewAndApply(operation, summary) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/packed/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({capability:'quests', operation})
      });
      const issues = issueText(preview);
      if (!preview.ready) {
        alert(issues || 'This quest edit is not write-ready.');
        return false;
      }
      if (!confirm(`${summary}\n\nBefore: ${pretty(preview.before)}\nAfter: ${pretty(preview.after)}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/packed/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          capability:'quests', operation, expected_before_sha256:preview.before_sha256, approved:true
        })
      });
      await selectCharacter(selectedChar);
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }

  function renderQuestState() {
    const box = document.getElementById('categoryData');
    const entry = activeCategoryData?.packed?.quests;
    if (!box || !entry?.decoded) return;

    const decoded = entry.decoded || {};
    const catalog = entry.catalog || {};
    const offline = editableOnline() && entry.editable === true;
    const shell = document.createElement('div');
    shell.className = 'ce-progression';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Quest State</strong>${pill(decoded.family?.toUpperCase() || '')}${pill(decoded.layout || '')}${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">${esc(sourceText(catalog))}</span></div><div class="ce-progress-grid ce-quest-grid"></div>`;
    box.prepend(shell);

    const grid = shell.querySelector('.ce-quest-grid');
    for (const area of decoded.areas || []) {
      const currentSet = new Set((area.current_ids || []).map(Number));
      const completedSet = new Set((area.completed_ids || []).map(Number));
      const catalogRows = Object.values(catalog?.areas?.[String(area.area_id)] || {}).sort((a,b)=>Number(a.id)-Number(b.id));
      const ids = new Set([...catalogRows.map(r=>Number(r.id)), ...currentSet, ...completedSet]);
      const rowsById = new Map(catalogRows.map(r=>[Number(r.id), r]));
      const card = document.createElement('div');
      card.className = 'ce-progress-card';
      card.innerHTML = `<h4>${esc(area.name)} ${pill(`${currentSet.size} active`)} ${pill(`${completedSet.size} complete`,'ok')}</h4>
        <div class="ce-muted">Area ${esc(area.area_id)} · IDs 0-255 · 32-byte current + 32-byte completed bitsets</div>
        <div class="ce-toolbar" style="margin-top:7px"><input class="ce-quest-filter" type="search" placeholder="Filter quest name or ID"><label>Numeric ID <input class="ce-quest-id" type="number" min="0" max="255" style="width:90px;min-width:0"></label><button class="ce-quest-show">Show ID</button></div>
        <div class="ce-progress-list ce-quest-list" style="margin-top:7px"></div>`;
      grid.appendChild(card);

      const filter = card.querySelector('.ce-quest-filter');
      const numeric = card.querySelector('.ce-quest-id');
      const list = card.querySelector('.ce-quest-list');
      let forcedId = null;
      const draw = () => {
        const q = String(filter.value || '').toLowerCase();
        let visibleIds = [...ids].sort((a,b)=>a-b);
        if (forcedId !== null && !ids.has(forcedId)) visibleIds.unshift(forcedId);
        const rows = visibleIds.map(id => rowsById.get(id) || questRow(catalog, area.area_id, id)).filter(row => !q || `${row.label} ${row.symbol || ''} ${row.id}`.toLowerCase().includes(q));
        list.innerHTML = rows.map(row => `<div class="ce-progress-row"><span>${esc(row.label)}<small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small></span><label>Active <input type="checkbox" data-qid="${Number(row.id)}" data-state="current" ${currentSet.has(Number(row.id))?'checked':''} ${offline?'':'disabled'}></label><label class="ce-seen">Completed <input type="checkbox" data-qid="${Number(row.id)}" data-state="completed" ${completedSet.has(Number(row.id))?'checked':''} ${offline?'':'disabled'}></label></div>`).join('') || '<div class="ce-progress-empty">No matching quests.</div>';
        list.querySelectorAll('input[data-qid]').forEach(cb => cb.addEventListener('change', async () => {
          const questId = Number(cb.dataset.qid), state = cb.dataset.state, desired = cb.checked;
          cb.disabled = true;
          const row = questRow(catalog, area.area_id, questId);
          const ok = await previewAndApply(
            {area_id:Number(area.area_id), quest_id:questId, state, enabled:desired},
            `${desired ? 'Set' : 'Clear'} ${state === 'current' ? 'active/accepted' : 'completed'}: ${row.label} (${questId})`
          );
          if (!ok) { cb.checked = !desired; cb.disabled = !offline; }
        }));
      };
      filter.addEventListener('input', () => { forcedId = null; draw(); });
      card.querySelector('.ce-quest-show').addEventListener('click', () => {
        const value = Number(numeric.value);
        if (!Number.isInteger(value) || value < 0 || value > 255) { alert('Quest ID must be between 0 and 255.'); return; }
        forcedId = value; filter.value = ''; draw();
      });
      draw();
    }
  }
})();
