(() => {
  const root = document.getElementById('server-environments');
  if (!root) return;

  const API_ROOT = '/character-editor/environments';
  let state = {profiles: [], active: null, families: [], environments: []};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  async function api(path, options) {
    const response = await fetch(API_ROOT + path, options);
    const payload = await response.json().catch(() => ({detail: response.statusText}));
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    return payload;
  }

  function resetForm() {
    document.getElementById('envProfileId').value = '';
    document.getElementById('envFormTitle').textContent = 'Add server environment';
    document.getElementById('envName').value = '';
    document.getElementById('envEnvironment').value = 'test';
    document.getElementById('envFamily').value = 'auto';
    document.getElementById('envRoot').value = '';
    document.getElementById('envEnabled').checked = true;
    document.getElementById('envNotes').value = '';
    document.getElementById('envMakeActive').checked = false;
    document.getElementById('envFormMessage').textContent = '';
  }

  function populateForm(profile) {
    document.getElementById('envProfileId').value = profile.profile_id;
    document.getElementById('envFormTitle').textContent = `Edit ${profile.name}`;
    document.getElementById('envName').value = profile.name || '';
    document.getElementById('envEnvironment').value = profile.environment || 'other';
    document.getElementById('envFamily').value = profile.family || 'auto';
    document.getElementById('envRoot').value = profile.server_root || '';
    document.getElementById('envEnabled').checked = Boolean(profile.enabled);
    document.getElementById('envNotes').value = profile.notes || '';
    document.getElementById('envMakeActive').checked = Boolean(profile.is_active);
    document.getElementById('envFormMessage').textContent = '';
  }

  function renderActive() {
    const box = document.getElementById('envActiveSummary');
    const active = state.active;
    if (!active) {
      box.innerHTML = '<strong>No named environment active.</strong> <span class="muted">Legacy single-server path settings remain in use until a named environment is activated.</span>';
      return;
    }
    const live = active.environment === 'live' ? '<span class="chip" style="background:var(--red-soft);color:var(--red);">LIVE</span>' : '';
    box.innerHTML = `<strong>${esc(active.name)}</strong> ${live} <span class="chip">${esc(String(active.environment).toUpperCase())}</span> <span class="chip">${esc(String(active.family).toUpperCase())}</span><div class="mono muted" style="margin-top:5px">${esc(active.server_root)}</div>`;
  }

  function renderProfiles() {
    const box = document.getElementById('envProfiles');
    box.innerHTML = state.profiles.map(profile => {
      const active = profile.is_active ? '<span class="chip" style="background:var(--accent-soft);">ACTIVE</span>' : '';
      const live = profile.environment === 'live' ? '<span class="chip" style="background:var(--red-soft);color:var(--red);">LIVE</span>' : '';
      const disabled = profile.enabled ? '' : '<span class="chip">DISABLED</span>';
      return `<div style="border:1px solid var(--border);border-radius:7px;padding:10px;margin:8px 0;background:var(--surface)">
        <div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap"><strong>${esc(profile.name)}</strong>${active}${live}${disabled}<span style="flex:1"></span><span class="muted">${esc(String(profile.family).toUpperCase())}</span></div>
        <div class="mono" style="margin:6px 0">${esc(profile.server_root)}</div>
        <div class="muted">${esc(String(profile.environment).toUpperCase())}${profile.notes ? ' · ' + esc(profile.notes) : ''}</div>
        <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:8px">
          <button type="button" data-edit="${profile.profile_id}">Edit</button>
          <button type="button" data-test="${profile.profile_id}">Test connection</button>
          <button type="button" data-activate="${profile.profile_id}" ${profile.is_active || !profile.enabled ? 'disabled' : ''}>Activate</button>
          <button type="button" data-delete="${profile.profile_id}" ${profile.is_active ? 'disabled' : ''}>Delete</button>
        </div>
      </div>`;
    }).join('') || '<p class="muted">No named server environments yet. Add Live, Test, Dev, Backup, or other server checkouts here.</p>';

    box.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
      const profile = state.profiles.find(row => Number(row.profile_id) === Number(button.dataset.edit));
      if (profile) populateForm(profile);
    }));
    box.querySelectorAll('[data-test]').forEach(button => button.addEventListener('click', () => testProfile(Number(button.dataset.test))));
    box.querySelectorAll('[data-activate]').forEach(button => button.addEventListener('click', () => activateProfile(Number(button.dataset.activate))));
    box.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', () => deleteProfile(Number(button.dataset.delete))));
  }

  async function refresh() {
    const message = document.getElementById('envLoadMessage');
    try {
      state = await api('/profiles.json');
      document.getElementById('envEnvironment').innerHTML = state.environments.map(value => `<option value="${esc(value)}">${esc(value.toUpperCase())}</option>`).join('');
      document.getElementById('envFamily').innerHTML = state.families.map(value => `<option value="${esc(value)}">${esc(value.toUpperCase())}</option>`).join('');
      renderActive();
      renderProfiles();
      message.textContent = '';
    } catch (error) {
      message.textContent = 'Unable to load server environments: ' + error.message;
    }
  }

  async function saveProfile() {
    const id = document.getElementById('envProfileId').value;
    const body = {
      name: document.getElementById('envName').value.trim(),
      environment: document.getElementById('envEnvironment').value,
      family: document.getElementById('envFamily').value,
      server_root: document.getElementById('envRoot').value.trim(),
      enabled: document.getElementById('envEnabled').checked,
      notes: document.getElementById('envNotes').value.trim(),
      make_active: document.getElementById('envMakeActive').checked,
    };
    const message = document.getElementById('envFormMessage');
    if (!body.name || !body.server_root) {
      message.textContent = 'Name and server root are required.';
      return;
    }
    if (body.environment === 'live' && body.make_active && !confirm(`Save and activate LIVE environment "${body.name}"?`)) return;
    message.textContent = 'Saving…';
    try {
      const saved = await api(id ? `/profiles/${Number(id)}` : '/profiles', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
      });
      if (id && body.make_active && !saved.is_active) await api(`/profiles/${Number(id)}/activate`, {method: 'POST'});
      await refresh();
      message.textContent = 'Saved.';
      if (body.make_active) {
        const active = state.profiles.find(row => row.is_active);
        if (active) populateForm(active);
      } else {
        const current = state.profiles.find(row => Number(row.profile_id) === Number(saved.profile_id));
        if (current) populateForm(current);
      }
    } catch (error) {
      message.textContent = error.message;
    }
  }

  async function activateProfile(id) {
    const profile = state.profiles.find(row => Number(row.profile_id) === Number(id));
    if (!profile) return;
    if (profile.environment === 'live' && !confirm(`Activate LIVE environment "${profile.name}"?\n\nProfile-aware Server tools will use this environment.`)) return;
    try {
      await api(`/profiles/${id}/activate`, {method: 'POST'});
      await refresh();
    } catch (error) {
      alert(error.message);
    }
  }

  async function testProfile(id) {
    const output = document.getElementById('envTestResult');
    output.textContent = 'Testing connection…';
    try {
      const result = await api(`/profiles/${id}/test`, {method: 'POST'});
      const database = result.database || {};
      const adapter = result.adapter || {};
      output.textContent = [
        'Connection: OK',
        `Adapter: ${(adapter.family || 'unknown').toUpperCase()} (${adapter.confidence || 'unknown'} confidence)`,
        `Database: ${database.database || 'unknown'}`,
        `Host: ${database.host || 'unknown'}:${database.port || ''}`,
        `User: ${database.user || 'unknown'}`,
        `Server version: ${result.server_version || 'unknown'}`,
        `Config: ${database.conf_path || 'unknown'}`,
      ].join('\n');
    } catch (error) {
      output.textContent = `Connection failed: ${error.message}`;
    }
  }

  async function deleteProfile(id) {
    const profile = state.profiles.find(row => Number(row.profile_id) === Number(id));
    if (!profile || !confirm(`Delete server environment "${profile.name}"?\n\nThis does not modify the server or its database.`)) return;
    try {
      await api(`/profiles/${id}/delete`, {method: 'POST'});
      resetForm();
      await refresh();
    } catch (error) {
      alert(error.message);
    }
  }

  document.getElementById('envSave').addEventListener('click', saveProfile);
  document.getElementById('envReset').addEventListener('click', resetForm);
  document.getElementById('envRefresh').addEventListener('click', refresh);
  refresh().then(resetForm);
})();

(() => {
  const anchor = document.getElementById('server-environments');
  if (!anchor) return;
  const API = '/character-editor/client-cache';
  const section = document.createElement('section');
  section.id = 'client-dat-cache';
  section.innerHTML = `
    <h2>Client DAT cache</h2>
    <p class="muted">Item DAT metadata and embedded icons are cached on first use. You can optionally pre-extract the complete item DAT surface once so Character Editor and other item views never parse those records while rendering. Source DAT size/mtime changes invalidate only the affected cached category.</p>
    <div class="table-wrap" style="padding:14px">
      <div id="clientCacheSummary" class="muted">Loading cache status…</div>
      <div id="clientCacheSources" style="margin-top:10px"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        <button type="button" id="clientCacheBuildAll">Build all item DAT cache</button>
        <button type="button" id="clientCacheRefresh">Refresh status</button>
        <button type="button" id="clientCacheClear">Clear cache</button>
      </div>
      <div id="clientCacheProgress" class="muted" style="margin-top:9px"></div>
    </div>`;
  anchor.insertAdjacentElement('afterend', section);

  const summary = section.querySelector('#clientCacheSummary');
  const sourcesBox = section.querySelector('#clientCacheSources');
  const progress = section.querySelector('#clientCacheProgress');
  const buildButton = section.querySelector('#clientCacheBuildAll');
  const fmtBytes = n => {
    const value = Number(n || 0);
    if (value < 1024) return `${value} B`;
    if (value < 1024*1024) return `${(value/1024).toFixed(1)} KB`;
    return `${(value/1024/1024).toFixed(1)} MB`;
  };
  async function call(path, options) {
    const r = await fetch(API + path, options);
    const j = await r.json().catch(() => ({detail:r.statusText}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    return j;
  }
  async function refreshCache() {
    try {
      const j = await call('/status.json');
      summary.innerHTML = `<strong>${j.fresh_rows}/${j.total_records}</strong> fresh records · <strong>${j.stale_rows}</strong> stale · <strong>${j.orphaned_rows}</strong> orphaned · <strong>${j.available_rows}</strong> extracted items · <strong>${fmtBytes(j.total_bytes)}</strong> on disk ${j.complete ? '<span class="chip">COMPLETE</span>' : '<span class="chip">NEEDS BUILD</span>'}<div class="mono muted" style="margin-top:4px">${j.client_root || ''}</div>`;
      sourcesBox.innerHTML = (j.sources||[]).map(s => `<div style="display:flex;gap:8px;align-items:center;margin:3px 0"><span style="min-width:120px">${s.category}</span><span class="chip">${s.fresh_count}/${s.record_count} fresh</span>${s.stale_count ? `<span class="chip">${s.stale_count} stale</span>` : ''}<span class="mono muted">${s.rom_path}</span></div>`).join('');
      return j;
    } catch (e) {
      summary.textContent = `Cache unavailable: ${e.message}`;
      sourcesBox.innerHTML = '';
      throw e;
    }
  }
  async function buildAll() {
    buildButton.disabled = true;
    try {
      const status = await refreshCache();
      const sources = status.sources || [];
      let done = 0;
      for (const source of sources) {
        progress.textContent = `Building ${source.category} (${done+1}/${sources.length})…`;
        const result = await call('/build-source', {
          method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({category:source.category})
        });
        done += 1;
        progress.textContent = `Built ${source.category}: ${result.available} items, ${result.empty} empty slots, ${result.failed} failures in ${result.elapsed_seconds}s. (${done}/${sources.length})`;
        await refreshCache();
      }
      progress.textContent = `Complete. Built/refreshed ${sources.length} item DAT categories.`;
    } catch (e) {
      progress.textContent = `Build stopped: ${e.message}`;
    } finally {
      buildButton.disabled = false;
    }
  }
  section.querySelector('#clientCacheRefresh').addEventListener('click', refreshCache);
  buildButton.addEventListener('click', buildAll);
  section.querySelector('#clientCacheClear').addEventListener('click', async () => {
    if (!confirm('Clear the cached client item metadata and icons? They will be recreated lazily as needed.')) return;
    try {
      const result = await call('/clear', {method:'POST'});
      progress.textContent = `Cleared ${fmtBytes(result.bytes_removed)}. Lazy extraction remains enabled.`;
      await refreshCache();
    } catch (e) { progress.textContent = e.message; }
  });
  refreshCache();
})();
