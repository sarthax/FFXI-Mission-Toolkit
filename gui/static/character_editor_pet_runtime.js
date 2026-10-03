(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'pets-effects') await renderPetRuntimeSummary();
  };

  function kvRows(obj) {
    if (!obj) return '<div class="ce-progress-empty">No data.</div>';
    return `<div class="ce-kv">${Object.entries(obj).map(([k,v]) => `<div>${esc(k)}</div><div class="mono ce-readonly">${esc(pretty(v))}</div>`).join('')}</div>`;
  }

  async function renderPetRuntimeSummary() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-pet-runtime-panel').forEach(node => node.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-pet-runtime-panel';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Companion & Runtime Summary</strong>${pill('read only','warn')}</div><div class="ce-progress-card"><div class="ce-muted">Resolving companion names and persisted runtime state…</div></div>`;
    box.prepend(shell);
    const card = shell.querySelector('.ce-progress-card');
    try {
      const p = await api(`/character-editor/characters/${selectedChar}/pet-runtime.json`);
      const companion = p.companion || {};
      const wyvern = companion.wyvern || {};
      const automaton = companion.automaton || {};
      let html = `<div class="ce-muted" style="margin-bottom:8px">${esc(p.safety?.reason || '')}</div>`;
      html += `<div class="ce-card" style="margin:6px 0"><strong>Companions</strong><div class="ce-kv">
        <div>Wyvern</div><div>${esc(wyvern.name || 'Unnamed / not selected')} <span class="mono ce-muted">ID ${esc(wyvern.id ?? 0)}</span></div>
        <div>Automaton</div><div>${esc(automaton.name || 'Unnamed / not selected')} <span class="mono ce-muted">ID ${esc(automaton.id ?? 0)}</span></div>
        <div>Adventuring fellow ID</div><div class="mono ce-readonly">${esc(companion.adventuring_fellow_id ?? 0)}</div>
        <div>Chocobo link ID</div><div class="mono ce-readonly">${esc(companion.chocobo_id ?? 0)}</div>
      </div></div>`;
      html += `<div class="ce-card" style="margin:6px 0"><strong>Opaque Pet State</strong>${kvRows(companion.opaque || {})}<div class="ce-muted">Sizes only. Attachment/chocobo BLOBs remain codec-gated and are not editable.</div></div>`;
      if (p.chocobo) html += `<div class="ce-card" style="margin:6px 0"><strong>Chocobo Profile</strong>${kvRows(p.chocobo)}</div>`;
      const effects = p.effects || [], recasts = p.recasts || [];
      html += `<div class="ce-card" style="margin:6px 0"><strong>Persisted Status Effects</strong> ${pill(`${effects.length} row(s)`)}`;
      html += effects.length ? `<table class="ce-table"><thead><tr><th>Effect</th><th>Power</th><th>Duration</th><th>Tier</th><th>Flags</th></tr></thead><tbody>${effects.map(r => `<tr><td>${esc(r.effectid)}</td><td>${esc(r.power)}</td><td>${esc(r.duration)}</td><td>${esc(r.tier)}</td><td>${esc(r.flags)}</td></tr>`).join('')}</tbody></table>` : '<div class="ce-muted">No persisted effects.</div>';
      html += `<div class="ce-muted">Persisted runtime restoration state · direct row editing disabled.</div></div>`;
      html += `<div class="ce-card" style="margin:6px 0"><strong>Persisted Recasts</strong> ${pill(`${recasts.length} row(s)`)}`;
      html += recasts.length ? `<table class="ce-table"><thead><tr><th>ID</th><th>Time</th><th>Recast</th></tr></thead><tbody>${recasts.map(r => `<tr><td>${esc(r.id)}</td><td>${esc(r.time)}</td><td>${esc(r.recast)}</td></tr>`).join('')}</tbody></table>` : '<div class="ce-muted">No persisted recasts.</div>';
      html += `<div class="ce-muted">Cooldown restoration state · direct row editing disabled.</div></div>`;
      card.innerHTML = html;
    } catch (e) {
      card.innerHTML = `<div class="ce-progress-empty">${esc(e.message)}</div>`;
    }
  }
})();
