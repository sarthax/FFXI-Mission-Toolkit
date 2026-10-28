/* Review controls on a Test catalog entry (#1410). The server renders only the steps the revision may take next and
 * stays the authority: it re-checks the stored revision and refuses anything out of order. This file only sends the
 * request the page describes and reports the answer; it adds no rule of its own beyond asking for a reviewer note
 * before a publish request is sent. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.CatalogEntryReview = api;
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';
  const NOTE_MAX = 300;

  // The request for one review step, or an {error} the person can act on before anything is sent.
  function requestFor(data, note) {
    const trimmed = String(note || '').trim();
    if (trimmed.length > NOTE_MAX) return {error: 'The note is longer than ' + NOTE_MAX + ' characters.'};
    if (data.state === 'PUBLISHED' && !trimmed) return {error: 'Publishing records a reviewer decision. Write a note first.'};
    const revision = Number(data.revision);
    if (!Number.isInteger(revision) || revision < 1) return {error: 'Unknown revision.'};
    return {body: {feature_id: data.feature, case_id: data.case, revision, state: data.state, note: trimmed}};
  }

  async function send(request, token) {
    const response = await fetch('/feature-testing/test-catalog/state', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-Requested-With': 'toolkit-ui', 'X-Test-Operator-Token': token},
      body: JSON.stringify(request.body)});
    const value = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = value && value.detail;
      throw new Error(typeof detail === 'string' ? detail : 'HTTP ' + response.status);
    }
    return value;
  }

  function wire(doc) {
    const result = doc.getElementById('ce-result');
    let pending = false;
    for (const button of doc.querySelectorAll('[data-catalog-action]')) {
      button.addEventListener('click', async () => {
        if (pending) return;
        const built = requestFor(button.dataset, doc.getElementById('ce-note').value);
        if (built.error) { result.textContent = built.error; return; }
        if (button.dataset.confirm && !window.confirm(button.dataset.confirm)) { result.textContent = 'Cancelled; nothing changed.'; return; }
        pending = true; for (const b of doc.querySelectorAll('[data-catalog-action]')) b.disabled = true;
        try {
          const done = await send(built, doc.getElementById('ce-token').value);
          result.textContent = 'Recorded ' + done.state + ' for r' + done.revision + '. Reloading…';
          const url = new URL(window.location.href); url.searchParams.set('revision', String(done.revision));
          window.location.assign(url.toString());
        } catch (error) {
          result.textContent = 'Not recorded: ' + error.message;
          pending = false; for (const b of doc.querySelectorAll('[data-catalog-action]')) b.disabled = false;
        }
      });
    }
  }

  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', () => wire(document));
  }
  return {requestFor, NOTE_MAX};
});
