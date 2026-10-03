(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'spells-abilities') await renderSpellManager();
  };

  async function previewAndApply(spell, action, learnedBefore) {
    if (!selectedChar) return false;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/spells/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({spell_id:Number(spell.spellid), action})
      });
      const issues = (preview?.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This spell change is not write-ready.');
        return false;
      }
      const verb = action === 'learn' ? 'Learn' : 'Unlearn';
      if (!confirm(`${verb} ${spell.name} (ID ${spell.spellid})?\n\nBefore: ${preview.learned_before ? 'learned' : 'not learned'}\nAfter: ${preview.learned_after ? 'learned' : 'not learned'}${issues ? '\n\n' + issues : ''}\n\nApply this change?`)) return false;
      await api(`/character-editor/characters/${selectedChar}/spells/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          spell_id:Number(spell.spellid), action,
          expected_learned_before:Boolean(learnedBefore), approved:true
        })
      });
      await selectCharacter(selectedChar);
      await loadCategory('spells-abilities');
      return true;
    } catch (e) {
      alert(e.message);
      return false;
    }
  }

  async function renderSpellManager() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-spell-manager').forEach(panel => panel.remove());

    const offline = editableOnline();
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-spell-manager';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Spell Manager</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}</div>
      <div class="ce-progress-card"><div class="ce-toolbar"><input class="ce-spell-filter" type="search" placeholder="Search spell name or ID" style="flex:1"><label class="ce-muted"><input class="ce-spell-learned-only" type="checkbox"> Learned only</label><span class="ce-spell-count"></span></div><div class="ce-progress-list ce-spell-list" style="max-height:520px;overflow:auto"></div></div>`;
    box.prepend(shell);

    const list = shell.querySelector('.ce-spell-list');
    const count = shell.querySelector('.ce-spell-count');
    list.innerHTML = '<div class="ce-progress-empty">Loading spell catalog…</div>';

    try {
      const [catalogPayload, learnedPayload] = await Promise.all([
        api('/character-editor/spells.json?limit=1000'),
        api(`/character-editor/characters/${selectedChar}/spells.json`)
      ]);
      const rows = (catalogPayload?.rows || []).map(row => ({...row, spellid:Number(row.spellid)}));
      const learned = new Set((learnedPayload?.spell_ids || []).map(Number));
      const filter = shell.querySelector('.ce-spell-filter');
      const learnedOnly = shell.querySelector('.ce-spell-learned-only');

      const draw = () => {
        const q = String(filter.value || '').trim().toLowerCase();
        const visible = rows.filter(row => {
          if (learnedOnly.checked && !learned.has(row.spellid)) return false;
          if (!q) return true;
          return `${row.name || ''} ${row.spellid}`.toLowerCase().includes(q);
        });
        count.innerHTML = `${pill(`${learned.size} learned`,'ok')}${pill(`${visible.length} shown`)}`;
        list.innerHTML = visible.map(row => {
          const has = learned.has(row.spellid);
          const meta = [
            `ID ${row.spellid}`,
            row.skill !== undefined ? `skill ${row.skill}` : '',
            row.element !== undefined ? `element ${row.element}` : '',
            row.mpCost !== undefined ? `MP ${row.mpCost}` : ''
          ].filter(Boolean).join(' · ');
          return `<div class="ce-progress-row"><span>${esc(row.name || `Spell ${row.spellid}`)}<small>${esc(meta)}</small></span><span>${has ? pill('learned','ok') : pill('not learned')} <button class="ce-spell-toggle" data-id="${row.spellid}" data-action="${has ? 'unlearn' : 'learn'}" ${offline ? '' : 'disabled'}>${has ? 'Unlearn' : 'Learn'}</button></span></div>`;
        }).join('') || '<div class="ce-progress-empty">No matching spells.</div>';
        list.querySelectorAll('.ce-spell-toggle').forEach(button => {
          button.addEventListener('click', async () => {
            const spellId = Number(button.dataset.id);
            const row = rows.find(item => item.spellid === spellId);
            if (!row) return;
            await previewAndApply(row, button.dataset.action, learned.has(spellId));
          });
        });
      };
      filter.addEventListener('input', draw);
      learnedOnly.addEventListener('change', draw);
      draw();
    } catch (e) {
      list.innerHTML = `<div class="ce-progress-empty">${esc(e.message)}</div>`;
    }
  }
})();
