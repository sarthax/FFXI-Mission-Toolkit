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

  function describeStep(template, step) {
    const action = Object.keys(step.do)[0], expect = Object.keys(step.expect)[0];
    return template.label + ' — ' + action + ' ' + JSON.stringify(step.do[action]) +
      ', then check ' + expect + ' = ' + JSON.stringify(step.expect[expect]);
  }

  function moveItem(list, index, delta) {
    const target = index + delta;
    if (index < 0 || index >= list.length || target < 0 || target >= list.length) return list.slice();
    const next = list.slice();
    [next[index], next[target]] = [next[target], next[index]];
    return next;
  }

  // ---- browser UI -------------------------------------------------------------------------------------------------
  const defaultIo = {
    async getLibrary() {
      const response = await fetch('/scenario-developer/typed-library');
      if (!response.ok) throw Error('The typed action library is unavailable (' + response.status + ')');
      return response.json();
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
    const state = {templates: [], entries: [], built: null, request: 0, timer: null};
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
    const notSteps = el('details'); notSteps.append(el('summary', '', 'Not available as steps'));

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
      return {holder, value: () => {
        if (param.type === 'bool') return input.value === '' ? {error: param.name + ' is required'} : {value: input.value === 'true'};
        const parsed = parseNumberText(input.value);
        return parsed === undefined ? {error: param.name + ' is required'} : {value: parsed};
      }};
    }

    function renderTemplate() {
      const template = selected();
      state.built = null; add.disabled = true;
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
        item.append(el('strong', '', entry.name), doc.createTextNode(' — ' + describeStep(entry.template, entry.step)));
        item.append(el('small', 'sd-muted', ' [' + entry.step.support_tier + ' · oracle ' + entry.step.oracle_status +
          ' · verdict ' + entry.step.verdict + ']'));
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
      state.entries = state.entries.concat([{name: stepName, template, step: clone(state.built)}]);
      renderSteps();
      name.value = uniqueName(template.label, state.entries.map(e => e.name));
      status.textContent = 'Added "' + stepName + '". Edit the values to add another.';
    });
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(output.textContent); status.textContent = 'Copied the native JSON.'; }
      catch (_error) { status.textContent = 'Copy is unavailable here; select the JSON text and copy it.'; }
    });
    select.addEventListener('change', renderTemplate);

    const exportRow = el('div', 'sd-controls');
    exportRow.append(copy, download);
    container.append(field('Step type', select), limits, actionBox, expectBox, field('Step name', name), status, add,
      el('h3', '', 'Steps'), list, el('h3', '', 'Native Headless JSON (draft)'), output, exportRow, notSteps);

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
  return {parseNumberText, composeWalkTarget, uniqueName, nativeScenario, nativeJson, describeStep, moveItem, mount};
});
