(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadCategory !== 'function') return;

  const previousLoadCategory = loadCategory;
  loadCategory = async function(key) {
    await previousLoadCategory(key);
    if (key === 'jobs-skills') await renderJobsSkills();
  };

  const JOBS = ['WAR','MNK','WHM','BLM','RDM','THF','PLD','DRK','BST','BRD','RNG','SAM','NIN','DRG','SMN','BLU','COR','PUP','DNC','SCH','GEO','RUN'];
  const RANK_LETTER = {1:'A+',2:'A-',3:'B+',4:'B',5:'B-',6:'C+',7:'C',8:'C-',9:'D',10:'E',11:'F',12:'G'};
  const SKILL_SECTIONS = [['Combat','Combat skills'],['Magic','Magic skills'],['Puppet','Automaton skills'],['Synthesis','Crafting (synthesis)']];
  let selectedNav = 'jobs';
  let selectedJob = '';
  let refCache = null;
  const base = () => `/character-editor/characters/${selectedChar}/fields`;

  async function postJson(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({detail: r.statusText}));
    if (!r.ok) throw new Error(d.detail || r.statusText);
    return d;
  }

  async function renderJobsSkills() {
    const box = document.getElementById('categoryData');
    if (!box || !selectedChar) return;
    box.querySelectorAll(':scope > .ce-jobs-manager').forEach(n => n.remove());
    const shell = document.createElement('div');
    shell.className = 'ce-progression ce-jobs-manager';
    shell.innerHTML = '<div class="ce-progress-empty">Loading jobs and skills…</div>';
    box.prepend(shell);

    if (!refCache) {
      try { refCache = await (await fetch('/character-editor/reference/jobs-skills.json')).json(); }
      catch (e) { shell.innerHTML = `<div class="warn">Could not load reference: ${esc(e.message)}</div>`; return; }
    }
    const ref = refCache;
    const t = activeCategoryData?.tables || {};
    const jobsRow = (t.char_jobs || [])[0] || {};
    const expRow = (t.char_exp || [])[0] || {};
    const skillRows = new Map((t.char_skills || []).map(r => [Number(r.skillid), r]));
    const offline = editableOnline();
    const pending = new Map(); // "table|column|skillid" -> {table,column,selector,value,label}

    const levelOf = j => Number(jobsRow[j.toLowerCase()] || 0);
    if (!selectedJob) selectedJob = JOBS.reduce((b, j) => levelOf(j) > levelOf(b) ? j : b, JOBS[0]);

    const skillIds = Object.keys(ref.skills).map(Number).filter(id => id > 0).sort((a, b) => a - b);
    const nav = [{section:'Jobs'}, {key:'jobs', label:'Job levels & EXP', badge:`${JOBS.filter(j => levelOf(j) > 0).length} jobs`},
                 {key:'points', label:'Merits & limits', badge:`${expRow.merits ?? 0} / ${expRow.limits ?? 0}`}, {section:'Skills'}];
    for (const [cat, label] of SKILL_SECTIONS) {
      const ids = skillIds.filter(id => ref.skills[id].category === cat);
      if (ids.length) nav.push({key:`skills:${cat}`, label, ids, badge:`${ids.filter(id => skillRows.has(id)).length}/${ids.length}`});
    }

    shell.innerHTML = `<style>.ce-jobs-manager .ce-split{display:grid;grid-template-columns:190px minmax(0,1fr);gap:10px;align-items:start}
      .ce-jobs-manager .ce-split-nav{position:sticky;top:96px;display:flex;flex-direction:column;gap:2px}
      .ce-jobs-manager .ce-split-section{font-size:9px;text-transform:uppercase;letter-spacing:.06em;opacity:.55;margin:10px 0 2px}
      .ce-jobs-manager .ce-split-item{display:flex;justify-content:space-between;text-align:left;padding:4px 8px;font-size:12px;cursor:pointer;border:1px solid transparent;border-radius:4px;background:transparent;color:inherit}
      .ce-jobs-manager .ce-split-item.active{border-color:var(--border,#555);background:rgba(255,255,255,.1);font-weight:700}.ce-jobs-manager .ce-split-item small{font-size:10px;opacity:.7}
      .ce-jobs-manager .ce-jrow{display:grid;grid-template-columns:70px 90px 110px minmax(0,1fr);gap:8px;align-items:center;padding:4px 6px;border-top:1px solid var(--border,#333);font-size:12px}
      .ce-jobs-manager .ce-srow{display:grid;grid-template-columns:minmax(130px,1.2fr) 110px 60px 90px minmax(0,1fr);gap:8px;align-items:center;padding:4px 6px;border-top:1px solid var(--border,#333);font-size:12px}
      .ce-jobs-manager input[type=number]{width:90px;min-width:0;padding:2px 4px}.ce-jobs-manager .ce-pending{background:rgba(138,101,0,.18);outline:1px solid #8a6500}
      .ce-jobs-manager .ce-jhead{font-size:9px;text-transform:uppercase;opacity:.6}
      .ce-jobs-manager .ce-apply-inline{position:sticky;bottom:0;display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:8px;background:var(--panel,#1b1b1b);border-top:1px solid var(--border,#444)}
      @media(max-width:760px){.ce-jobs-manager .ce-split{grid-template-columns:1fr}.ce-jobs-manager .ce-split-nav{position:static;flex-direction:row;flex-wrap:wrap}}</style>
      <div class="ce-progress-head"><strong>Jobs &amp; Skills</strong>${offline ? pill('offline editing enabled','ok') : pill('editing locked until offline','warn')}<span class="ce-progress-source">Skills are the numbers behind combat, magic and crafting. Traits (on Spells &amp; Abilities) are passive bonuses that unlock from job level; they are not stored here.</span></div>
      <div class="ce-split"><nav class="ce-split-nav"></nav><section class="ce-split-detail"></section></div>
      <div class="ce-apply-inline" hidden><span class="ce-pending-count"></span><button class="ce-discard">Discard</button><button class="ce-apply primary">Apply changes</button></div>`;
    const navEl = shell.querySelector('.ce-split-nav'), detail = shell.querySelector('.ce-split-detail'), bar = shell.querySelector('.ce-apply-inline');
    if (!nav.some(n => n.key === selectedNav)) selectedNav = 'jobs';

    const refreshBar = () => { bar.hidden = !pending.size; bar.querySelector('.ce-pending-count').textContent = `${pending.size} pending change${pending.size === 1 ? '' : 's'}`; };
    const drawNav = () => {
      navEl.innerHTML = nav.map(n => n.section ? `<div class="ce-split-section">${esc(n.section)}</div>`
        : `<button class="ce-split-item${n.key === selectedNav ? ' active' : ''}" data-nav="${esc(n.key)}"><span>${esc(n.label)}</span><small>${esc(n.badge || '')}</small></button>`).join('');
      navEl.querySelectorAll('[data-nav]').forEach(b => b.addEventListener('click', () => { selectedNav = b.dataset.nav; drawNav(); drawDetail(); }));
    };
    const stage = (id, table, column, selector, value, original, label) => {
      if (Number(value) === Number(original)) pending.delete(id); else pending.set(id, {table, column, selector, value:Number(value), label});
      refreshBar();
    };
    const dis = offline ? '' : 'disabled';

    const drawJobs = () => {
      const unlocked = Number(jobsRow.unlocked || 0);
      detail.innerHTML = `<h3>Job levels &amp; EXP</h3><div class="ce-muted">Level cap (genkai): <input type="number" class="ce-genkai" min="50" max="99" value="${pending.get('jobs|genkai')?.value ?? Number(jobsRow.genkai ?? 50)}" ${dis}> · 'Unlocked' is the job-unlocked bitmask (bit = job id).</div>
        <div class="ce-jrow ce-jhead"><span>Job</span><span>Unlocked</span><span>Level</span><span>EXP (current level)</span></div>
        ${JOBS.map((j, i) => { const lc = j.toLowerCase(); const lv = pending.get(`jobs|${lc}`)?.value ?? levelOf(j); const xp = pending.get(`exp|${lc}`)?.value ?? Number(expRow[lc] ?? 0);
          const bit = (unlocked >> (i + 1)) & 1;
          return `<div class="ce-jrow"><b>${j}</b><label><input type="checkbox" data-bit="${i + 1}" ${bit ? 'checked' : ''} ${dis}></label><input type="number" data-col="${lc}" data-t="jobs" min="0" max="99" value="${lv}" class="${pending.has(`jobs|${lc}`) ? 'ce-pending' : ''}" ${dis}><input type="number" data-col="${lc}" data-t="exp" min="0" value="${xp}" class="${pending.has(`exp|${lc}`) ? 'ce-pending' : ''}" ${dis}></div>`; }).join('')}`;
      detail.querySelector('.ce-genkai').addEventListener('change', e => stage('jobs|genkai', 'char_jobs', 'genkai', null, e.target.value, jobsRow.genkai, 'Level cap'));
      detail.querySelectorAll('input[data-col]').forEach(inp => inp.addEventListener('change', () => {
        const tbl = inp.dataset.t === 'jobs' ? 'char_jobs' : 'char_exp', orig = inp.dataset.t === 'jobs' ? jobsRow[inp.dataset.col] : expRow[inp.dataset.col];
        stage(`${inp.dataset.t}|${inp.dataset.col}`, tbl, inp.dataset.col, null, inp.value, orig, `${inp.dataset.col.toUpperCase()} ${inp.dataset.t === 'jobs' ? 'level' : 'EXP'}`);
        inp.classList.toggle('ce-pending', pending.has(`${inp.dataset.t}|${inp.dataset.col}`));
      }));
      detail.querySelectorAll('input[data-bit]').forEach(cb => cb.addEventListener('change', () => {
        let mask = pending.has('jobs|unlocked') ? pending.get('jobs|unlocked').value : unlocked;
        mask = cb.checked ? (mask | (1 << Number(cb.dataset.bit))) : (mask & ~(1 << Number(cb.dataset.bit)));
        stage('jobs|unlocked', 'char_jobs', 'unlocked', null, mask, unlocked, 'Unlocked jobs');
      }));
    };

    const drawPoints = () => {
      detail.innerHTML = `<h3>Merits &amp; limits</h3><div class="ce-muted">Unspent merit points, limit points and the EXP/limit mode. Allocated merits are on the Merits page.</div>
        ${[['mode','Mode (0 = EXP, 1 = limit)'],['merits','Merit points'],['limits','Limit points']].map(([c, l]) => `<div class="ce-jrow" style="grid-template-columns:200px 110px"><span>${l}</span><input type="number" data-col="${c}" min="0" value="${pending.get(`exp|${c}`)?.value ?? Number(expRow[c] ?? 0)}" ${dis}></div>`).join('')}`;
      detail.querySelectorAll('input[data-col]').forEach(inp => inp.addEventListener('change', () => stage(`exp|${inp.dataset.col}`, 'char_exp', inp.dataset.col, null, inp.value, expRow[inp.dataset.col], inp.dataset.col)));
    };

    const drawSkills = n => {
      const lvl = levelOf(selectedJob);
      const capFor = id => { const r = Number(ref.ranks[String(id)]?.[selectedJob] || 0); return r ? (ref.caps[String(lvl)]?.[r] ?? null) : null; };
      detail.innerHTML = `<h3>${esc(n.label)}</h3><div class="ce-toolbar"><label>Cap preview for <select class="ce-sk-job">${JOBS.map(j => `<option ${j === selectedJob ? 'selected' : ''}>${j}</option>`).join('')}</select> Lv${lvl}</label><button class="ce-sk-max" ${dis}>Set all to cap</button></div>
        <div class="ce-muted">Stored value is skill ×10 (5000 = 500.0). Rank letter and cap come from the server's skill tables for the chosen job and its level. Crafts have no job cap.</div>
        <div class="ce-srow ce-jhead"><span>Skill</span><span>Skill level</span><span>Rank</span><span>Cap</span><span></span></div>
        <div class="ce-sk-list"></div>`;
      const list = detail.querySelector('.ce-sk-list');
      const draw = () => {
        list.innerHTML = n.ids.map(id => {
          const row = skillRows.get(id); const key = `skill|${id}`;
          const stored = row ? Number(row.value) : 0;
          const val = pending.get(key)?.value ?? stored;
          const rk = Number(ref.ranks[String(id)]?.[selectedJob] || 0), cap = capFor(id);
          return `<div class="ce-srow${pending.has(key) ? ' ce-pending' : ''}"><span>${esc(ref.skills[id].name)}<br><small class="ce-muted">ID ${id}${row ? '' : ' · no row yet'}</small></span><input type="number" data-id="${id}" min="0" max="32767" step="1" value="${val / 10}" ${dis}><span>${rk ? RANK_LETTER[rk] || rk : '—'}</span><span>${cap ?? '—'}</span><span class="ce-muted">${cap && val / 10 >= cap ? 'at cap' : ''}</span></div>`;
        }).join('');
        list.querySelectorAll('input[data-id]').forEach(inp => inp.addEventListener('change', () => {
          const id = Number(inp.dataset.id), row = skillRows.get(id);
          stage(`skill|${id}`, 'char_skills', 'value', {skillid:id}, Math.round(Number(inp.value) * 10), row ? row.value : 0, ref.skills[id].name);
          draw();
        }));
      };
      detail.querySelector('.ce-sk-job').addEventListener('change', e => { selectedJob = e.target.value; drawSkills(n); });
      detail.querySelector('.ce-sk-max').addEventListener('click', () => {
        for (const id of n.ids) { const cap = capFor(id); if (cap) stage(`skill|${id}`, 'char_skills', 'value', {skillid:id}, cap * 10, skillRows.get(id)?.value ?? 0, ref.skills[id].name); }
        draw();
      });
      draw();
    };

    const drawDetail = () => {
      const n = nav.find(x => x.key === selectedNav);
      if (selectedNav === 'jobs') drawJobs(); else if (selectedNav === 'points') drawPoints(); else if (n) drawSkills(n);
    };

    bar.querySelector('.ce-discard').addEventListener('click', () => { pending.clear(); refreshBar(); drawDetail(); });
    bar.querySelector('.ce-apply').addEventListener('click', async () => {
      const changes = [...pending.values()];
      if (!changes.length || !confirm(`Apply ${changes.length} change(s) to this character?`)) return;
      const btn = bar.querySelector('.ce-apply'); btn.disabled = true;
      // One request per table row: batch columns that share table+selector.
      const groups = new Map();
      for (const c of changes) {
        const k = `${c.table}|${JSON.stringify(c.selector)}`;
        const g = groups.get(k) || {table:c.table, selector:c.selector, changes:{}};
        g.changes[c.column] = c.value; groups.set(k, g);
      }
      let done = 0;
      try {
        for (const g of groups.values()) {
          const body = {table:g.table, changes:g.changes}; if (g.selector) body.selector = g.selector;
          const p = await postJson(`${base()}/preview`, body);
          if (!p.ready) throw new Error((p.issues || []).map(i => i.message).join('; ') || `${g.table} is not write-ready`);
          await postJson(`${base()}/apply`, {...body, expected_before:p.before, approved:true});
          done++;
        }
      } catch (e) { alert(`Applied ${done} of ${groups.size} row edits. Stopped: ${e.message}`); }
      await selectCharacter(selectedChar);
      await loadCategory('jobs-skills');
    });
    drawNav(); drawDetail(); refreshBar();
  }
})();
