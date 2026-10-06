/* Replaces raw numeric id fields on AH tool pages with name-searchable pickers.
   The original <input> stays in the DOM (hidden) and keeps holding the numeric id, so each page's own
   script keeps reading/writing it unchanged. */
(() => {
  const PLAYERS = [
    // id, label, includeAuctionOnlySellers
    ['cuSellerId', 'Seller', true], ['apSellerId', 'Seller', true], ['lmSellerId', 'Seller', true],
    ['seedPlayerSeller', 'Seller character', false], ['seedSyntheticSeller', 'Seller character', false],
    ['apSeedSeller', 'Seller character', false], ['ahPreviewSellerId', 'Seller character', false],
    ['ahPreviewBuyerId', 'Buyer character', false],
  ];
  const CATEGORIES = [['cuCategoryId', 'Category'], ['apCategoryId', 'Category'], ['apSeedCategory', 'Category']];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const getJson = async url => { const r = await fetch(url, {headers: {Accept: 'application/json'}}); if (!r.ok) throw new Error(r.statusText); return r.json(); };
  let cats = null;
  const loadCats = async () => cats || (cats = (await getJson('/auction-house/categories.json')).rows || []);

  const css = document.createElement('style');
  css.textContent = `.ahp{position:relative;display:block}.ahp input.ahp-q{width:100%;min-width:220px}
.ahp-pop{position:absolute;z-index:70;left:0;right:0;top:100%;max-height:260px;overflow:auto;background:var(--surface-1,var(--bg-color,#222));border:1px solid var(--border-color,#5558);border-radius:6px;box-shadow:0 8px 22px #0006}
.ahp-pop div{padding:5px 9px;cursor:pointer;font-size:13px}.ahp-pop div:hover,.ahp-pop div.on{background:#8883}.ahp-pop small{opacity:.65}
.ahp-sel{font-size:11px;opacity:.7;margin-top:2px;min-height:14px}`;
  document.head.appendChild(css);

  function attach(id, label, fetchRows, render, pick) {
    const real = document.getElementById(id);
    if (!real || real.dataset.picker) return;
    real.dataset.picker = '1';
    const lab = real.closest('label');
    if (lab) {
      const node = [...lab.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
      if (node) node.textContent = label + ' ';
    }
    const wrap = document.createElement('span');
    wrap.className = 'ahp';
    const q = document.createElement('input');
    q.type = 'search'; q.className = 'ahp-q'; q.autocomplete = 'off';
    q.placeholder = real.getAttribute('placeholder') || 'Type a name' + (pick.byAccount ? ', account or id' : '');
    const pop = document.createElement('div'); pop.className = 'ahp-pop'; pop.hidden = true;
    const sel = document.createElement('div'); sel.className = 'ahp-sel';
    real.type = 'hidden';
    real.parentNode.insertBefore(wrap, real);
    wrap.append(q, pop, sel, real);

    let timer = 0, shown = [];
    const setValue = (val, text) => {
      real.value = val == null ? '' : String(val);
      q.value = text || '';
      sel.textContent = val ? `#${val}` : '';
      real.dispatchEvent(new Event('input', {bubbles: true}));
      real.dispatchEvent(new Event('change', {bubbles: true}));
    };
    const choose = r => { const [val, text, extra] = pick.apply(r); setValue(val, text); sel.textContent = extra || `#${val}`; if (pick.after) pick.after(r); pop.hidden = true; };
    const search = async () => {
      const term = q.value.trim();
      if (!term) { if (real.value) setValue('', ''); pop.hidden = true; return; }
      try { shown = await fetchRows(term); } catch (e) { shown = []; }
      pop.innerHTML = shown.length ? shown.map((r, i) => `<div data-i="${i}">${render(r)}</div>`).join('') : '<div><small>No matches</small></div>';
      pop.hidden = false;
    };
    q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 180); });
    q.addEventListener('focus', () => { if (q.value.trim() && !real.value) search(); });
    q.addEventListener('keydown', e => { if (e.key === 'Enter' && shown.length && !pop.hidden) { e.preventDefault(); choose(shown[0]); } if (e.key === 'Escape') pop.hidden = true; });
    pop.addEventListener('mousedown', e => { const d = e.target.closest('[data-i]'); if (d) { e.preventDefault(); choose(shown[+d.dataset.i]); } });
    document.addEventListener('click', e => { if (!wrap.contains(e.target)) pop.hidden = true; });

    // The page's own script (preset load, reset) may set the hidden value directly: mirror it into the display.
    let last = real.value;
    setInterval(async () => {
      if (real.value === last) return;
      last = real.value;
      if (!real.value) { q.value = ''; sel.textContent = ''; return; }
      try { const r = await pick.resolve(real.value); if (r) { q.value = r[0]; sel.textContent = r[1] || ''; } else { q.value = ''; sel.textContent = `#${real.value}`; } } catch (e) { sel.textContent = `#${real.value}`; }
    }, 400);
    if (real.value) { last = ''; }
  }

  function init() {
    for (const [id, label, anySeller] of PLAYERS) {
      attach(id, label,
        async term => (await getJson(`/auction-house/console/characters.json?q=${encodeURIComponent(term)}&limit=20${anySeller ? '&include_sellers=true' : ''}`)).rows,
        r => `<b>${esc(r.char_name)}</b> <small>#${r.char_id}${r.login ? ' · account ' + esc(r.login) : ''}${r.source === 'auction-only' ? ' · AH seller only' : ''}</small>`,
        {
          byAccount: true,
          apply: r => [r.char_id, r.char_name, `#${r.char_id}${r.login ? ' · account ' + r.login : ''}`],
          resolve: async v => { const row = (await getJson(`/auction-house/console/characters.json?q=${encodeURIComponent(v)}&limit=5${anySeller ? '&include_sellers=true' : ''}`)).rows.find(r => String(r.char_id) === String(v)); return row ? [row.char_name, `#${row.char_id}${row.login ? ' · account ' + row.login : ''}`] : null; },
          // filling a paired name field (Seller name) with the pick keeps name-based filters consistent
          after: r => { const nm = document.getElementById(id.replace(/Id$/, 'Name')); if (nm && nm !== document.getElementById(id)) nm.value = ''; },
        });
    }
    for (const [id, label] of CATEGORIES) {
      attach(id, label,
        async term => { const t = term.toLowerCase(); return (await loadCats()).filter(c => String(c.category_id) === t || (c.path || c.label || '').toLowerCase().includes(t)).slice(0, 40); },
        c => `${esc(c.path || c.label || 'Category ' + c.category_id)} <small>#${c.category_id}</small>`,
        {
          apply: c => [c.category_id, c.path || c.label || `Category ${c.category_id}`, `#${c.category_id}`],
          resolve: async v => { const c = (await loadCats()).find(x => String(x.category_id) === String(v)); return c ? [c.path || c.label || '', `#${c.category_id}`] : null; },
        });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
