/* Per-browser favorites for the shell and the Domains page.
 * Stored in localStorage only (a viewer convenience); every access is guarded so a blocked
 * or cleared store just means "no favorites" instead of a broken page. */
(function () {
  var KEY = "mt.favorites.v1";
  function read() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(v) ? v.filter(function (x) { return x && typeof x.href === "string"; }) : [];
    } catch (e) { return []; }
  }
  function write(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list)); return true; } catch (e) { return false; }
  }
  var api = {
    list: read,
    has: function (href) { return read().some(function (x) { return x.href === href; }); },
    toggle: function (href, label) {
      var list = read(), i = list.findIndex(function (x) { return x.href === href; });
      if (i >= 0) list.splice(i, 1); else list.push({ href: href, label: label || href });
      write(list);
      document.dispatchEvent(new CustomEvent("mt-favorites-changed"));
      return i < 0;
    }
  };
  window.MTFav = api;
  window.addEventListener("storage", function (ev) {
    if (ev.key === KEY) document.dispatchEvent(new CustomEvent("mt-favorites-changed"));
  });
})();
