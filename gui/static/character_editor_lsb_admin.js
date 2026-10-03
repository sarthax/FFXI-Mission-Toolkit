(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'advanced') renderLsbAdminEditors();
  };

  const FLAG_FIELDS = ['gmModeEnabled','gmHiddenEnabled','muted','rename'];
  const HISTORY_FIELDS = [
    'enemies_defeated','times_knocked_out','mh_entrances','joined_parties','joined_alliances',
    'spells_cast','abilities_used','ws_used','items_used','chats_sent','npc_interactions',
    'battles_fought','gm_calls','distance_travelled'
  ];

  function renderLsbAdminEditors() {
    const box = document.getElementById('categoryData');
    if (!box) return;
    box.querySelectorAll(':scope > .ce-lsb-admin-panel').forEach(node => node.remove());
    if (String(selectedCharacterData?.adapter?.family || '').toLowerCase() !== 'lsb') return;

    const flags = activeCategoryData?.tables?.char_flags?.[0];
    const history = activeCategoryData?.tables?.char_history?.[0];
    if (!flags && !history) return;

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-lsb-admin-panel';
    shell.innerHTML = `<div class="ce-progress-head"><strong>LSB Administrative State</strong>${pill('LandSandBoat only')}${editableOnline() ? pill('offline editing enabled','ok') : pill('editing locked','warn')}</div>
      <div class="ce-muted" style="margin-bottom:8px">Persistent LSB admin flags and history counters. Runtime-only disconnecting, status effects, recasts, pet IDs, and pet BLOB state remain read-only.</div>
      <div class="ce-lsb-admin-body"></div>`;
    box.prepend(shell);
    const body = shell.querySelector('.ce-lsb-admin-body');
    if (flags) body.appendChild(renderTableEditor('char_flags', flags, FLAG_FIELDS, true));
    if (history) body.appendChild(renderTableEditor('char_history', history, HISTORY_FIELDS, false));
  }

  function renderTableEditor(table, row, fields, booleanFields) {
    const card = document.createElement('div');
    card.className = 'ce-card';
    card.style.margin = '6px 0';
    const locked = !editableOnline();
    let html = `<strong>${esc(table)}</strong><div class="ce-kv">`;
    if (table === 'char_flags' && row.disconnecting !== undefined) {
      html += `<div>disconnecting<div class="ce-field-note">runtime/session state · read only</div></div><div class="mono ce-readonly">${esc(row.disconnecting)}</div>`;
    }
    for (const field of fields) {
      if (row[field] === undefined) continue;
      if (booleanFields) {
        html += `<div>${esc(field)}</div><div><select class="ce-lsb-edit" data-table="${table}" data-field="${field}" data-original="${Number(row[field] || 0)}" ${locked?'disabled':''}><option value="0" ${Number(row[field]||0)===0?'selected':''}>0 · false</option><option value="1" ${Number(row[field]||0)===1?'selected':''}>1 · true</option></select></div>`;
      } else {
        html += `<div>${esc(field)}</div><div><input class="ce-edit-input ce-lsb-edit" data-table="${table}" data-field="${field}" data-original="${esc(row[field] ?? 0)}" type="number" min="0" max="4294967295" step="1" value="${esc(row[field] ?? 0)}" ${locked?'disabled':''}></div>`;
      }
    }
    html += `</div><div class="ce-edit-actions"><button class="ce-lsb-preview" ${locked?'disabled':''}>Preview changes</button><span class="ce-muted">${locked?'Character must be verifiably offline':'Preview and confirmation required'}</span></div>`;
    card.innerHTML = html;
    card.querySelector('.ce-lsb-preview')?.addEventListener('click', button => previewLsbAdmin(table, row, card, button.currentTarget));
    return card;
  }

  async function previewLsbAdmin(table, row, card, button) {
    if (!selectedChar || !editableOnline()) return;
    const changes = {};
    card.querySelectorAll('.ce-lsb-edit').forEach(input => {
      if (String(input.value) !== String(input.dataset.original)) changes[input.dataset.field] = Number(input.value);
    });
    if (!Object.keys(changes).length) {
      alert('No values changed.');
      return;
    }
    button.disabled = true;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/lsb-admin/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table,changes})
      });
      const issues = (preview.issues || []).map(i => `${i.blocking?'BLOCK':'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This edit is not write-ready.');
        return;
      }
      const delta = Object.entries(preview.changes || {}).map(([k,v]) => `${k}: ${preview.before?.[k]} → ${v}`).join('\n');
      if (!confirm(`Apply LSB ${table} changes?\n\n${delta}${issues?`\n\n${issues}`:''}`)) return;
      const result = await api(`/character-editor/characters/${selectedChar}/lsb-admin/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({table,changes,expected_before:preview.before,approved:true})
      });
      if (result.audit_error) alert(`Change committed, but audit logging reported: ${result.audit_error}`);
      await selectCharacter(selectedChar);
      await activateTab('advanced');
    } catch (e) {
      alert(e.message);
    } finally {
      button.disabled = false;
    }
  }
})();
