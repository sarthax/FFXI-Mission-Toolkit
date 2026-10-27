/* Scenario validation 422 presentation only; never writes or normalizes input. */
(function (root) {
  'use strict';
  const fieldIds = new Set(['sd-purpose', 'sd-rationale', 'sd-given', 'sd-when',
    'sd-then', 'sd-gaps', 'sd-advanced-json']);
  let marked = [];

  function clear() {
    for (const id of marked) {
      const field = root.document.getElementById(id);
      if (field) field.removeAttribute('aria-invalid');
    }
    marked = [];
    const container = root.document.getElementById('sd-validation-summary');
    if (container) { container.replaceChildren(); container.hidden = true; }
  }

  function show(errors) {
    clear();
    const container = root.document.getElementById('sd-validation-summary');
    if (!container || !Array.isArray(errors) || !errors.length) return false;
    const safe = errors.slice(0, 12).filter(item =>
      item && typeof item.message === 'string' && typeof item.field === 'string');
    if (!safe.length) return false;
    container.hidden = false;
    const heading = root.document.createElement('strong');
    heading.textContent = safe.length + ' field issue' + (safe.length === 1 ? '' : 's') +
      ' — edit the fields below and validate again. Unsaved input was preserved.';
    container.append(heading);
    const list = root.document.createElement('ul');
    for (const error of safe) {
      const li = root.document.createElement('li');
      const name = root.document.createElement('strong');
      name.textContent = error.field + (error.required ? ' (required)' : '') + ': ';
      li.append(name);
      const message = root.document.createElement('span');
      message.textContent = error.message;
      li.append(message);
      if (fieldIds.has(error.control_id)) {
        const field = root.document.getElementById(error.control_id);
        if (field) {
          field.setAttribute('aria-invalid', 'true');
          marked.push(error.control_id);
        }
      }
      list.append(li);
    }
    container.append(list);
    // Keyboard and screen-reader users land on the summary, not the Validate button.
    container.setAttribute('tabindex', '-1');
    if (typeof container.focus === 'function') container.focus();
    return true;
  }

  root.ScenarioValidationFeedback = {show, clear};
})(typeof window === 'undefined' ? globalThis : window);
