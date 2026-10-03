(() => {
  const ENVIRONMENTS = ['live', 'test', 'dev', 'backup', 'other'];
  const FAMILIES = ['auto', 'lsb', 'topaz', 'dsp'];

  function fill(select, values) {
    if (!select || select.options.length) return;
    select.innerHTML = values
      .map(value => `<option value="${value}">${value.toUpperCase()}</option>`)
      .join('');
  }

  function ensureProfileSelectors() {
    fill(document.getElementById('envEnvironment'), ENVIRONMENTS);
    fill(document.getElementById('envFamily'), FAMILIES);
  }

  ensureProfileSelectors();
  const observer = new MutationObserver(ensureProfileSelectors);
  observer.observe(document.body, {childList: true, subtree: true});
})();
