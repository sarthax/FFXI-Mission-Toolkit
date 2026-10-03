(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'merits-jobpoints') renderMeritManager();
  };

  function meritId(row) {
    return Number(row?.meritid ?? row?.merit_id ?? row?.id ?? -1);
  }

  function meritRank(row) {
    return Number(row?.upgrades ?? row?.upgrade ?? row?.rank ?? 0);
  }

  function formatJobs(jobs) {
    return (jobs || []).map(job => String(job).toUpperCase()).join(', ');
  }

  function renderFallback(shell, rows, catalog) {
    const source = catalog?.source || {};
    const note = catalog?.note || catalog?.error || 'No structured merit catalog is available for this checkout.';
    shell.innerHTML = `<div class="ce-progress-head"><strong>Merits</strong>${pill(`${rows.length} allocated rows`)}${pill('catalog unavailable','warn')}</div>
      <div class="warn">${esc(note)}</div>
      <div class="ce-progress-card"><div class="ce-muted">Source: ${esc(source.path || 'not found')}</div><div class="ce-progress-list" style="margin-top:6px">${rows.map(row => `<div class="ce-progress-row ce-readonly-row"><span>Merit ID ${esc(meritId(row))}</span><strong>Rank ${esc(meritRank(row))}</strong></div>`).join('') || '<div class="ce-progress-empty">No allocated merits.</div>'}</div></div>`;
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

    const totalAllocated = rows.reduce((sum, row) => sum + Math.max(0, meritRank(row)), 0);
    shell.innerHTML = `<div class="ce-progress-head"><strong>Merit Categories</strong>${pill(`${categories.length} categories`)}${pill(`${totalAllocated} total upgrades`,'ok')}<span class="ce-progress-source">${esc(catalog.source.kind || 'merits')} · ${esc(catalog.source.path || '')}</span></div>
      <div class="ce-toolbar"><input class="ce-merit-filter" type="search" placeholder="Filter merit, category, job, or ID"><label class="ce-muted"><input class="ce-merit-allocated-only" type="checkbox"> Allocated only</label></div>
      <div class="ce-progress-grid ce-merit-grid"></div>`;

    const filter = shell.querySelector('.ce-merit-filter');
    const allocatedOnly = shell.querySelector('.ce-merit-allocated-only');
    const grid = shell.querySelector('.ce-merit-grid');

    const draw = () => {
      const q = String(filter.value || '').trim().toLowerCase();
      grid.innerHTML = categories.map(category => {
        const meritRows = (category.merits || []).map(merit => {
          const stored = byId.get(Number(merit.id));
          const rank = stored ? meritRank(stored) : 0;
          const max = merit.max_upgrades == null ? null : Number(merit.max_upgrades);
          const costs = merit.costs || [];
          const nextCost = rank >= 0 && rank < costs.length ? costs[rank] : null;
          const effect = Number(merit.value_per_upgrade || 0) * rank;
          const jobs = formatJobs(merit.jobs);
          const haystack = `${category.label} ${merit.label} ${merit.symbol || ''} ${merit.id} ${jobs}`.toLowerCase();
          return {...merit, rank, max, nextCost, effect, jobs, visible:(!allocatedOnly.checked || rank > 0) && (!q || haystack.includes(q))};
        });
        const visible = meritRows.filter(row => row.visible);
        if (!visible.length) return '';
        const allocated = meritRows.reduce((sum, row) => sum + Math.max(0, row.rank), 0);
        const categoryCap = Number(category.max_upgrades || 0);
        const body = visible.map(row => {
          const rankText = row.max == null ? `${row.rank}` : `${row.rank}/${row.max}`;
          const effectText = Number(row.value_per_upgrade || 0) ? `${row.effect} total · +${row.value_per_upgrade}/rank` : 'effect defined by server';
          const next = row.nextCost == null ? (row.max !== null && row.rank >= row.max ? 'MAX' : '—') : `${row.nextCost} merit pts`;
          const jobText = row.jobs ? `<small>Jobs: ${esc(row.jobs)}</small>` : '';
          return `<div class="ce-merit-row"><div class="ce-merit-name"><strong>${esc(row.label)}</strong><small>ID ${esc(row.id)}${row.symbol ? ' · '+esc(row.symbol) : ''}</small>${jobText}</div><div><span class="ce-field-label">Rank</span><strong>${esc(rankText)}</strong></div><div><span class="ce-field-label">Effect</span><span>${esc(effectText)}</span></div><div><span class="ce-field-label">Next cost</span><span>${esc(next)}</span></div></div>`;
        }).join('');
        return `<details class="ce-progress-card ce-merit-category" open><summary><strong>${esc(category.label)}</strong> ${pill(`${allocated}${categoryCap ? '/'+categoryCap : ''} allocated`, allocated ? 'ok' : '')}</summary><div class="ce-merit-rows">${body}</div></details>`;
      }).join('') || '<div class="ce-progress-empty">No merit definitions match this filter.</div>';
    };

    const style = document.createElement('style');
    style.textContent = `.ce-merit-grid{grid-template-columns:repeat(auto-fit,minmax(390px,1fr))}.ce-merit-category>summary{cursor:pointer;padding:2px 0}.ce-merit-rows{margin-top:5px}.ce-merit-row{display:grid;grid-template-columns:minmax(150px,1.4fr) 70px minmax(110px,.8fr) 90px;gap:6px;align-items:center;padding:5px;border-top:1px solid var(--border,#333);font-size:11px}.ce-merit-row small{display:block;opacity:.62}.ce-merit-row .ce-field-label{display:block;font-size:8px;text-transform:uppercase;opacity:.58}@media(max-width:720px){.ce-merit-grid{grid-template-columns:1fr}.ce-merit-row{grid-template-columns:1fr 55px}.ce-merit-row>div:nth-child(n+3){display:none}}`;
    shell.prepend(style);
    filter.addEventListener('input', draw);
    allocatedOnly.addEventListener('change', draw);
    draw();

    const raw = [...box.querySelectorAll(':scope > .ce-data-block')].find(details => /char_merit/.test(details.querySelector(':scope > summary')?.textContent || ''));
    if (raw) {
      raw.open = false;
      raw.querySelector(':scope > summary')?.insertAdjacentHTML('beforeend', ' <span class="ce-muted">· raw rows</span>');
    }
  }
})();
