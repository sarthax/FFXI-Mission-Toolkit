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
    link.href = '/settings#server-environments';
    link.className = 'chip';
    link.textContent = 'Manage environments';
    link.title = 'Open Settings server environment manager';
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
        <a class="chip" href="/settings#server-environments">Manage environments</a>
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
    // 2D plot handoffs. Keep Paths as an additional workflow, but restore the direct plot pages:
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

// Shared application-shell navigation behavior. The server-rendered shell remains the source of
// truth for section labels and routes: category menus are loaded from the category's own rendered
// page on demand rather than duplicating WORKSPACES in JavaScript.
(() => {
  const cache = new Map();
  let categoryPopover = null;
  let categoryOwner = null;
  let sectionBar = null;

  function installStyles() {
    if (document.getElementById('shellNavigationEnhancementStyles')) return;
    const style = document.createElement('style');
    style.id = 'shellNavigationEnhancementStyles';
    style.textContent = `
      #shellWorkspacePopover{position:fixed;z-index:220;min-width:260px;max-width:min(520px,92vw);max-height:70vh;overflow:auto}
      #shellWorkspacePopover[hidden]{display:none}
      #shellSectionBar{flex:none;background:var(--surface);border-bottom:1px solid var(--border);padding:5px 8px;max-height:180px;overflow:auto;z-index:70}
      #shellSectionBar[hidden]{display:none}
      #shellSectionBar .shell-section-strip{display:flex;align-items:flex-start;gap:5px;overflow-x:auto;scrollbar-width:thin}
      #shellSectionBar .section-link{flex:none;padding:4px 7px;border:1px solid transparent}
      #shellSectionBar .section-link:hover,#shellSectionBar .section-link.active{border-color:var(--border)}
      #shellSectionBar .shell-group{display:flex;align-items:center;gap:3px;flex:none;margin:0;padding:0 6px 0 0;border-right:1px solid var(--border)}
      #shellSectionBar .shell-group-title{padding:4px 3px;white-space:nowrap}
      #shellSectionBar .shell-group+.shell-group{margin:0;padding-top:0}
      @media(max-width:1180px){#shellSectionBar{display:none!important}}
    `;
    document.head.appendChild(style);
  }

  function closeCategoryPopover() {
    if (categoryPopover) categoryPopover.hidden = true;
    if (categoryOwner) categoryOwner.setAttribute('aria-expanded', 'false');
    categoryOwner = null;
  }

  function ensureCategoryPopover() {
    if (categoryPopover) return categoryPopover;
    categoryPopover = document.createElement('div');
    categoryPopover.id = 'shellWorkspacePopover';
    categoryPopover.className = 'shell-popover';
    categoryPopover.hidden = true;
    categoryPopover.setAttribute('role', 'menu');
    document.body.appendChild(categoryPopover);
    return categoryPopover;
  }

  function positionCategoryPopover(link) {
    const rect = link.getBoundingClientRect();
    const popover = ensureCategoryPopover();
    popover.style.top = `${Math.round(rect.bottom + 7)}px`;
    const maxLeft = Math.max(8, window.innerWidth - Math.min(520, popover.offsetWidth || 320) - 8);
    popover.style.left = `${Math.min(Math.round(rect.left), maxLeft)}px`;
  }

  function currentSectionMarkup() {
    return document.querySelector('#app-shell details.section-menu .shell-popover')?.innerHTML || '';
  }

  async function menuMarkup(link) {
    const href = link.getAttribute('href');
    if (link.classList.contains('active')) return currentSectionMarkup();
    if (cache.has(href)) return cache.get(href);
    const response = await fetch(href, {headers: {'X-Mission-Toolkit-Shell': 'sections'}});
    if (!response.ok) throw new Error(`Unable to load navigation (${response.status})`);
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const markup = doc.querySelector('#app-shell details.section-menu .shell-popover')?.innerHTML || '';
    cache.set(href, markup);
    return markup;
  }

  async function openCategoryMenu(link) {
    const popover = ensureCategoryPopover();
    if (categoryOwner === link && !popover.hidden) {
      closeCategoryPopover();
      return;
    }
    closeCategoryPopover();
    categoryOwner = link;
    link.setAttribute('aria-haspopup', 'menu');
    link.setAttribute('aria-expanded', 'true');
    popover.hidden = false;
    popover.innerHTML = '<div class="muted" style="padding:6px 7px">Loading sections…</div>';
    positionCategoryPopover(link);
    try {
      const markup = await menuMarkup(link);
      const overview = `<a class="section-link" href="${link.href}">Open ${link.textContent.trim()} overview</a>`;
      popover.innerHTML = overview + (markup ? `<div class="shell-group" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--border)">${markup}</div>` : '');
      positionCategoryPopover(link);
    } catch (error) {
      popover.innerHTML = `<div class="muted" style="padding:6px 7px">${String(error.message || error)}</div><a class="section-link" href="${link.href}">Open ${link.textContent.trim()}</a>`;
      positionCategoryPopover(link);
    }
  }

  function ensureSectionBar() {
    if (sectionBar) return sectionBar;
    sectionBar = document.createElement('div');
    sectionBar.id = 'shellSectionBar';
    sectionBar.hidden = true;
    sectionBar.setAttribute('aria-label', 'Current workspace sections');
    const strip = document.createElement('div');
    strip.className = 'shell-section-strip';
    strip.innerHTML = currentSectionMarkup();
    sectionBar.appendChild(strip);
    document.getElementById('app-shell')?.insertAdjacentElement('afterend', sectionBar);
    return sectionBar;
  }

  function setSectionBarExpanded(expanded) {
    const bar = ensureSectionBar();
    const summary = document.querySelector('#app-shell details.section-menu > summary');
    bar.hidden = !expanded;
    if (summary) summary.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    sessionStorage.setItem('shellSectionsExpanded', expanded ? '1' : '0');
  }

  function installSectionToggle() {
    const details = document.querySelector('#app-shell details.section-menu');
    const summary = details?.querySelector(':scope > summary');
    if (!details || !summary) return;
    details.open = false;
    summary.setAttribute('role', 'button');
    summary.setAttribute('aria-controls', 'shellSectionBar');
    summary.setAttribute('aria-expanded', 'false');
    summary.addEventListener('click', event => {
      event.preventDefault();
      details.open = false;
      closeCategoryPopover();
      setSectionBarExpanded(ensureSectionBar().hidden);
    });
    summary.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      summary.click();
    });
    if (sessionStorage.getItem('shellSectionsExpanded') === '1') setSectionBarExpanded(true);
  }

  function installCategoryMenus() {
    const links = [...document.querySelectorAll('#app-shell .shell-workspaces a.workspace-link')];
    for (const link of links) {
      link.setAttribute('aria-haspopup', 'menu');
      link.setAttribute('aria-expanded', 'false');
      link.addEventListener('click', event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        openCategoryMenu(link);
      });
    }
  }

  function installShellNavigation() {
    if (!document.getElementById('app-shell')) return;
    installStyles();
    installCategoryMenus();
    installSectionToggle();
    document.addEventListener('click', event => {
      if (categoryPopover?.hidden !== false) return;
      if (categoryPopover.contains(event.target) || categoryOwner?.contains(event.target)) return;
      closeCategoryPopover();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeCategoryPopover();
    });
    window.addEventListener('resize', () => {
      if (categoryOwner && categoryPopover?.hidden === false) positionCategoryPopover(categoryOwner);
    });
    window.addEventListener('scroll', closeCategoryPopover, true);
  }

  window.addEventListener('DOMContentLoaded', installShellNavigation, {once: true});
})();
