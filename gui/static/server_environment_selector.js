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

  function installShellContext(state) {
    const contextList = document.querySelector('#app-shell .context-list');
    if (!contextList || document.getElementById('shellServerEnvironmentContext')) return;
    const active = state.active || null;
    const item = document.createElement('span');
    item.id = 'shellServerEnvironmentContext';
    item.className = 'context-item' + (active ? '' : ' unknown');
    item.title = active
      ? `${active.server_root}\nProfile ${active.profile_id}`
      : 'No named server environment is active; legacy path settings are being used.';
    item.innerHTML = `
      <span class="context-label">Server environment</span>
      <span class="context-value">${active ? label(active) : 'LEGACY / Not selected'}</span>`;
    contextList.prepend(item);
  }

  function decorateSettings(state) {
    if (location.pathname !== '/settings' || document.getElementById('serverEnvironmentSettingsCard')) return;
    const form = document.getElementById('settings-form');
    if (!form) return;
    const pathsHeading = [...form.querySelectorAll('h2')].find(h => h.textContent.trim() === 'Paths');
    if (!pathsHeading) return;

    const active = state.active || null;
    const enabledCount = (state.profiles || []).filter(profile => profile.enabled).length;
    const card = document.createElement('div');
    card.id = 'serverEnvironmentSettingsCard';
    card.className = 'table-wrap';
    card.style.cssText = 'padding:14px;margin:10px 0 16px;border-left:4px solid var(--accent);';
    card.innerHTML = `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <strong>Server environments</strong>
        <span class="chip mono">${active ? label(active) : 'No named environment active'}</span>
        <a class="chip" href="/character-editor">Manage environments</a>
      </div>
      <p class="muted" style="margin:8px 0 0">
        ${enabledCount} enabled profile${enabledCount === 1 ? '' : 's'}. Named environments are the primary live/admin target for Character Editor, Zone Editor, Item Editor, Entity tools, and other server-aware workflows. The Topaz/DSP path fields below remain only for legacy bootstrap, fallback, and lineage-specific comparison/index tools.
      </p>`;
    pathsHeading.insertAdjacentElement('beforebegin', card);

    const legacyLabels = [
      ['topaz_server_path', 'Legacy Topaz compatibility root — bootstrap/fallback and Topaz-specific reference tools'],
      ['dsp_server_path', 'Legacy DSP compatibility root — bootstrap/fallback and DSP-specific reference tools'],
    ];
    for (const [name, text] of legacyLabels) {
      const input = form.querySelector(`[name="${name}"]`);
      const labelEl = input?.parentElement?.querySelector('label');
      if (labelEl) labelEl.textContent = text;
    }

    const pathsNote = pathsHeading.nextElementSibling;
    if (pathsNote?.classList.contains('muted')) {
      pathsNote.innerHTML = 'Named Server Environments are now authoritative for live/admin tools. These path fields are retained for client/reference paths plus legacy server compatibility; changing a legacy server path does <strong>not</strong> switch the active named environment.';
    }
  }

  function repairCapturePlotHandoffs() {
    const match = location.pathname.match(/^\/captures\/(\d+)$/);
    if (!match) return;
    const captureId = Number(match[1]);
    if (!Number.isInteger(captureId) || captureId <= 0) return;

    // PR #420 added the Zone Editor Paths deep-link by replacing the established standalone
    // 2D plot handoffs.  Keep Paths as an additional workflow, but restore the direct plot pages:
    // those pages are also the supported gateway to the standalone 3D path viewer.
    document.querySelectorAll('a[href^="/zoneplot/from_capture?"]').forEach(link => {
      const url = new URL(link.getAttribute('href'), location.origin);
      const entityId = url.searchParams.get('entity_id');
      const pc = url.searchParams.get('pc');
      const zoneDb = url.searchParams.get('zone_db');

      if (entityId) {
        const editor = link.cloneNode(true);
        editor.textContent = 'editor';
        editor.title = 'Open this trace in the Zone Editor Paths tab';
        editor.classList.add('muted');
        link.insertAdjacentText('afterend', ' · ');
        link.nextSibling.insertAdjacentElement?.('afterend', editor);
        if (!editor.isConnected) link.parentNode?.append(' · ', editor);
        link.href = `/captures/plot?capture_id=${captureId}&entity_id=${encodeURIComponent(entityId)}`;
        link.textContent = '2D / 3D plot';
        link.title = 'Open standalone 2D plot; use its 3D view button for the zone viewer';
        return;
      }

      if (pc === '1' && zoneDb) {
        const editor = link.cloneNode(true);
        editor.textContent = 'Zone Editor';
        editor.title = 'Open this PC trace in the Zone Editor Paths tab';
        link.insertAdjacentElement('afterend', editor);
        link.insertAdjacentText('afterend', ' · ');
        link.href = `/captures/plot?capture_id=${captureId}&pc=1&zone_db=${encodeURIComponent(zoneDb)}`;
        link.title = 'Open standalone 2D plot; use its 3D view button for the zone viewer';
        return;
      }

      // The capture-wide Paths action remains a Zone Editor action, but label it explicitly so it
      // is no longer confused with the standalone 2D/3D plot controls beside it.
      if (!entityId && pc !== '1') {
        link.textContent = 'Zone Editor Paths';
        link.title = 'Open all PathLog traces in the Zone Editor Paths tab';
      }
    });
  }

  async function loadState() {
    try {
      const response = await fetch('/character-editor/environments/profiles.json');
      if (!response.ok) return null;
      return await response.json();
    } catch (error) {
      console.warn('server environment profiles unavailable', error);
      return null;
    }
  }

  async function install() {
    // Plot/viewer link repair is independent of server-profile availability and must continue to
    // work even if Character Editor profile discovery is unavailable.
    repairCapturePlotHandoffs();

    const state = await loadState();
    if (!state) return;

    installShellContext(state);
    decorateSettings(state);

    if (!TARGET_PATHS.has(location.pathname)) return;
    const select = document.getElementById('srv');
    if (!select) return;

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
