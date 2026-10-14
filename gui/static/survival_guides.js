(function () {
  var sum = document.getElementById('sg-sum'), body = document.getElementById('sg-body');
  if (!body) return;
  var COL = {ok: '#1e9e6a', warn: '#d68910', bad: '#c0392b', idle: '#888'};
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function load() {
    fetch('/domains/survival_guides/overview.json').then(function (r) { return r.json(); }).then(function (d) {
      var s = d.summary;
      sum.textContent = s.total + ' guides · ' + s.dat_verified + ' DAT-verified · ' + (s.live == null ? 'live DB unreachable' : s.live + ' live') +
        ' · ' + s.zero_pos + ' at zero position · ' + s.in_game_ok + ' marked ok in game · ' + s.bad + ' bad';
      var h = '<table class="table"><tr><th>Zone</th><th>npc id</th><th>x</th><th>y</th><th>z</th><th>pos src</th><th>DAT</th><th>Live</th><th>In game</th><th>Note</th></tr>';
      d.guides.forEach(function (g) {
        var opts = ['idle', 'ok', 'warn', 'bad'].map(function (o) { return '<option' + (o === g.validation ? ' selected' : '') + '>' + o + '</option>'; }).join('');
        h += '<tr><td>' + g.zoneid + ' ' + esc(g.zone) + '</td><td>' + g.id + '</td><td>' + g.x + '</td><td>' + g.y + '</td><td>' + g.z + '</td><td>' + esc(g.pos_source) +
          (g.zero_pos ? ' <b style="color:#c0392b">ZERO</b>' : '') + '</td><td>' + (g.dat_verified ? '✓' : '<span class="muted">–</span>') + '</td><td>' +
          (g.live == null ? '?' : g.live ? '✓' : '<b style="color:#c0392b">missing</b>') + '</td><td><select data-id="' + g.id + '" style="color:' + COL[g.validation] + '">' + opts +
          '</select></td><td><input data-note="' + g.id + '" value="' + esc(g.vnote) + '" size="28"></td></tr>';
      });
      body.innerHTML = h + '</table>';
      body.querySelectorAll('select').forEach(function (el) { el.onchange = function () { save(el.dataset.id); }; });
      body.querySelectorAll('input[data-note]').forEach(function (el) { el.onchange = function () { save(el.dataset.note); }; });
    });
  }
  function save(id) {
    var st = body.querySelector('select[data-id="' + id + '"]').value, note = body.querySelector('input[data-note="' + id + '"]').value;
    fetch('/domains/survival_guides/mark', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id: id, state: st, note: note})}).then(load);
  }
  load();
})();
