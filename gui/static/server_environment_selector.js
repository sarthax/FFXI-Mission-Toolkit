(() => {
  const TARGET_PATHS = new Set(['/zoneplot2', '/itemedit']);

  function label(profile) {
    const env = String(profile.environment || 'other').toUpperCase();
    const family = String(profile.family || 'auto').toUpperCase();
    return `${profile.name} — ${env} / ${family}`;
  }

  function badgeText(profile) {
    if (!profile) return 'LEGACY';
    return String(profile.environment || 'other').toUpperCase();
  }

  function installBadge(select, active) {
    let badge = document.getElementById('sharedServerEnvironmentBadge');
    if (!badge) {
      badge = document.createElement('span');
      badge.id = 'sharedServerEnvironmentBadge';
      badge.className = 'chip mono';
      const labelEl = select.closest('label');
      if (labelEl) labelEl.insertAdjacentElement('afterend', badge);
      else select.insertAdjacentElement('afterend', badge);
    }
    badge.textContent = badgeText(active);
    badge.title = active
      ? `${active.name}\n${active.server_root}`
      : 'Legacy single-server settings are active';
    badge.style.borderColor = active?.environment === 'live' ? 'var(--red)' : 'var(--border)';
    badge.style.color = active?.environment === 'live' ? 'var(--red)' : '';
  }

  function installManageLink(select) {
    if (document.getElementById('sharedServerEnvironmentManage')) return;
    const link = document.createElement('a');
    link.id = 'sharedServerEnvironmentManage';
    link.href = '/character-editor';
    link.className = 'chip';
    link.textContent = 'Manage environments';
    link.title = 'Open Character Editor environment manager';
    const labelEl = select.closest('label');
    if (labelEl) labelEl.insertAdjacentElement('afterend', link);
    else select.insertAdjacentElement('afterend', link);
  }

  async function install() {
    if (!TARGET_PATHS.has(location.pathname)) return;
    const select = document.getElementById('srv');
    if (!select) return;

    let state;
    try {
      const response = await fetch('/character-editor/environments/profiles.json');
      if (!response.ok) return;
      state = await response.json();
    } catch (error) {
      console.warn('server environment profiles unavailable', error);
      return;
    }

    const profiles = (state.profiles || []).filter(profile => profile.enabled);
    if (!profiles.length) {
      installBadge(select, null);
      installManageLink(select);
      return;
    }

    const active = state.active || null;
    const previousValue = active ? `profile:${active.profile_id}` : '';
    select.innerHTML = [
      ...(active ? [] : ['<option value="">Select environment…</option>']),
      ...profiles.map(profile => {
        const value = `profile:${Number(profile.profile_id)}`;
        const selected = active && Number(active.profile_id) === Number(profile.profile_id) ? ' selected' : '';
        return `<option value="${value}"${selected}>${label(profile)}</option>`;
      }),
    ].join('');
    if (previousValue) select.value = previousValue;
    select.title = 'Named server environment. Changing this also changes the active environment used by Server tools.';

    installBadge(select, active);
    installManageLink(select);

    select.addEventListener('change', event => {
      const raw = select.value;
      if (!raw.startsWith('profile:')) return;
      const id = Number(raw.slice('profile:'.length));
      const profile = profiles.find(row => Number(row.profile_id) === id);
      if (!profile) return;

      if (profile.environment === 'live') {
        const ok = confirm(
          `Switch active server environment to LIVE profile "${profile.name}"?\n\n` +
          'Edits and live database operations on this page will target that environment.'
        );
        if (!ok) {
          event.preventDefault();
          event.stopImmediatePropagation();
          select.value = previousValue;
          return;
        }
      }
    }, true);
  }

  window.addEventListener('load', install, {once: true});
})();
