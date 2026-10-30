/* Workspace dropdowns for the top bar.
 * One shared fixed-position panel (so the horizontally scrolling workspace strip never clips
 * it) lists every section of a workspace, with a filter box and starred favorites. The wheel
 * is handled explicitly so the list scrolls with the mouse wherever the pointer is. */
(function () {
  var dataEl = document.getElementById("shell-nav-data");
  if (!dataEl) return;
  var spaces;
  try { spaces = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var bar = document.getElementById("app-shell");
  var panel = document.createElement("div");
  panel.className = "ws-panel";
  panel.hidden = true;
  panel.setAttribute("role", "menu");
  document.body.appendChild(panel);
  var current = null, filter = "";

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function links(ws) {
    var out = [];
    (ws.sections || []).forEach(function (s) {
      if (s.children) s.children.forEach(function (c) { if (c.href) out.push({ group: s.label, label: c.label, href: c.href }); });
      else if (s.href) out.push({ group: "", label: s.label, href: s.href });
    });
    return out;
  }
  function row(l) {
    var fav = window.MTFav && window.MTFav.has(l.href);
    return '<div class="ws-row"><a class="ws-link" role="menuitem" href="' + esc(l.href) + '">' + esc(l.label) + "</a>" +
      '<button type="button" class="ws-star' + (fav ? " on" : "") + '" data-href="' + esc(l.href) + '" data-label="' +
      esc(l.label) + '" aria-pressed="' + (fav ? "true" : "false") + '" title="' + (fav ? "Remove from favorites" : "Add to favorites") + '">' +
      (fav ? "★" : "☆") + "</button></div>";
  }
  function render() {
    if (!current) return;
    var q = filter.trim().toLowerCase(), all = links(current);
    var shown = q ? all.filter(function (l) { return (l.label + " " + l.group).toLowerCase().indexOf(q) >= 0; }) : all;
    var html = '<input class="ws-filter" type="search" placeholder="Filter ' + esc(current.name) + '…" value="' + esc(filter) + '" aria-label="Filter links">';
    var favs = window.MTFav ? window.MTFav.list() : [];
    if (favs.length && !q) {
      html += '<div class="ws-group">Favorites</div>' + favs.map(row).join("");
    }
    var last = null;
    shown.forEach(function (l) {
      if (l.group !== last) { html += l.group ? '<div class="ws-group">' + esc(l.group) + "</div>" : (last === null ? "" : '<div class="ws-group">&nbsp;</div>'); last = l.group; }
      html += row(l);
    });
    if (!shown.length) html += '<div class="ws-empty">No matching links.</div>';
    var keep = panel.scrollTop;
    panel.innerHTML = html;
    panel.scrollTop = keep;
    var f = panel.querySelector(".ws-filter");
    if (f && filter) { f.focus(); f.setSelectionRange(filter.length, filter.length); }
  }
  function close() { panel.hidden = true; current = null; filter = ""; document.querySelectorAll(".ws-caret[aria-expanded=true]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); }); }
  function open(btn, ws) {
    current = ws; filter = ""; render();
    panel.hidden = false;
    var r = btn.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 16);
    panel.style.width = w + "px";
    panel.style.left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + "px";
    panel.style.top = bar.getBoundingClientRect().bottom + 4 + "px";
    panel.style.maxHeight = "calc(100vh - " + (bar.getBoundingClientRect().bottom + 12) + "px)";
    panel.scrollTop = 0;
    btn.setAttribute("aria-expanded", "true");
  }
  document.querySelectorAll(".ws-caret").forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      var ws = spaces.find(function (s) { return s.name === btn.dataset.ws; });
      if (!ws) return;
      if (current === ws && !panel.hidden) close(); else { close(); open(btn, ws); }
    });
  });
  panel.addEventListener("input", function (ev) {
    if (ev.target.classList.contains("ws-filter")) { filter = ev.target.value; render(); }
  });
  panel.addEventListener("click", function (ev) {
    var star = ev.target.closest(".ws-star");
    if (star) { ev.preventDefault(); window.MTFav && window.MTFav.toggle(star.dataset.href, star.dataset.label); render(); }
  });
  panel.addEventListener("wheel", function (ev) {
    if (panel.scrollHeight <= panel.clientHeight) { ev.preventDefault(); return; }
    panel.scrollTop += ev.deltaMode === 1 ? ev.deltaY * 16 : ev.deltaY;
    ev.preventDefault(); /* never let the page behind scroll while the list is open */
  }, { passive: false });
  document.addEventListener("click", function (ev) { if (!panel.hidden && !panel.contains(ev.target)) close(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") close(); });
  window.addEventListener("resize", close);
  document.addEventListener("mt-favorites-changed", function () { if (!panel.hidden) render(); });
})();
