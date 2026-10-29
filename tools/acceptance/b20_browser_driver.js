// Paste into the browser console (or a javascript_tool call) on /scenario-developer.
// Prereq: fixtures from make_b20_fixtures.py served same-origin at /static/b20fx/<case>/ (untracked
// gui/static/b20fx in a throwaway worktree). Synthetic data only; the viewer is read-only.
const d = document.getElementById('sd-readiness-handoff'); d.open = true;
window.__posts = [];
if (!window.__of) window.__of = window.fetch;            // capture the original ONCE; reload clears globals
window.fetch = function (u, o) {
  if (o && o.method && o.method !== 'GET') window.__posts.push({ u: String(u), m: o.method });
  return window.__of.apply(this, arguments);
};
window.__sel = async (side, c, file) => {               // side 0 = review, 1 = sidecar
  const inp = document.getElementById('sd-readiness-viewer').querySelectorAll('input[type=file]')[side];
  const t = await (await window.__of('/static/b20fx/' + c + '/' + file)).text();
  const dt = new DataTransfer(); dt.items.add(new File([t], file, { type: 'application/json' }));
  inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true }));
};
window.__run = async (c) => {
  window.__posts = [];
  await __sel(0, c, 'original_reviewed.json'); await __sel(1, c, 'readiness_sidecar.json');
  const v = document.getElementById('sd-readiness-viewer');
  v.querySelector('button').click(); await new Promise(r => setTimeout(r, 1500));
  return { case: c, posts: window.__posts.map(p => p.m + ' ' + p.u), text: v.innerText.split('\n').slice(4).join(' | ').slice(0, 700) };
};
// Example: for (const c of ['01_matching_pair','06_mismatch_identity_review','09_invalid_json_review']) console.log(await __run(c));
