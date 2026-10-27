/* Scenario validation 422 presentation only; never writes or normalizes input. */
(function (root) {
  'use strict';
  const fieldIds = new Set(['sd-purpose', 'sd-rationale', 'sd-given', 'sd-when',
    'sd-then', 'sd-gaps', 'sd-advanced-json']);
  let marked = [];
  // control id -> its aria-describedby before errors were attached (null if none).
  let described = new Map();

  function clear() {
    for (const id of marked) {
      const field = root.document.getElementById(id);
      if (field) {
        field.removeAttribute('aria-invalid');
        const original = described.get(id);
        if (original) field.setAttribute('aria-describedby', original);
        else field.removeAttribute('aria-describedby');
      }
    }
    marked = [];
    described = new Map();
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
    const messageIds = new Map();
    safe.forEach((error, index) => {
      const li = root.document.createElement('li');
      li.id = 'sd-validation-error-' + index;
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
          if (!marked.includes(error.control_id)) {
            marked.push(error.control_id);
            described.set(error.control_id, field.getAttribute
              ? field.getAttribute('aria-describedby') : null);
          }
          // Tie each field to its own message(s) so screen readers announce them on focus.
          const ids = messageIds.get(error.control_id) || [];
          ids.push(li.id);
          messageIds.set(error.control_id, ids);
        }
      }
      list.append(li);
    });
    for (const [controlId, ids] of messageIds) {
      const field = root.document.getElementById(controlId);
      const original = described.get(controlId);
      field.setAttribute('aria-describedby', (original ? original + ' ' : '') + ids.join(' '));
    }
    container.append(list);
    // Keyboard and screen-reader users land on the summary, not the Validate button.
    container.setAttribute('tabindex', '-1');
    if (typeof container.focus === 'function') container.focus();
    return true;
  }

  root.ScenarioValidationFeedback = {show, clear};
})(typeof window === 'undefined' ? globalThis : window);
