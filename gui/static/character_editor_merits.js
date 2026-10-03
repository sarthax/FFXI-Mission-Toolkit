(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'merits-jobpoints') renderMeritManager();
  };

  const GENERAL_KEYS = ['hp_mp','start', 'attributes', 'combat', 'magic', 'others', 'ws'];
  const JOB_ORDER = ['war','mnk','whm','blm','rdm','thf','pld','drk','bst','brd','rng','sam','nin','drg','smn','blu','cor','pup','dnc','sch','geo','run'];
  let selectedNav = 'general:start';

  const meritId = row => Number(row?.meritid ?? row?.merit_id ?? row?.id ?? -1);
  const meritRank = row => Number(row?.upgrades ?? row?.upgrade ?? row?.rank ?? 0);
  const formatJobs = jobs => (jobs || []).map(job => String(job).toUpperCase()).join(', ');

  function renderFallback(shell, rows, catalog) {
    const source = catalog?.source || {};
    const note = catalog?.note || catalog?.error || 'No structured merit catalog is available for this checkout.';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Merits</strong>${pill(`${rows.length} allocated rows`)}${pill('catalog unavailable','warn')}</div>
      <div class="warn">${esc(note)}</div>
      <div class="ce-progress-card"><div class="ce-muted">Source: ${esc(source.path || 'not found')}</div><div class="ce-progress-list" style="margin-top:6px">${rows.map(row => `<div class="ce-progress-row ce-readonly-row"><span>Merit ID ${esc(meritId(row))}</span><strong>Rank ${esc(meritRank(row))}</strong></div>`).join('') || '<div class="ce-progress-empty">No allocated merits.</div>'}</div></div>`;
  }

  async function postJson(url, body) {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json().catch(() => ({detail: response.statusText}));
    if (!response.ok) throw new Error(data.detail || response.statusText);
    return data;
  }

  function renderMeritManager() {
    const box = document.getElementById('categoryData');
    if (!box) return;
    box.querySelectorAll(':scope > .ce-merit-manager').forEach(node => node.remove());

    const rows = activeCategoryData?.tables?.char_merit || [];
    const byId = new Map(rows.map(row => [meritId(row), row]));
    const catalog = activeCategoryData?.catalogs?.merits || {};
    const categories = catalog.categories || [];
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-merit-manager';
    box.prepend(shell);

    if (!catalog?.source?.available || !categories.length) {
      renderFallback(shell, rows, catalog);
      return;
    }

    const offline = editableOnline();
    const byKey = new Map(categories.map(c => [c.key, c]));
    const pending = new Map(); // merit id -> new rank
    const rankOf = merit => pending.has(Number(merit.id)) ? pending.get(Number(merit.id)) : (byId.has(Number(merit.id)) ? meritRank(byId.get(Number(merit.id))) : 0);
    const storedRank = merit => byId.has(Number(merit.id)) ? meritRank(byId.get(Number(merit.id))) : 0;
    const allocatedIn = cats => cats.reduce((sum, c) => sum + (c.merits || []).reduce((s, m) => s + Math.max(0, storedRank(m)), 0), 0);

    const general = GENERAL_KEYS.map(k => byKey.get(k)).filter(Boolean);
    const jobs = JOB_ORDER.map(job => ({job, cats: [byKey.get(`${job}_1`), byKey.get(`${job}_2`)].filter(c => c && (c.merits || []).length)})).filter(j => j.cats.length);
    const totalAllocated = allocatedIn(categories);

    shell.innerHTML = `<div class="ce-progress-head"><strong>Merits</strong>${pill(`${totalAllocated} total upgrades`,'ok')}<span class="ce-progress-source">${esc(catalog.source.kind || 'merits')} · ${esc(catalog.source.path || '')}</span></div>
      <div class="ce-merit-layout"><nav class="ce-merit-nav"></nav><section class="ce-merit-detail"></section></div>`;
    const nav = shell.querySelector('.ce-merit-nav');
    const detail = shell.querySelector('.ce-merit-detail');

    const navItem = (id, label, allocated) => `<button type="button" class="ce-merit-nav-item ${id === selectedNav ? 'active' : ''}" data-nav="${esc(id)}"><span>${esc(label)}</span>${allocated ? `<em>${allocated}</em>` : ''}</button>`;
    const drawNav = () => {
      nav.innerHTML = `<div class="ce-merit-nav-title">All jobs</div>${general.map(c => navItem('general:' + c.key, c.label, allocatedIn([c]))).join('')}
        <div class="ce-merit-nav-title">Jobs</div>${jobs.map(j => navItem('job:' + j.job, j.job.toUpperCase(), allocatedIn(j.cats))).join('')}`;
      nav.querySelectorAll('[data-nav]').forEach(btn => btn.addEventListener('click', () => { selectedNav = btn.dataset.nav; drawNav(); drawDetail(); }));
    };

    const meritRow = merit => {
      const rank = rankOf(merit), stored = storedRank(merit);
      const max = merit.max_upgrades == null ? null : Number(merit.max_upgrades);
      const costs = merit.costs || [];
      const nextCost = rank < costs.length ? costs[rank] : null;
      const effect = Number(merit.value_per_upgrade || 0) * rank;
      const effectText = Number(merit.value_per_upgrade || 0) ? `${effect} total · +${merit.value_per_upgrade}/rank` : 'effect defined by server';
      const next = nextCost == null ? (max !== null && rank >= max ? 'MAX' : '—') : `${nextCost} pts`;
      const jobText = (merit.jobs || []).length ? `<small>Jobs: ${esc(formatJobs(merit.jobs))}</small>` : '';
      const changed = rank !== stored;
      return `<div class="ce-merit-row ${changed ? 'ce-merit-changed' : ''}" data-merit="${esc(merit.id)}">
        <div class="ce-merit-name"><strong>${esc(merit.label)}</strong><small>ID ${esc(merit.id)}${merit.symbol ? ' · ' + esc(merit.symbol) : ''}</small>${jobText}</div>
        <div class="ce-merit-rank"><span class="ce-field-label">Rank${max != null ? ' / ' + max : ''}</span>
          <div class="ce-merit-stepper"><button type="button" data-step="-1" ${offline && rank > 0 ? '' : 'disabled'}>−</button><input type="number" min="0" ${max != null ? `max="${max}"` : ''} value="${rank}" ${offline ? '' : 'disabled'}><button type="button" data-step="1" ${offline && (max == null || rank < max) ? '' : 'disabled'}>+</button></div></div>
        <div><span class="ce-field-label">Effect</span><span>${esc(effectText)}</span></div>
        <div><span class="ce-field-label">Next cost</span><span>${esc(next)}</span></div></div>`;
    };

    const drawDetail = () => {
      let sections = [];
      let title = '';
      if (selectedNav.startsWith('job:')) {
        const job = jobs.find(j => `job:${j.job}` === selectedNav) || jobs[0];
        title = `${job.job.toUpperCase()} — Group 1 and Group 2`;
        sections = job.cats.map(c => ({label: c.label, cat: c}));
      } else {
        const cat = general.find(c => `general:${c.key}` === selectedNav) || general[0];
        title = cat?.label || 'Merits';
        sections = cat ? [{label: cat.label, cat}] : [];
      }
      const changedCount = pending.size;
      detail.innerHTML = `<div class="ce-merit-detail-head"><h3>${esc(title)}</h3>${offline ? '' : pill('character must be offline to edit', 'warn')}<span class="sp"></span>
          <span class="ce-merit-pending">${changedCount ? `${changedCount} unsaved merit change${changedCount === 1 ? '' : 's'}` : ''}</span>
          <button type="button" class="ce-merit-reset" ${changedCount ? '' : 'disabled'}>Discard</button>
          <button type="button" class="ce-merit-apply" ${offline && changedCount ? '' : 'disabled'}>Apply merit changes</button></div>
        ${sections.map(({label, cat}) => {
          const allocated = (cat.merits || []).reduce((s, m) => s + Math.max(0, rankOf(m)), 0);
          return `<div class="ce-progress-card ce-merit-category"><div class="ce-merit-cat-head"><strong>${esc(label)}</strong>${pill(`${allocated}${cat.max_upgrades ? '/' + cat.max_upgrades : ''} allocated`, allocated ? 'ok' : '')}</div>
            <div class="ce-merit-rows">${(cat.merits || []).map(meritRow).join('')}</div></div>`;
        }).join('') || '<div class="ce-progress-empty">No merits in this group.</div>'}`;

      const merits = new Map(categories.flatMap(c => c.merits || []).map(m => [Number(m.id), m]));
      detail.querySelectorAll('.ce-merit-row').forEach(rowEl => {
        const id = Number(rowEl.dataset.merit), merit = merits.get(id);
        const setRank = value => {
          const max = merit.max_upgrades == null ? Infinity : Number(merit.max_upgrades);
          const rank = Math.max(0, Math.min(max, Math.floor(Number(value) || 0)));
          if (rank === storedRank(merit)) pending.delete(id); else pending.set(id, rank);
          drawDetail();
        };
        rowEl.querySelector('input').addEventListener('change', e => setRank(e.target.value));
        rowEl.querySelectorAll('[data-step]').forEach(btn => btn.addEventListener('click', () => setRank(rankOf(merit) + Number(btn.dataset.step))));
      });
      detail.querySelector('.ce-merit-reset')?.addEventListener('click', () => { pending.clear(); drawDetail(); });
      detail.querySelector('.ce-merit-apply')?.addEventListener('click', async event => {
        const button = event.currentTarget;
        const summary = [...pending].map(([id, rank]) => `${merits.get(id)?.label || id} (${id}): ${storedRank(merits.get(id))} → ${rank}`).join('\n');
        if (!confirm(`Apply ${pending.size} merit change(s)?\n\n${summary}\n\nThe character must stay offline.`)) return;
        button.disabled = true;
        try {
          const base = `/character-editor/characters/${selectedChar}/fields`;
          for (const [id, rank] of pending) {
            const body = {table: 'char_merit', selector: {meritid: id}, changes: {upgrades: rank}};
            const preview = await postJson(`${base}/preview`, body);
            if (!preview.ready) throw new Error((preview.issues || []).map(i => i.message).join('; ') || `Merit ${id} is not write-ready`);
            await postJson(`${base}/apply`, {...body, expected_before: preview.before, approved: true});
          }
          pending.clear();
          await selectCharacter(selectedChar);
        } catch (e) {
          alert(`Merit apply stopped: ${e.message}\nSome earlier changes may already be saved; reloading.`);
          await selectCharacter(selectedChar);
        }
      });
    };

    const style = document.createElement('style');
    style.textContent = `.ce-merit-layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:10px;align-items:start}
      .ce-merit-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px;max-height:75vh;overflow:auto}
      .ce-merit-nav-title{font-size:9px;text-transform:uppercase;letter-spacing:.06em;opacity:.55;margin:8px 0 2px}
      .ce-merit-nav-item{display:flex;justify-content:space-between;align-items:center;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-merit-nav-item:hover{background:rgba(255,255,255,.06)}.ce-merit-nav-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1);font-weight:700}
      .ce-merit-nav-item em{font-style:normal;font-size:10px;padding:0 6px;border-radius:8px;background:#1e7e34}
      .ce-merit-detail-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}.ce-merit-detail-head h3{margin:0}
      .ce-merit-category{margin-bottom:8px}.ce-merit-cat-head{display:flex;gap:8px;align-items:center;margin-bottom:4px}
      .ce-merit-row{display:grid;grid-template-columns:minmax(150px,1.4fr) 150px minmax(110px,.8fr) 80px;gap:6px;align-items:center;padding:5px;border-top:1px solid var(--border,#333);font-size:11px}
      .ce-merit-row small{display:block;opacity:.62}.ce-merit-row .ce-field-label{display:block;font-size:8px;text-transform:uppercase;opacity:.58}
      .ce-merit-changed{background:rgba(138,101,0,.18);outline:1px solid #8a6500}
      .ce-merit-stepper{display:flex;gap:3px;align-items:center}.ce-merit-stepper input{width:54px;min-width:0;padding:2px 4px}.ce-merit-stepper button{padding:1px 8px}
      @media(max-width:760px){.ce-merit-layout{grid-template-columns:1fr}.ce-merit-nav{position:static;flex-direction:row;flex-wrap:wrap;max-height:none}.ce-merit-row{grid-template-columns:1fr 150px}.ce-merit-row>div:nth-child(n+3){display:none}}`;
    shell.prepend(style);
    if (!selectedNav || (!selectedNav.startsWith('job:') && !general.some(c => `general:${c.key}` === selectedNav))) selectedNav = general.length ? `general:${general[0].key}` : `job:${jobs[0]?.job}`;
    drawNav();
    drawDetail();

    const raw = [...box.querySelectorAll(':scope > .ce-data-block')].find(details => /char_merit/.test(details.querySelector(':scope > summary')?.textContent || ''));
    if (raw) {
      raw.open = false;
      raw.querySelector(':scope > summary')?.insertAdjacentHTML('beforeend', ' <span class="ce-muted">· raw rows</span>');
    }
  }
})();
