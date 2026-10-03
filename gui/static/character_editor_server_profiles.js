(() => {
  if (!document.querySelector('.character-editor-page')) return;

  const API_ROOT = '/character-editor/environments';

  async function loadEnvironment() {
    const response = await fetch(API_ROOT + '/profiles.json');
    const payload = await response.json().catch(() => ({detail: response.statusText}));
    if (!response.ok) throw new Error(payload.detail || response.statusText);
    return payload;
  }

  function installToolbar() {
    const toolbar = document.querySelector('.character-editor-page .dense-toolbar');
    if (!toolbar || document.getElementById('serverEnvironmentBadge')) return;

    const badge = document.createElement('span');
    badge.id = 'serverEnvironmentBadge';
    badge.className = 'ce-pill warn';
    badge.textContent = 'ENVIRONMENT…';

    const settingsLink = document.createElement('a');
    settingsLink.id = 'serverEnvironmentSettingsLink';
    settingsLink.className = 'chip';
    settingsLink.href = '/settings#server-environments';
    settingsLink.textContent = 'Server settings';
    settingsLink.title = 'Manage shared server environments in Settings';

    const spacer = toolbar.querySelector('.sp');
    toolbar.insertBefore(badge, spacer || null);
    toolbar.insertBefore(settingsLink, spacer || null);
  }

  function render(state) {
    const badge = document.getElementById('serverEnvironmentBadge');
    if (!badge) return;
    const active = state.active;
    if (!active) {
      badge.textContent = 'LEGACY SERVER';
      badge.className = 'ce-pill warn';
      badge.title = 'No named server environment is active. Manage shared server environments in Settings.';
      return;
    }

    const environment = String(active.environment || 'other').toUpperCase();
    const family = String(active.family || 'auto').toUpperCase();
    badge.textContent = `${active.name} · ${environment} / ${family}`;
    badge.className = 'ce-pill ' + (active.environment === 'live' ? 'bad' : 'ok');
    badge.title = `${active.server_root || ''}\nManaged in Settings`;
  }

  installToolbar();
  loadEnvironment().then(render).catch(error => {
    const badge = document.getElementById('serverEnvironmentBadge');
    if (!badge) return;
    badge.textContent = 'PROFILE ERROR';
    badge.className = 'ce-pill bad';
    badge.title = error.message;
  });
})();
