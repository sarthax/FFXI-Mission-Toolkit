(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'advanced') await renderAuditHistory();
  };

  function compactTarget(event) {
    const target = event.target || {};
    if (event.operation?.startsWith('inventory.')) {
      const item = target.item_id ? `item ${target.item_id}` : 'inventory row';
      const loc = target.location ?? target.source_location ?? target.destination_location;
      const slot = target.slot ?? target.source_slot ?? target.destination_slot;
      return `${item}${loc !== undefined ? ` · location ${loc}` : ''}${slot !== undefined ? ` · slot ${slot}` : ''}`;
    }
    if (event.operation?.startsWith('spell.')) {
      const spell = target.spell || {};
      return `${spell.name || 'Spell'} ${target.spell_id ?? ''}`.trim();
    }
    if (event.operation?.startsWith('blacklist.')) {
      const person = target.target || {};
      return `${person.charname || 'Character'} ${target.target_id ?? ''}`.trim();
    }
    if (event.operation === 'scalar.update') {
      const selector = Object.entries(target.selector || {}).map(([k,v]) => `${k}=${v}`).join(', ');
      return `${target.table || 'row'}${selector ? ` · ${selector}` : ''}`;
    }
    if (event.operation?.startsWith('packed.')) {
      return `${target.capability || event.operation.slice(7)} · chars.${target.column || '?'}`;
    }
    if (event.operation?.startsWith('undo.')) {
      return `restored ${event.metadata?.original_event_id || target.original_event_id || 'prior event'}`;
    }
    return Object.keys(target).length ? JSON.stringify(target).slice(0, 160) : '';
  }

  function formatTime(value) {
    try { return new Date(value).toLocaleString(); }
    catch (_) { return String(value || ''); }
  }

  async function renderAuditHistory() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-audit-panel').forEach(panel => panel.remove());

    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-audit-panel';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Audit History</strong>${pill('durable local journal')}${editableOnline() ? pill('undo enabled','ok') : pill('undo locked','warn')}<span class="sp"></span><button class="ce-audit-refresh">Refresh</button></div>
      <div class="ce-progress-card"><div class="ce-muted" style="margin-bottom:7px">Committed Character Editor changes. Undo requires the character to be offline and the live target to still match the recorded after-state exactly.</div><div class="ce-audit-list"><div class="ce-progress-empty">Loading history…</div></div></div>`;
    box.appendChild(shell);
    shell.querySelector('.ce-audit-refresh')?.addEventListener('click', renderAuditHistory);
    const list = shell.querySelector('.ce-audit-list');

    try {
      const payload = await api(`/character-editor/characters/${selectedChar}/audit.json?limit=100`);
      const events = payload.events || [];
      const undone = new Set(events.filter(e => String(e.operation || '').startsWith('undo.')).map(e => e.metadata?.original_event_id).filter(Boolean));
      if (!events.length) {
        list.innerHTML = '<div class="ce-progress-empty">No Character Editor audit events have been recorded for this character.</div>';
        return;
      }
      list.innerHTML = events.map(event => {
        const isUndo = String(event.operation || '').startsWith('undo.');
        const wasUndone = undone.has(event.event_id);
        const canAttempt = Boolean(event.undo_supported) && !isUndo && !wasUndone;
        const disabled = !canAttempt || !editableOnline();
        const status = isUndo ? pill('undo','ok') : wasUndone ? pill('undone','ok') : event.undo_supported ? pill('undoable') : pill('history only');
        return `<div class="ce-card ce-audit-row" style="margin:6px 0" data-event="${esc(event.event_id)}">
          <div class="ce-toolbar"><strong>${esc(event.operation)}</strong>${status}<span class="sp"></span><span class="ce-muted">${esc(formatTime(event.timestamp_utc))}</span></div>
          <div>${esc(compactTarget(event))}</div>
          <div class="mono ce-muted" style="font-size:.8em">${esc(event.event_id)}</div>
          <div class="ce-edit-actions"><button class="ce-audit-undo" ${disabled ? 'disabled' : ''}>Undo</button><span class="ce-muted">${wasUndone ? 'Already restored by a later audit event' : canAttempt ? (editableOnline() ? 'Preview required before restore' : 'Character must be offline') : 'No automatic restore for this event'}</span></div>
        </div>`;
      }).join('');
      list.querySelectorAll('.ce-audit-undo:not([disabled])').forEach(button => {
        const row = button.closest('.ce-audit-row');
        button.addEventListener('click', () => previewUndo(row?.dataset.event, button));
      });
    } catch (e) {
      list.innerHTML = `<div class="ce-progress-empty">${esc(e.message)}</div>`;
    }
  }

  async function previewUndo(eventId, button) {
    if (!eventId || !selectedChar || !editableOnline()) return;
    button.disabled = true;
    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/audit/${encodeURIComponent(eventId)}/undo/preview`, {method:'POST'});
      const issues = (preview.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This audit event is not currently undo-ready.');
        return;
      }
      const target = compactTarget({operation:preview.operation,target:preview.target});
      const message = `Undo ${preview.operation}?\n\n${target}\n\nThis restores the exact recorded before-state and creates a new undo audit event.${issues ? `\n\n${issues}` : ''}`;
      if (!confirm(message)) return;
      const result = await api(`/character-editor/characters/${selectedChar}/audit/${encodeURIComponent(eventId)}/undo/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({approved:true})
      });
      if (result.audit_error) alert(`Restore committed, but audit logging reported: ${result.audit_error}`);
      await selectCharacter(selectedChar);
      if (activeTab !== 'advanced') await activateTab('advanced');
      else await loadCategory('advanced');
    } catch (e) {
      alert(e.message);
    } finally {
      button.disabled = false;
    }
  }
})();
