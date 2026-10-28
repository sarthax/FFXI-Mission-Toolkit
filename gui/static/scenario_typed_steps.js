/* Typed step builder (#1411): pick a reviewed template (#1409), fill typed parameters, get native Headless draft JSON.
 * Validation is done by the server through the typed action library, the single source of truth; nothing is ported
 * here. Nothing is sent to a game client or saved with the scenario draft, and no oracle or verdict is implied. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ScenarioTypedSteps = api;
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';
  const MAX_STEPS = 100;
  const NUMBER = /^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/;

  // Text from an input becomes a number when it is one; anything else is passed on as text so the server rejects it
  // with its own reason. Blank text is "no value" (undefined).
  function parseNumberText(text) {
    const t = String(text === undefined || text === null ? '' : text).trim();
    if (t === '') return undefined;
    if (!NUMBER.test(t)) return t;
    if (/^[-+]?\d+$/.test(t)) { // integers are checked exactly so a too-large value is never rounded into range
      const big = BigInt(t);
      return big <= 2n ** 53n && big >= -(2n ** 53n) ? Number(big) : t;
    }
    const n = Number(t);
    return Number.isFinite(n) ? n : t;
  }

  // Build the walk_to value from the coordinate fields: [x, z], [x, y, z], or {coords, timeout_ms, stall_ms}.
  function composeWalkTarget(fields) {
    const x = parseNumberText(fields.x), y = parseNumberText(fields.y), z = parseNumberText(fields.z);
    if (x === undefined || z === undefined) return {error: 'x and z are required (y is optional)'};
    const coords = y === undefined ? [x, z] : [x, y, z];
    const timeout = parseNumberText(fields.timeout_ms), stall = parseNumberText(fields.stall_ms);
    if (timeout === undefined && stall === undefined) return {value: coords};
    const value = {coords};
    if (timeout !== undefined) value.timeout_ms = timeout;
    if (stall !== undefined) value.stall_ms = stall;
    return {value};
  }

  function uniqueName(base, taken) {
    const root = String(base || '').trim().slice(0, 100) || 'step';
    if (!taken.includes(root)) return root;
    let n = 2;
    while (taken.includes(root + ' (' + n + ')')) n++;
    return root + ' (' + n + ')';
  }

  const clone = value => JSON.parse(JSON.stringify(value));

  // One native step in the shape the Headless scenario files use: a name plus do / expect maps.
  function nativeScenario(entries) {
    return entries.map(entry => ({name: entry.name, do: clone(entry.step.do), expect: clone(entry.step.expect)}));
  }
  const nativeJson = entries => JSON.stringify(nativeScenario(entries), null, 2);

  function describeAction(step) {
    const action = Object.keys(step.do)[0], expect = Object.keys(step.expect)[0];
    return action + ' ' + JSON.stringify(step.do[action]) + ', then check ' + expect + ' = ' + JSON.stringify(step.expect[expect]);
  }
  function describeStep(template, step) {
    return template.label + ' — ' + describeAction(step);
  }

  function moveItem(list, index, delta) {
    const target = index + delta;
    if (index < 0 || index >= list.length || target < 0 || target >= list.length) return list.slice();
    const next = list.slice();
    [next[index], next[target]] = [next[target], next[index]];
    return next;
  }

  // ---- catalog picker helpers (pure) --------------------------------------------------------------------------------
  // Candidates come from the existing local DSP catalog search. They are *unreconciled source candidates*: a pick fills
  // an ID field the author can still edit, and says where the value came from; it never proves the ID is right for a
  // particular zone or client.
  function catalogQueryProblem(query) {
    const q = String(query === undefined || query === null ? '' : query).trim();
    if (q === '') return 'Type part of a name to search.';
    if (q.length > 64) return 'Search text can be at most 64 characters.';
    return '';
  }
  function catalogUrl(kind, query, limit = 12) {
    return '/scenario-developer/catalog/search?kind=' + encodeURIComponent(kind) + '&query=' +
      encodeURIComponent(String(query).trim()) + '&limit=' + encodeURIComponent(limit);
  }
  // Only well-formed rows of the requested kind are ever offered; anything else from the server is ignored.
  function usableCandidate(candidate, kind) {
    return !!candidate && typeof candidate === 'object' && candidate.kind === kind &&
      Number.isSafeInteger(candidate.id) && candidate.id >= 0 &&
      typeof candidate.name === 'string' && candidate.name.trim() !== '' && typeof candidate.source_path === 'string';
  }
  function describeCandidate(candidate) {
    return candidate.name.trim().slice(0, 120) + ' (id ' + candidate.id + ')' +
      (candidate.duplicate_id_in_results ? ' — AMBIGUOUS: this ID appears more than once' : '');
  }
  function provenanceNote(candidate, parameter) {
    return parameter + ' = ' + candidate.id + ' (' + candidate.name.trim().slice(0, 120) + ') — unreconciled DSP source ' +
      'candidate from ' + candidate.source_path + '; not verified for this zone or client';
  }

  // ---- native import helpers (pure) -----------------------------------------------------------------------------------
  const MAX_IMPORT_CHARS = 30000; // the local route refuses larger bodies
  function parseNativeText(text) {
    const raw = String(text === undefined || text === null ? '' : text).trim();
    if (raw === '') return {error: 'Paste native scenario JSON to review.'};
    if (raw.length > MAX_IMPORT_CHARS) return {error: 'That is too large to review here (limit ' + MAX_IMPORT_CHARS + ' characters).'};
    let parsed;
    try { parsed = JSON.parse(raw); } catch (error) { return {error: 'That is not valid JSON: ' + error.message}; }
    if (!Array.isArray(parsed)) return {error: 'A native scenario is an array of steps. Wrap a single step in [ ].'};
    if (parsed.length < 1 || parsed.length > MAX_STEPS) return {error: 'A native scenario must have 1 to ' + MAX_STEPS + ' steps.'};
    return {steps: parsed};
  }
  function reviewRowText(row) {
    const label = (typeof row.name === 'string' && row.name ? row.name : '(unnamed)').slice(0, 100);
    return '#' + (row.index + 1) + ' ' + label + ' — ' + row.status +
      (row.reasons && row.reasons.length ? ': ' + row.reasons.join('; ') : '');
  }
  function importProvenance(row) {
    return 'Imported from pasted native JSON (step ' + (row.index + 1) + ', "' + String(row.name).slice(0, 100) +
      '") — unreviewed source; shape-checked only; accepted by a human reviewer';
  }

  // ---- browser UI -------------------------------------------------------------------------------------------------
  const defaultIo = {
    async getLibrary() {
      const response = await fetch('/scenario-developer/typed-library');
      if (!response.ok) throw Error('The typed action library is unavailable (' + response.status + ')');
      return response.json();
    },
    async searchCatalog(kind, query) {
      const response = await fetch(catalogUrl(kind, query), {headers: {'x-requested-with': 'toolkit-ui'}});
      const body = await response.json().catch(() => ({}));
      if (response.ok) return {ok: true, choices: Array.isArray(body.choices) ? body.choices : []};
      const detail = body && body.detail;
      return {ok: false, message: (typeof detail === 'string' ? detail : 'Catalog search rejected (' + response.status + ')') +
        ' You can still enter an ID by hand.'};
    },
    async reviewImport(steps) {
      const response = await fetch('/scenario-developer/typed-import', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({steps})});
      const body = await response.json().catch(() => ({}));
      if (response.ok) return {ok: true, review: body};
      const detail = body && body.detail;
      return {ok: false, message: (detail && detail.message) || (typeof detail === 'string' ? detail : 'Review rejected (' + response.status + ')')};
    },
    async buildStep(payload) {
      const response = await fetch('/scenario-developer/typed-step', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      const body = await response.json().catch(() => ({}));
      if (response.ok) return {ok: true, step: body};
      const detail = body && body.detail;
      return {ok: false, message: (detail && detail.message) || 'Rejected (' + response.status + ')',
        part: detail && detail.part};
    },
  };

  function mount(container, io = defaultIo, doc = document) {
    const el = (tag, cls, text) => {
      const node = doc.createElement(tag);
      if (cls) node.className = cls;
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const field = (label, control) => {
      const wrap = el('label', 'sd-field');
      wrap.append(doc.createTextNode(label), control);
      return wrap;
    };
    const state = {templates: [], entries: [], built: null, request: 0, timer: null, picked: {action: null, expect: null}, review: null};
    const inputs = {action: {}, expect: null};
    container.replaceChildren();

    container.append(el('p', 'sd-warning',
      'Draft native Headless steps only. They are not saved with the scenario draft, nothing is sent to a game ' +
      'client, and no oracle or verdict is implied: every step stays UNAPPROVED / UNKNOWN until something ' +
      'independent establishes the outcome.'));
    const select = el('select');
    select.id = 'sd-typed-template';
    const limits = el('p', 'sd-muted');
    const actionBox = el('div'), expectBox = el('div');
    const name = el('input');
    name.id = 'sd-typed-name'; name.type = 'text'; name.maxLength = 100;
    const status = el('p', 'sd-muted', 'Choose a step type.');
    status.id = 'sd-typed-status'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const add = el('button', '', 'Add step');
    add.type = 'button'; add.id = 'sd-typed-add'; add.disabled = true;
    const list = el('ol'); list.id = 'sd-typed-steps-list';
    const output = el('pre'); output.id = 'sd-typed-json'; output.tabIndex = 0;
    const copy = el('button', '', 'Copy JSON'), download = el('a', '', 'Download JSON');
    copy.type = 'button'; copy.id = 'sd-typed-copy'; download.id = 'sd-typed-download';
    const notSteps = el('details'); notSteps.id = 'sd-typed-unsupported'; notSteps.append(el('summary', '', 'Not available as steps'));

    const selected = () => state.templates.find(t => t.id === select.value);

    function numberInput(param, group, key) {
      const input = el('input');
      input.type = param.type === 'finite_number' ? 'text' : 'number';
      if (input.type === 'number') { input.step = '1'; if (param.type === 'int_range') { input.min = param.min; input.max = param.max; } }
      else input.inputMode = 'decimal';
      input.id = 'sd-typed-' + group + '-' + key;
      input.addEventListener('input', schedule);
      return input;
    }

    function pickerBox(param, group, input) {
      const kindLabel = param.picker === 'zone' ? 'zone' : 'NPC';
      const box = el('div', 'sd-muted');
      const query = el('input'); query.type = 'text'; query.maxLength = 64; query.id = 'sd-typed-' + group + '-search';
      const go = el('button', '', 'Search'); go.type = 'button'; go.id = 'sd-typed-' + group + '-search-go';
      const note = el('p', 'sd-muted'); note.setAttribute('role', 'status'); note.id = 'sd-typed-' + group + '-search-note';
      const results = el('ul'); results.id = 'sd-typed-' + group + '-results';
      let sequence = 0;
      async function search() {
        const text = String(query.value).trim(), problem = catalogQueryProblem(text);
        results.replaceChildren();
        if (problem) { note.textContent = problem; return; }
        const mine = ++sequence;
        note.textContent = 'Searching the configured DSP source…';
        let reply;
        try { reply = await io.searchCatalog(param.picker, text); }
        catch (error) { reply = {ok: false, message: 'Catalog search failed: ' + error.message + ' You can still enter an ID by hand.'}; }
        if (mine !== sequence) return; // a newer search superseded this answer
        if (!reply.ok) { note.textContent = reply.message; return; }
        const rows = (reply.choices || []).filter(c => usableCandidate(c, param.picker)).slice(0, 20);
        note.textContent = rows.length
          ? rows.length + ' unverified source candidate' + (rows.length === 1 ? '' : 's') + ' (a bounded search, not a full list). ' +
            'Pick one to fill the ID, or type your own.'
          : 'No match in the configured DSP source. That is not proof the ' + kindLabel + ' does not exist; you can still enter an ID by hand.';
        for (const candidate of rows) {
          const item = el('li'), choice = el('button', '', describeCandidate(candidate));
          choice.type = 'button'; choice.setAttribute('aria-label', 'Use ' + describeCandidate(candidate));
          choice.addEventListener('click', () => {
            input.value = String(candidate.id);
            state.picked[group] = candidate;
            note.textContent = 'Filled from the catalog: ' + provenanceNote(candidate, param.name);
            schedule();
          });
          item.append(choice, el('small', 'sd-muted', ' ' + candidate.source_path));
          results.append(item);
        }
      }
      go.addEventListener('click', search);
      query.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); search(); } });
      box.append(field('Find a ' + kindLabel + ' in the DSP catalog (optional)', query), go, note, results);
      return box;
    }

    function paramControls(param, group) {
      const holder = el('div', 'sd-grid');
      const read = {};
      if (param.type === 'walk_target') {
        for (const key of ['x', 'y', 'z', 'timeout_ms', 'stall_ms']) {
          const input = numberInput({type: 'finite_number'}, group, key);
          holder.append(field(key + (key === 'y' || key.endsWith('_ms') ? ' (optional)' : ''), input));
          read[key] = input;
        }
        return {holder, value: () => composeWalkTarget(Object.fromEntries(Object.entries(read).map(([k, i]) => [k, i.value])))};
      }
      let input;
      if (param.type === 'bool') {
        input = el('select');
        for (const [value, text] of [['', 'choose…'], ['true', 'true'], ['false', 'false']]) {
          const option = el('option', '', text); option.value = value; input.append(option);
        }
        input.id = 'sd-typed-' + group + '-value';
        input.addEventListener('input', schedule);
      } else input = numberInput(param, group, 'value');
      holder.append(field(param.name + ' — ' + param.constraint, input));
      if (param.picker && io.searchCatalog) holder.append(pickerBox(param, group, input));
      return {holder, input, value: () => {
        if (param.type === 'bool') return input.value === '' ? {error: param.name + ' is required'} : {value: input.value === 'true'};
        const parsed = parseNumberText(input.value);
        return parsed === undefined ? {error: param.name + ' is required'} : {value: parsed};
      }};
    }

    function renderTemplate() {
      const template = selected();
      state.built = null; add.disabled = true; state.picked = {action: null, expect: null};
      actionBox.replaceChildren(); expectBox.replaceChildren();
      if (!template) { limits.textContent = ''; return; }
      limits.textContent = 'Tier ' + template.support_tier + ' — shape checked against the pinned native schema; ' +
        'it does not prove the runner dispatches it. Limit: ' + template.limitations;
      inputs.action = paramControls(template.action.param, 'action');
      inputs.expect = paramControls(template.expectation.param, 'expect');
      actionBox.append(el('h4', '', 'Action: ' + template.action.native_key), inputs.action.holder);
      expectBox.append(el('h4', '', 'Check: ' + template.expectation.native_key), inputs.expect.holder);
      name.value = uniqueName(template.label, state.entries.map(e => e.name));
      validate();
    }

    function schedule() {
      state.built = null; add.disabled = true;
      clearTimeout(state.timer);
      state.timer = setTimeout(validate, 150);
    }

    async function validate() {
      const template = selected();
      if (!template) return;
      const mine = ++state.request;
      const action = inputs.action.value(), expectation = inputs.expect.value();
      const problem = action.error || expectation.error;
      if (problem) { status.textContent = problem; return; }
      let result;
      try {
        result = await io.buildStep({template_id: template.id, action_value: action.value, expectation_value: expectation.value});
      } catch (error) { result = {ok: false, message: 'Validation unavailable: ' + error.message}; }
      if (mine !== state.request) return; // a newer edit superseded this answer
      if (result.ok) {
        state.built = result.step;
        status.textContent = 'Valid native draft step (' + result.step.support_tier + '; oracle ' + result.step.oracle_status + ').';
        add.disabled = state.entries.length >= MAX_STEPS;
      } else status.textContent = result.message;
    }

    function renderSteps() {
      list.replaceChildren();
      state.entries.forEach((entry, index) => {
        const item = el('li');
        item.append(el('strong', '', entry.name), doc.createTextNode(' — ' +
          (entry.name === entry.template.label ? describeAction(entry.step) : describeStep(entry.template, entry.step))));
        item.append(el('small', 'sd-muted', ' [' + entry.step.support_tier + ' · oracle ' + entry.step.oracle_status +
          ' · verdict ' + entry.step.verdict + ']'));
        for (const note of entry.provenance || []) item.append(el('div', 'sd-muted', 'Source: ' + note));
        const controls = el('span', 'sd-controls');
        for (const [label, act] of [['Up', () => move(index, -1)], ['Down', () => move(index, 1)], ['Remove', () => remove(index)]]) {
          const button = el('button', '', label); button.type = 'button';
          button.setAttribute('aria-label', label + ' ' + entry.name);
          button.addEventListener('click', act); controls.append(button);
        }
        item.append(controls); list.append(item);
      });
      const text = state.entries.length ? nativeJson(state.entries) : 'No steps yet.';
      output.textContent = text;
      copy.disabled = !state.entries.length;
      download.hidden = !state.entries.length;
      if (state.entries.length) {
        if (download.href && download.href.startsWith('blob:')) URL.revokeObjectURL(download.href);
        download.href = URL.createObjectURL(new Blob([text + '\n'], {type: 'application/json'}));
        download.download = 'native-scenario-draft.json';
      }
    }
    const move = (index, delta) => { state.entries = moveItem(state.entries, index, delta); renderSteps(); };
    const remove = index => { state.entries = state.entries.filter((_, i) => i !== index); renderSteps(); validate(); };

    add.addEventListener('click', () => {
      const template = selected();
      if (!template || !state.built || state.entries.length >= MAX_STEPS) return;
      const stepName = uniqueName(name.value, state.entries.map(e => e.name));
      const provenance = [];
      for (const [group, part] of [['action', 'action'], ['expect', 'expectation']]) {
        const picked = state.picked[group], control = inputs[group];
        if (picked && control && control.input && parseNumberText(control.input.value) === picked.id)
          provenance.push(provenanceNote(picked, template[part].param.name));
      }
      state.entries = state.entries.concat([{name: stepName, template, step: clone(state.built), provenance}]);
      renderSteps();
      name.value = uniqueName(template.label, state.entries.map(e => e.name));
      status.textContent = 'Added "' + stepName + '". Edit the values to add another.';
    });
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(output.textContent); status.textContent = 'Copied the native JSON.'; }
      catch (_error) { status.textContent = 'Copy is unavailable here; select the JSON text and copy it.'; }
    });
    select.addEventListener('change', renderTemplate);

    // ---- import: pasted native JSON is reviewed, and only steps a person accepts join the list
    const importBox = el('details'); importBox.id = 'sd-typed-import';
    importBox.append(el('summary', '', 'Import native JSON for review (for example from an agent or a scenario file)'));
    const importText = el('textarea'); importText.id = 'sd-typed-import-text'; importText.rows = 8;
    importText.setAttribute('aria-label', 'Native scenario JSON');
    const importGo = el('button', '', 'Review import'); importGo.type = 'button'; importGo.id = 'sd-typed-import-go';
    const importNote = el('p', 'sd-muted'); importNote.id = 'sd-typed-import-note'; importNote.setAttribute('role', 'status');
    const reviewList = el('ul'); reviewList.id = 'sd-typed-import-review';
    const acceptAll = el('button', '', 'Select all supported'); acceptAll.type = 'button'; acceptAll.id = 'sd-typed-import-all';
    const importAdd = el('button', '', 'Add accepted steps'); importAdd.type = 'button'; importAdd.id = 'sd-typed-import-add';
    importAdd.disabled = true; acceptAll.disabled = true;
    const importControls = el('div', 'sd-controls'); importControls.append(acceptAll, importAdd);
    importBox.append(el('p', 'sd-muted', 'Imported steps come from an unreviewed source. A passing check only means the step has a reviewed ' +
      'shape; it does not make the step correct or establish any outcome. Nothing is added until you accept it.'),
      importText, importGo, importNote, reviewList, importControls);
    const accepts = [];
    function syncImportButtons() { importAdd.disabled = !accepts.some(a => a.checkbox.checked); }
    function clearReview() {
      state.review = null; accepts.length = 0; reviewList.replaceChildren();
      acceptAll.disabled = true; importAdd.disabled = true;
    }
    importText.addEventListener('input', () => { if (state.review) { clearReview(); importNote.textContent = 'The text changed. Review it again.'; } });
    importGo.addEventListener('click', async () => {
      clearReview();
      const parsed = parseNativeText(importText.value);
      if (parsed.error) { importNote.textContent = parsed.error; return; }
      importNote.textContent = 'Reviewing…';
      let result;
      try { result = await io.reviewImport(parsed.steps); }
      catch (error) { result = {ok: false, message: 'Review unavailable: ' + error.message}; }
      if (!result.ok) { importNote.textContent = result.message; return; }
      state.review = result.review;
      const counts = result.review.counts;
      importNote.textContent = counts.SUPPORTED + ' supported, ' + counts.UNSUPPORTED + ' unsupported, ' + counts.INVALID +
        ' invalid. Tick the steps you accept; none are accepted automatically.';
      for (const row of result.review.steps) {
        const item = el('li');
        if (row.status === 'SUPPORTED') {
          const checkbox = el('input'); checkbox.type = 'checkbox';
          checkbox.setAttribute('aria-label', 'Accept ' + row.name);
          checkbox.addEventListener('change', syncImportButtons);
          item.append(checkbox, doc.createTextNode(' '));
          accepts.push({checkbox, row});
        }
        item.append(el('strong', '', reviewRowText(row)));
        if (row.status === 'SUPPORTED') item.append(el('div', 'sd-muted', describeAction(row.step)));
        reviewList.append(item);
      }
      acceptAll.disabled = !accepts.length;
    });
    acceptAll.addEventListener('click', () => { for (const a of accepts) a.checkbox.checked = true; syncImportButtons(); });
    importAdd.addEventListener('click', () => {
      const chosen = accepts.filter(a => a.checkbox.checked).map(a => a.row);
      if (!chosen.length) return;
      let added = 0;
      for (const row of chosen) {
        if (state.entries.length >= MAX_STEPS) break;
        const template = state.templates.find(t => t.id === row.template_id);
        if (!template) continue; // the library changed since the review; nothing is guessed
        state.entries = state.entries.concat([{name: uniqueName(row.name, state.entries.map(e => e.name)), template,
          step: clone(row.step), provenance: [importProvenance(row)]}]);
        added++;
      }
      renderSteps(); clearReview(); importText.value = '';
      importNote.textContent = 'Added ' + added + ' of ' + chosen.length + ' accepted step' + (chosen.length === 1 ? '' : 's') +
        '. They are unapproved drafts; review each one.';
    });

    const exportRow = el('div', 'sd-controls');
    exportRow.append(copy, download);
    container.append(field('Step type', select), limits, actionBox, expectBox, field('Step name', name), status, add,
      el('h3', '', 'Steps'), list, el('h3', '', 'Native Headless JSON (draft)'), output, exportRow, importBox, notSteps);

    return io.getLibrary().then(registry => {
      state.templates = registry.templates.filter(t => t.kind === 'action_expectation');
      for (const template of state.templates) {
        const option = el('option', '', template.label); option.value = template.id; select.append(option);
      }
      const readbacks = registry.templates.filter(t => t.kind === 'observation');
      const unsupported = el('ul');
      for (const template of readbacks) {
        unsupported.append(el('li', '', template.label + ' — a Toolkit readback (' + template.readback.route +
          '), not a Headless step; it has no native action or check. ' + template.limitations));
      }
      notSteps.append(unsupported);
      renderSteps(); renderTemplate();
      return state;
    }).catch(error => { status.textContent = 'Typed step builder unavailable: ' + error.message; });
  }

  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', () => {
      const container = document.getElementById('sd-typed-root');
      if (container) mount(container);
    });
  }
  return {parseNumberText, composeWalkTarget, uniqueName, nativeScenario, nativeJson, describeStep, describeAction, moveItem, parseNativeText, reviewRowText, importProvenance,
    catalogQueryProblem, catalogUrl, usableCandidate, describeCandidate, provenanceNote, mount};
});
