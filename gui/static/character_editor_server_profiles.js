(() => {
  if (!document.querySelector('.character-editor-page')) return;

  const API_ROOT = '/character-editor/environments';
  let environmentState = {profiles: [], active: null, families: [], environments: []};

  async function envApi(path, options) {
    const response = await fetch(API_ROOT + path, options);
    const payload = await response.json().catch(() => ({detail: response.statusText}));
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    return payload;
  }

  function label(profile) {
    const family = String(profile.family || 'auto').toUpperCase();
    const environment = String(profile.environment || 'other').toUpperCase();
    return `${profile.name} — ${environment} / ${family}`;
  }

  function activeWarning(profile) {
    if (!profile) return '';
    if (profile.environment === 'live') return 'LIVE';
    if (profile.environment === 'backup') return 'BACKUP';
    return String(profile.environment || '').toUpperCase();
  }

  function installToolbar() {
    const toolbar = document.querySelector('.character-editor-page .dense-toolbar');
    if (!toolbar || document.getElementById('serverEnvironmentSelect')) return;

    const select = document.createElement('select');
    select.id = 'serverEnvironmentSelect';
    select.title = 'Active server environment';
    select.style.maxWidth = '310px';

    const badge = document.createElement('span');
    badge.id = 'serverEnvironmentBadge';
    badge.className = 'ce-pill';

    const manage = document.createElement('button');
    manage.type = 'button';
    manage.textContent = 'Manage environments';
    manage.addEventListener('click', openManager);

    const spacer = toolbar.querySelector('.sp');
    toolbar.insertBefore(select, spacer || null);
    toolbar.insertBefore(badge, spacer || null);
    toolbar.insertBefore(manage, spacer || null);

    select.addEventListener('change', async () => {
      const profileId = Number(select.value);
      const profile = environmentState.profiles.find(row => Number(row.profile_id) === profileId);
      if (!profile || profile.is_active) return;
      if (profile.environment === 'live' && !confirm(`Switch active server environment to LIVE profile "${profile.name}"?\n\nCharacter Editor writes will target that environment.`)) {
        renderToolbar();
        return;
      }
      select.disabled = true;
      try {
        await envApi(`/profiles/${profileId}/activate`, {method: 'POST'});
        location.reload();
      } catch (error) {
        alert(error.message);
        select.disabled = false;
        renderToolbar();
      }
    });
  }

  function renderToolbar() {
    const select = document.getElementById('serverEnvironmentSelect');
    const badge = document.getElementById('serverEnvironmentBadge');
    if (!select || !badge) return;

    const enabled = environmentState.profiles.filter(row => row.enabled);
    if (!enabled.length) {
      select.innerHTML = '<option value="">No named environments</option>';
      select.disabled = true;
    } else {
      select.disabled = false;
      select.innerHTML = enabled.map(row => `<option value="${Number(row.profile_id)}" ${row.is_active ? 'selected' : ''}>${esc(label(row))}</option>`).join('');
    }

    const active = environmentState.active;
    badge.textContent = active ? activeWarning(active) : 'LEGACY';
    badge.className = 'ce-pill ' + (active?.environment === 'live' ? 'bad' : active ? 'ok' : 'warn');
    badge.title = active ? `${active.name}\n${active.server_root}` : 'Using legacy single-server settings';
  }

  function ensureDialog() {
    if (document.getElementById('serverEnvironmentDialog')) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'serverEnvironmentDialog';
    dialog.style.width = 'min(1050px,95vw)';
    dialog.style.maxHeight = '90vh';
    dialog.innerHTML = `
      <form method="dialog" style="float:right"><button>Close</button></form>
      <h3>Server Environments</h3>
      <p class="ce-muted">Configure multiple Live, Test, Dev, or Backup server checkouts. Database credentials stay in each server's native configuration and are never displayed here.</p>
      <div style="display:grid;grid-template-columns:minmax(330px,.8fr) minmax(420px,1.2fr);gap:12px;clear:both">
        <section class="ce-card">
          <h4 id="envFormTitle" style="margin-top:0">Add environment</h4>
          <input id="envProfileId" type="hidden">
          <div class="ce-kv">
            <div>Name</div><div><input id="envName" placeholder="Live, Test, DSP Legacy…"></div>
            <div>Environment</div><div><select id="envEnvironment"></select></div>
            <div>Server family</div><div><select id="envFamily"></select></div>
            <div>Server root</div><div><input id="envRoot" style="width:100%" placeholder="D:\\Servers\\LSB-Test"></div>
            <div>Enabled</div><div><label><input id="envEnabled" type="checkbox" checked> selectable</label></div>
            <div>Notes</div><div><textarea id="envNotes" rows="3" style="width:100%" placeholder="Optional notes"></textarea></div>
          </div>
          <div class="ce-toolbar" style="margin-top:10px">
            <button type="button" id="envSave">Save</button>
            <button type="button" id="envReset">New profile</button>
            <label><input id="envMakeActive" type="checkbox"> make active after save</label>
          </div>
          <div id="envFormMessage" class="ce-muted" style="margin-top:8px"></div>
        </section>
        <section class="ce-card">
          <div class="ce-toolbar"><strong>Configured environments</strong><span class="sp"></span><button type="button" id="envRefresh">Refresh</button></div>
          <div id="envProfiles" style="margin-top:8px"></div>
          <pre id="envTestResult" class="ce-preview" style="margin-top:10px"></pre>
        </section>
      </div>`;
    document.body.appendChild(dialog);

    document.getElementById('envSave').addEventListener('click', saveProfile);
    document.getElementById('envReset').addEventListener('click', resetForm);
    document.getElementById('envRefresh').addEventListener('click', refreshEnvironments);
  }

  function resetForm() {
    document.getElementById('envProfileId').value = '';
    document.getElementById('envFormTitle').textContent = 'Add environment';
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
      const saved = await envApi(id ? `/profiles/${Number(id)}` : '/profiles', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
      });
      if (id && body.make_active && !saved.is_active) {
        await envApi(`/profiles/${Number(id)}/activate`, {method: 'POST'});
      }
      message.textContent = 'Saved.';
      await refreshEnvironments();
      if (body.make_active) location.reload();
      else populateForm(saved);
    } catch (error) {
      message.textContent = error.message;
    }
  }

  async function activateProfile(id) {
    const profile = environmentState.profiles.find(row => Number(row.profile_id) === Number(id));
    if (!profile) return;
    if (profile.environment === 'live' && !confirm(`Activate LIVE environment "${profile.name}"?\n\nAll profile-aware Server tools will resolve this server root.`)) return;
    try {
      await envApi(`/profiles/${id}/activate`, {method: 'POST'});
      location.reload();
    } catch (error) {
      alert(error.message);
    }
  }

  async function testProfile(id) {
    const output = document.getElementById('envTestResult');
    output.textContent = 'Testing connection…';
    try {
      const result = await envApi(`/profiles/${id}/test`, {method: 'POST'});
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
    const profile = environmentState.profiles.find(row => Number(row.profile_id) === Number(id));
    if (!profile || !confirm(`Delete server environment "${profile.name}"?\n\nThis does not modify the server or its database.`)) return;
    try {
      await envApi(`/profiles/${id}/delete`, {method: 'POST'});
      resetForm();
      await refreshEnvironments();
    } catch (error) {
      alert(error.message);
    }
  }

  function renderManager() {
    const box = document.getElementById('envProfiles');
    if (!box) return;
    box.innerHTML = environmentState.profiles.map(profile => {
      const status = profile.is_active ? '<span class="ce-pill ok">ACTIVE</span>' : '';
      const live = profile.environment === 'live' ? '<span class="ce-pill bad">LIVE</span>' : '';
      const disabled = profile.enabled ? '' : '<span class="ce-pill warn">DISABLED</span>';
      return `<div class="ce-card" style="margin:6px 0">
        <div class="ce-toolbar"><strong>${esc(profile.name)}</strong>${status}${live}${disabled}<span class="sp"></span><span class="ce-muted">${esc(String(profile.family).toUpperCase())}</span></div>
        <div class="mono" style="margin:5px 0">${esc(profile.server_root)}</div>
        <div class="ce-muted">${esc(String(profile.environment).toUpperCase())}${profile.notes ? ' · ' + esc(profile.notes) : ''}</div>
        <div class="ce-toolbar" style="margin-top:7px">
          <button type="button" data-edit="${profile.profile_id}">Edit</button>
          <button type="button" data-test="${profile.profile_id}">Test connection</button>
          <button type="button" data-activate="${profile.profile_id}" ${profile.is_active || !profile.enabled ? 'disabled' : ''}>Activate</button>
          <button type="button" data-delete="${profile.profile_id}" ${profile.is_active ? 'disabled' : ''}>Delete</button>
        </div>
      </div>`;
    }).join('') || '<div class="ce-muted">No named server environments yet. Existing single-server settings remain active until you add one.</div>';

    box.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
      const profile = environmentState.profiles.find(row => Number(row.profile_id) === Number(button.dataset.edit));
      if (profile) populateForm(profile);
    }));
    box.querySelectorAll('[data-test]').forEach(button => button.addEventListener('click', () => testProfile(Number(button.dataset.test))));
    box.querySelectorAll('[data-activate]').forEach(button => button.addEventListener('click', () => activateProfile(Number(button.dataset.activate))));
    box.querySelectorAll('[data-delete]').forEach(button => button.addEventListener('click', () => deleteProfile(Number(button.dataset.delete))));
  }

  async function refreshEnvironments() {
    try {
      environmentState = await envApi('/profiles.json');
      const envSelect = document.getElementById('envEnvironment');
      const familySelect = document.getElementById('envFamily');
      if (envSelect) envSelect.innerHTML = environmentState.environments.map(value => `<option value="${esc(value)}">${esc(value.toUpperCase())}</option>`).join('');
      if (familySelect) familySelect.innerHTML = environmentState.families.map(value => `<option value="${esc(value)}">${esc(value.toUpperCase())}</option>`).join('');
      renderToolbar();
      renderManager();
    } catch (error) {
      const badge = document.getElementById('serverEnvironmentBadge');
      if (badge) {
        badge.textContent = 'PROFILE ERROR';
        badge.className = 'ce-pill bad';
        badge.title = error.message;
      }
    }
  }

  async function openManager() {
    ensureDialog();
    await refreshEnvironments();
    resetForm();
    document.getElementById('serverEnvironmentDialog').showModal();
  }

  installToolbar();
  refreshEnvironments();
})();
