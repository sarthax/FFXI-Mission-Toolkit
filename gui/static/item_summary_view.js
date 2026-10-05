/* Shared renderer for /itemedit/summary.json -- used by the Item Editor and the Item Browser.
   window.ItemSummaryView.render(summaryObj, lsbCompareObj|null) -> HTMLElement */
(function () {
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const HEALTH = {behavior: ['ok', 'Has behavior'], 'check-only': ['warn', 'Check-only (no effect code)'],
                  stub: ['bad', 'Stub (hooks empty)'], missing: ['bad', 'Script file missing']};
  function sec(title, inner) { return inner ? `<section class="isv-sec"><h4>${esc(title)}</h4>${inner}</section>` : ''; }
  function rows(list, fn) { return list && list.length ? `<ul>${list.map(x => `<li>${fn(x)}</li>`).join('')}</ul>` : ''; }
  function render(s, lsb) {
    const el = document.createElement('div');
    el.className = 'isv';
    const c = s.combat, id = s.identity || {};
    let h = `<style>.isv .isv-sec{margin:.6rem 0}.isv h4{margin:0 0 .2rem;font-size:.85rem;opacity:.75;text-transform:uppercase;letter-spacing:.04em}
      .isv ul{margin:0;padding-left:1.1rem}.isv .ok{color:#3a9d5d}.isv .warn{color:#c98a1b}.isv .bad{color:#cf4a4a}
      .isv pre{max-height:14rem;overflow:auto;background:rgba(127,127,127,.12);padding:.4rem;border-radius:4px;font-size:.78rem}
      .isv .tag{display:inline-block;padding:0 .4rem;border-radius:3px;border:1px solid currentColor;font-size:.75rem}</style>`;
    h += `<h3 style="margin:.2rem 0">${esc(id.client_name || id.name)} <small class="muted">#${esc(s.item_id)}</small></h3>`;
    if (s.client_description) h += `<div class="muted" style="white-space:pre-line">${esc(s.client_description)}</div>`;
    if (c) h += sec('Weapon', `DMG ${esc(c.damage)} &nbsp; Delay ${esc(c.delay)}` +
      (c.multi_hit ? `<br><b>${esc(c.multi_hit.text)}</b>` + (c.multi_hit.distribution_pct ?
        ` <span class="muted">(${Object.entries(c.multi_hit.distribution_pct).map(([k, v]) => k + ' hit ' + v + '%').join(', ')})</span>` : '') : ''));
    h += sec('Bonuses', rows(s.bonuses, b => `${esc(b.name)} <b>${esc(b.value)}</b>${b.known ? '' : ' <span class="bad">(unknown id)</span>'}` +
      (b.meaning ? ` <span class="muted">${esc(b.meaning)}</span>` : '')));
    h += sec('Pet bonuses', rows(s.pet_bonuses, b => `${esc(b.pet_type)}: ${esc(b.name)} <b>${esc(b.value)}</b>`));
    h += sec('Conditional bonuses', rows(s.conditional_bonuses, b => `${esc(b.name)} <b>${esc(b.value)}</b> when ${esc(b.condition)}` +
      (b.param != null ? ` (${esc(b.param)}${b.param_meaning ? ' = ' + esc(b.param_meaning) : ''})` : '') +
      (b.known ? '' : ' <span class="bad">(unknown condition)</span>')));
    if (s.script) {
      const sc = s.script, hl = HEALTH[sc.health] || ['warn', sc.health];
      h += sec('Item script', `<span class="tag ${hl[0]}">${esc(hl[1])}</span> <code>${esc(sc.path)}</code>` +
        (sc.hooks.length ? `<ul>${sc.hooks.map(k => `<li><b>${esc(k.hook)}</b> &mdash; ${esc(k.meaning)}` +
          (k.trivial ? ' <span class="bad">(empty)</span>' : k.statements != null ? ` <span class="muted">${k.statements} statements${k.effect_calls.length ? '; calls ' + esc(k.effect_calls.join(', ')) : ''}</span>` : '') +
          (k.body && !k.trivial ? `<details><summary>show code</summary><pre>${esc(k.body)}</pre></details>` : '') + '</li>').join('')}</ul>` : ''));
    }
    h += sec('Set bonuses', rows(s.set_bonuses, g => esc(g.comment || ('set ' + g.set_id)) + (g.matches_required != null ? ` <span class="muted">(${esc(g.matches_required)} pieces)</span>` : '')));
    h += sec('While active (food/medicine)', rows(s.effect_gain_mods, m => `${esc(m.mod)} <b>${esc(m.value)}</b>`));
    h += sec('Referenced in server code', rows(s.code_references, r => `<code>${esc(r.file || r.path || JSON.stringify(r))}</code>${r.line ? ':' + esc(r.line) : ''}`));
    h += sec('Gaps / warnings', rows(s.notes, n => `<span class="warn">${esc(n.message)}</span>`));
    if (lsb) {
      if (!lsb.available) h += sec('LandSandBoat compare', `<span class="muted">${esc(lsb.reason)}</span>`);
      else if (!lsb.in_lsb) h += sec('LandSandBoat compare', '<span class="muted">Item not in LSB mod/weapon tables.</span>');
      else if (lsb.identical) h += sec('LandSandBoat compare', '<span class="ok">Matches LSB (mods and weapon stats).</span>');
      else h += sec('LandSandBoat compare', rows((lsb.mod_differences || []).map(d => ({t: 'mod', d})).concat((lsb.weapon_differences || []).map(d => ({t: 'w', d}))),
        x => x.t === 'mod' ? `${esc(x.d.mod)}: DSP <b>${esc(x.d.dsp ?? '—')}</b> vs LSB <b>${esc(x.d.lsb ?? '—')}</b>${x.d.hint ? ` <span class="muted">${esc(x.d.hint)}</span>` : ''}`
                            : `weapon ${esc(x.d.field)}: DSP <b>${esc(x.d.dsp)}</b> vs LSB <b>${esc(x.d.lsb)}</b>`));
    }
    el.innerHTML = h;
    return el;
  }
  window.ItemSummaryView = {render, esc};
})();
