(() => {
  const root = document.getElementById('ahAdmin');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat();
  const money = (v) => v == null ? '—' : `${fmt.format(Number(v))}g`;
  const pct = (v) => v == null ? '—' : `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(1)}%`;
  const when = (v) => v ? new Date(v).toLocaleString() : '—';
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let lastActionPreview = null;

  async function api(url) {
    const response = await fetch(url, {headers:{Accept:'application/json'}});
    let payload = null;
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
    return payload;
  }

  async function postApi(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {'Accept':'application/json','Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    let payload = null;
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload?.detail || `${response.status} ${response.statusText}`);
    return payload;
  }

  async function loadStatus() {
    const data = await api('/auction-house/status.json');
    const db = data.database || {};
    const ah = data.auction_house || {};
    $('ahStatus').innerHTML = `<strong>${esc(db.database || 'database')}</strong> · ${esc(ah.family_hint || 'unknown schema')} · ${esc(db.host || '')}<br><small>${esc(db.server_root || '')}</small>`;
  }

  async function loadWriteReadiness() {
    const box = $('ahWriteReadiness');
    try {
      const data = await api('/auction-house/write-readiness.json');
      const notes = (data.notes || []).map(note => `<li>${esc(note)}</li>`).join('');
      const card = (label, ready) => `<div class="ah-readiness-card"><strong>${esc(label)}</strong><br><span>${ready ? 'Prerequisites present' : 'Prerequisites missing'}</span></div>`;
      box.innerHTML = `<div><strong>Database:</strong> ${esc(data.database || 'unknown')} · <strong>Executor:</strong> disabled</div>
        <div class="ah-readiness-grid">${card('LSB listing contract', !!data.lsb_listing_ready)}${card('LSB purchase / cleanup contract', !!data.lsb_purchase_ready)}</div>
        ${notes ? `<ul>${notes}</ul>` : ''}`;
    } catch (error) {
      box.innerHTML = `<p>${esc(error.message)}</p>`;
    }
  }

  async function loadOverview() {
    const data = await api('/auction-house/overview.json?days=30');
    const values = [fmt.format(data.active_listings || 0), fmt.format(data.sales || 0), money(data.gil_transacted), `${fmt.format(data.unique_buyers || 0)} / ${fmt.format(data.unique_sellers || 0)}`];
    document.querySelectorAll('#ahMetrics .metric strong').forEach((node, i) => node.textContent = values[i]);
  }

  function renderHealthList(rows, renderer, emptyText) {
    if (!(rows || []).length) return `<p class="muted">${esc(emptyText)}</p>`;
    return `<ul class="ah-health-list">${rows.slice(0, 8).map(renderer).join('')}</ul>${rows.length > 8 ? `<p class="muted">Showing 8 of ${fmt.format(rows.length)} signals.</p>` : ''}`;
  }

  function renderHealth(data) {
    const counts = data.counts || {};
    $('ahHealthSummary').innerHTML = `
      <div class="metric"><span>Stale listings</span><strong>${fmt.format(counts.stale_listings || 0)}</strong></div>
      <div class="metric"><span>Market movements</span><strong>${fmt.format(counts.market_movements || 0)}</strong></div>
      <div class="metric"><span>Transaction outliers</span><strong>${fmt.format(counts.transaction_outliers || 0)}</strong></div>`;

    $('ahHealthStale').innerHTML = renderHealthList(data.stale_listings || [], row =>
      `<li><strong>${esc(row.item_name)}</strong> · ${esc(row.lot_type)} · ${Number(row.age_days || 0).toFixed(1)}d old · ${money(row.asking_price)}<br><small>${esc(row.seller_name || `seller #${row.seller_id}`)} · ${esc(row.category_path || '')}</small></li>`,
      'No stale listings at this threshold.'
    );

    $('ahHealthMovement').innerHTML = renderHealthList(data.market_movements || [], row =>
      `<li><strong>${esc(row.item_name)}</strong> · ${esc(row.lot_type)} · price ${pct(row.price_change_pct)} · volume ${pct(row.volume_change_pct)}<br><small>${fmt.format(row.recent_sales)} recent vs ${fmt.format(row.baseline_sales)} baseline sales</small></li>`,
      'No price/volume movements met the sample thresholds.'
    );

    const concentration = data.participant_concentration || {};
    const sellerTop = (concentration.sellers || [])[0];
    const buyerTop = (concentration.buyers || [])[0];
    const concentrationParts = [];
    if (sellerTop) concentrationParts.push(`<li><strong>Top seller:</strong> ${esc(sellerTop.name || `#${sellerTop.id}`)} · ${pct(sellerTop.gil_share_pct)} of ranked gil · ${fmt.format(sellerTop.sales)} sales</li>`);
    if (buyerTop) concentrationParts.push(`<li><strong>Top buyer:</strong> ${esc(buyerTop.name || `#${buyerTop.id}`)} · ${pct(buyerTop.gil_share_pct)} of ranked gil · ${fmt.format(buyerTop.sales)} sales</li>`);
    if (!concentration.buyer_identity_available) concentrationParts.push('<li class="muted">Buyer identity is unavailable in this schema.</li>');
    $('ahHealthConcentration').innerHTML = concentrationParts.length ? `<ul class="ah-health-list">${concentrationParts.join('')}</ul>` : '<p class="muted">No completed-sale concentration data.</p>';

    $('ahHealthOutliers').innerHTML = renderHealthList(data.transaction_outliers || [], row =>
      `<li><strong>${esc(row.item_name)}</strong> · ${esc(row.signal.replaceAll('_',' '))} · ${money(row.sale_price)} vs median ${money(row.peer_median_price)}<br><small>${Number(row.severity_ratio || 0).toFixed(2)}× median distance · ${fmt.format(row.peer_sales)} peer sales</small></li>`,
      'No transaction outliers met the current threshold.'
    );

    if (data.disclaimer) $('ahHealthDisclaimer').textContent = data.disclaimer;
  }

  async function loadHealth() {
    const days = Number($('ahHealthDays').value || 30);
    const staleDays = Number($('ahStaleDays').value || 30);
    const summary = $('ahHealthSummary');
    summary.innerHTML = '<p class="muted">Loading economy-health diagnostics…</p>';
    try {
      const qs = new URLSearchParams({days:String(days), stale_days:String(staleDays), recent_days:'7', baseline_days:'30'});
      renderHealth(await api(`/auction-house/health.json?${qs}`));
    } catch (error) {
      summary.innerHTML = `<p>${esc(error.message)}</p>`;
      $('ahHealthStale').innerHTML = '';
      $('ahHealthMovement').innerHTML = '';
      $('ahHealthConcentration').innerHTML = '';
      $('ahHealthOutliers').innerHTML = '';
    }
  }

  async function loadCategories() {
    const data = await api('/auction-house/categories.json');
    const select = $('ahCategory');
    const groups = new Map();
    for (const row of data.rows || []) {
      const groupName = row.group || 'Custom / Unknown';
      if (!groups.has(groupName)) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        groups.set(groupName, optgroup);
        select.appendChild(optgroup);
      }
      const option = document.createElement('option');
      option.value = row.category_id;
      option.textContent = `${row.path || row.label || `Category ${row.category_id}`} (${fmt.format(row.item_count)})`;
      groups.get(groupName).appendChild(option);
    }
  }

  async function loadItems() {
    const qs = new URLSearchParams();
    const term = $('ahSearch').value.trim();
    const category = $('ahCategory').value;
    if (term) qs.set('q', term);
    if (category) qs.set('category_id', category);
    qs.set('limit', '200');
    const box = $('ahItems');
    box.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const data = await api(`/auction-house/items.json?${qs}`);
      if (!(data.rows || []).length) {
        box.innerHTML = '<p class="muted">No auctionable items matched.</p>';
        return;
      }
      box.innerHTML = (data.rows || []).map(row => `
        <button type="button" class="ah-item" data-item-id="${row.item_id}">
          <img src="/auction-house/items/${row.item_id}/icon.png" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
          <span><strong>${esc(row.name)}</strong><small>ID ${row.item_id} · ${esc(row.category_path || `AH ${row.category_id}`)} · stack ${row.stack_size}</small></span>
          <span class="ah-count"><strong>${fmt.format(row.active_listings)}</strong> listed<br>${row.historical_sales ? `${fmt.format(row.historical_sales)} recorded sales` : 'no recorded sales'}</span>
        </button>`).join('');
      box.querySelectorAll('[data-item-id]').forEach(button => button.addEventListener('click', () => loadDetail(Number(button.dataset.itemId))));
    } catch (error) {
      box.innerHTML = `<p>${esc(error.message)}</p>`;
    }
  }

  const unitPrice = (price, isStack, stackSize) => isStack && Number(stackSize) > 1 ? Number(price) / Number(stackSize) : Number(price);

  function historyTable(rows, stackSize) {
    if (!rows.length) return '<p class="muted">No completed sale history found.</p>';
    return `<table class="ah-table"><thead><tr><th>Date</th><th>Seller</th><th>Buyer</th><th>Lot</th><th class="ah-price">Sale</th><th class="ah-price">Per item</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(when(r.sold_at_iso))}</td><td>${esc(r.seller_name || `#${r.seller_id}`)}</td><td>${esc(r.buyer_name || (r.buyer_id ? `#${r.buyer_id}` : '—'))}</td><td>${r.stack ? `Stack ×${stackSize}` : 'Single'}</td><td class="ah-price">${money(r.sale_price)}</td><td class="ah-price">${money(Math.round(unitPrice(r.sale_price, r.stack, stackSize)))}</td></tr>`).join('')}</tbody></table>`;
  }

  function listingTable(rows, stackSize) {
    if (!rows.length) return '<p class="muted">No current listings.</p>';
    return `<table class="ah-table"><thead><tr><th>Listed</th><th>Seller</th><th>Lot</th><th class="ah-price">Asking</th><th class="ah-price">Per item</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(when(r.listed_at_iso))}</td><td>${esc(r.seller_name || `#${r.seller_id}`)}</td><td>${r.stack ? `Stack ×${stackSize}` : 'Single'}</td><td class="ah-price">${money(r.asking_price)}</td><td class="ah-price">${money(Math.round(unitPrice(r.asking_price, r.stack, stackSize)))}</td></tr>`).join('')}</tbody></table>`;
  }

  function summarizeTrend(rows) {
    const sales = rows.reduce((n, r) => n + Number(r.sales || 0), 0);
    if (!sales) return null;
    return {
      sales,
      average: rows.reduce((n, r) => n + Number(r.average_price || 0) * Number(r.sales || 0), 0) / sales,
      averageUnit: rows.reduce((n, r) => n + Number(r.average_unit_price || 0) * Number(r.sales || 0), 0) / sales,
      low: Math.min(...rows.map(r => Number(r.min_price))),
      high: Math.max(...rows.map(r => Number(r.max_price))),
    };
  }

  function trendLine(label, summary, showUnit) {
    if (!summary) return `<small>${label}: no sales</small>`;
    const unit = showUnit ? ` · ${money(Math.round(summary.averageUnit))}/item` : '';
    return `<small><strong>${label}</strong>: ${fmt.format(summary.sales)} · avg ${money(Math.round(summary.average))}${unit}<br>${money(summary.low)}–${money(summary.high)}</small>`;
  }

  function trendCard(days, rows, stackSize) {
    const singles = summarizeTrend(rows.filter(r => !r.stack));
    const stacks = summarizeTrend(rows.filter(r => r.stack));
    const total = (singles?.sales || 0) + (stacks?.sales || 0);
    const stackLine = Number(stackSize) > 1 ? `<br>${trendLine(`Stack ×${stackSize}`, stacks, true)}` : '';
    return `<div class="ah-trend"><strong>${days} days · ${fmt.format(total)} sales</strong><br>${trendLine('Single', singles, false)}${stackLine}</div>`;
  }

  async function loadDetail(itemId) {
    const box = $('ahDetail');
    box.innerHTML = '<h2>Item detail</h2><p class="muted">Loading…</p>';
    try {
      const data = await api(`/auction-house/items/${itemId}.json?history_limit=100`);
      const item = data.item;
      const returnedListings = (data.active_listings || []).length;
      const totalListings = Number(item.active_listings || 0);
      const listingSuffix = totalListings > returnedListings ? ` · showing ${fmt.format(returnedListings)}` : '';
      box.innerHTML = `
        <div class="page-head"><div><h2>${esc(item.name)}</h2><div class="muted">Item ${item.item_id} · ${esc(item.category_path || `AH category ${item.category_id}`)} · stack ${item.stack_size}</div></div><img class="ah-icon" src="/auction-house/items/${item.item_id}/icon.png" alt=""></div>
        <h3>Price & volume</h3><div class="ah-trends">${trendCard(7, data.trends['7'] || [], item.stack_size)}${trendCard(30, data.trends['30'] || [], item.stack_size)}${trendCard(90, data.trends['90'] || [], item.stack_size)}</div>
        <h3>Current listings (${fmt.format(totalListings)}${listingSuffix})</h3>${listingTable(data.active_listings || [], item.stack_size)}
        <h3>Recent sales</h3>${historyTable(data.history || [], item.stack_size)}`;
      $('ahPreviewItemId').value = item.item_id;
    } catch (error) {
      box.innerHTML = `<h2>Item detail</h2><p>${esc(error.message)}</p>`;
    }
  }

  function resetValidationForPreview(data) {
    lastActionPreview = data;
    $('ahValidatePreview').disabled = false;
    $('ahValidationReport').innerHTML = '<p class="muted">Preview generated. Run read-only validation to re-read current server state and all safety gates.</p>';
  }

  function renderActionPreview(data) {
    resetValidationForPreview(data);
    const box = $('ahActionPreview');
    const warnings = (data.warnings || []).map(w => `<div class="ah-warning"><strong>${w.blocking ? 'Blocked' : 'Note'} · ${esc(w.code)}</strong><br>${esc(w.message)}</div>`).join('');
    const effect = data.economic_effect || {};
    const effectRows = Object.entries(effect).map(([k,v]) => `<tr><td>${esc(k.replaceAll('_',' '))}</td><td>${typeof v === 'number' ? fmt.format(v) : esc(v)}</td></tr>`).join('');
    const binding = data.policy_binding || {};
    const policy = binding.policy_fingerprint ? `${esc(binding.family || 'legacy')} · ${esc(String(binding.policy_fingerprint).slice(0,12))}…` : 'not available';
    box.innerHTML = `<h3>${esc(data.action || 'Action')} preview</h3><p><strong>Adapter:</strong> ${esc(data.adapter || 'unknown')} · <strong>Apply supported:</strong> ${data.apply_supported ? 'yes' : 'no'} · <strong>Policy:</strong> ${policy}</p>${warnings}<table class="ah-table"><tbody>${effectRows}</tbody></table>`;
  }

  function stageLabel(name) {
    return ({
      environment:'Environment',
      lineage:'Lineage semantics',
      schema_readiness:'Schema / triggers',
      database_freshness:'Database freshness',
      policy:'Active policy',
      policy_binding:'Policy binding',
      invariants:'Economic / inventory invariants',
    })[name] || name.replaceAll('_',' ');
  }

  function renderValidationReport(data) {
    const box = $('ahValidationReport');
    const stages = Object.entries(data.stages || {}).map(([name, stage]) => {
      const issues = (stage.issues || []).map(issue => `<li><strong>${esc(issue.code || 'issue')}</strong> — ${esc(issue.message || '')}</li>`).join('');
      return `<div class="ah-validation-stage"><strong>${stage.ready ? 'PASS' : 'BLOCKED'} · ${esc(stageLabel(name))}</strong>${issues ? `<ul>${issues}</ul>` : '<p class="muted">No blocking issue reported.</p>'}</div>`;
    }).join('');
    const blockers = (data.blockers || []).map(item => `<li><strong>${esc(stageLabel(item.stage || 'gate'))} · ${esc(item.code || 'blocked')}</strong> — ${esc(item.message || '')}</li>`).join('');
    const evidenceState = data.read_only_validation_ready ? 'READ-ONLY VALIDATION READY' : 'VALIDATION BLOCKED';
    box.innerHTML = `<div class="ah-validation-summary"><span class="badge">${esc(evidenceState)}</span><span class="badge">EXECUTION DISABLED</span><strong>${esc(data.operation || 'preview')}</strong></div>
      <div class="ah-validation-grid">${stages || '<p class="muted">No validation stages returned.</p>'}</div>
      <h4>Blocking reasons</h4>${blockers ? `<ul class="ah-validation-blockers">${blockers}</ul>` : '<p class="muted">No read-only evidence blockers. Execution remains disabled.</p>'}`;
  }

  $('ahListPreviewForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      renderActionPreview(await postApi('/auction-house/admin/list/preview.json', {
        item_id: Number($('ahPreviewItemId').value),
        seller_id: Number($('ahPreviewSellerId').value),
        price: Number($('ahPreviewPrice').value),
        stack: $('ahPreviewStack').checked,
      }));
    } catch (error) {
      $('ahActionPreview').innerHTML = `<p>${esc(error.message)}</p>`;
    }
  });

  $('ahPurchasePreviewForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const buyer = $('ahPreviewBuyerId').value.trim();
      renderActionPreview(await postApi('/auction-house/admin/purchase/preview.json', {
        auction_id: Number($('ahPreviewAuctionId').value),
        mode: $('ahPreviewPurchaseMode').value,
        buyer_id: buyer ? Number(buyer) : null,
      }));
    } catch (error) {
      $('ahActionPreview').innerHTML = `<p>${esc(error.message)}</p>`;
    }
  });

  $('ahValidatePreview').addEventListener('click', async () => {
    if (!lastActionPreview) return;
    const button = $('ahValidatePreview');
    button.disabled = true;
    $('ahValidationReport').innerHTML = '<p class="muted">Re-reading current database/configuration state…</p>';
    try {
      renderValidationReport(await postApi('/auction-house/admin/validate/preview.json', {preview:lastActionPreview}));
    } catch (error) {
      $('ahValidationReport').innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
      button.disabled = !lastActionPreview;
    }
  });

  $('ahSearchButton').addEventListener('click', loadItems);
  $('ahSearch').addEventListener('keydown', e => { if (e.key === 'Enter') loadItems(); });
  $('ahCategory').addEventListener('change', loadItems);
  $('ahHealthRefresh').addEventListener('click', loadHealth);
  $('ahHealthDays').addEventListener('change', loadHealth);
  $('ahStaleDays').addEventListener('change', loadHealth);
  // Deep link from the Item Browser: /auction-house?item=<id> opens that item's detail.
  const linkedItem = Number(new URLSearchParams(location.search).get('item'));
  if (linkedItem > 0) $('ahSearch').value = String(linkedItem);
  Promise.all([loadStatus(), loadWriteReadiness(), loadOverview(), loadHealth(), loadCategories()]).then(loadItems).then(() => {
    if (linkedItem > 0) { loadDetail(linkedItem); $('ahDetail').scrollIntoView({block: 'start'}); }
  }).catch(error => {
    $('ahStatus').textContent = error.message;
    $('ahItems').innerHTML = '<p class="muted">Auction House data unavailable.</p>';
  });
})();