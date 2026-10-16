"""Static HTML for the GM Command Center (category tabs, command list, entry pane, ID picker)."""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Server · GM Command Center</title>
<style>
:root{font-family:system-ui,sans-serif;color-scheme:dark;--bg:#12151a;--pn:#1a1f27;--bd:#2c333d;--tx:#dde3ea;--mu:#8b97a6;--ac:#5aa9ff}
body{margin:0;background:var(--bg);color:var(--tx);font-size:14px}
header{padding:10px 16px;border-bottom:1px solid var(--bd)}h1{margin:0;font-size:17px}
.note{color:var(--mu);font-size:12px;margin-top:3px}
#tabs{display:flex;gap:2px;flex-wrap:wrap;padding:8px 16px 0;border-bottom:1px solid var(--bd)}
#tabs button{background:none;border:1px solid transparent;border-bottom:0;color:var(--mu);padding:6px 11px;cursor:pointer;border-radius:6px 6px 0 0}
#tabs button.on{background:var(--pn);color:var(--tx);border-color:var(--bd)}
#tabs b{font-weight:400;opacity:.6;margin-left:4px}
main{display:grid;grid-template-columns:290px 1fr;height:calc(100vh - 112px)}
#list{border-right:1px solid var(--bd);overflow:auto;padding:8px}
#list input{width:100%;box-sizing:border-box;margin-bottom:6px}
.cmd{display:block;width:100%;text-align:left;background:none;border:0;color:var(--tx);padding:6px 8px;border-radius:5px;cursor:pointer}
.cmd:hover,.cmd.on{background:var(--pn)}.cmd.on{outline:1px solid var(--ac)}
.cmd small{display:block;color:var(--mu);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#pane{overflow:auto;padding:14px 18px}
input,select,button{font:inherit;background:var(--pn);color:var(--tx);border:1px solid var(--bd);border-radius:5px;padding:5px 8px}
button{cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}
.p{margin:10px 0;max-width:640px}.p label{display:block;font-size:12px;color:var(--mu);margin-bottom:3px}
.p .row{display:flex;gap:6px}.p .row input.v{flex:1}.req{color:#f0a060}
.res{border:1px solid var(--bd);background:var(--pn);border-radius:5px;margin-top:4px;max-height:200px;overflow:auto}
.res div{padding:4px 8px;cursor:pointer;display:flex;gap:10px}.res div:hover{background:#242c37}.res i{color:var(--ac);font-style:normal;min-width:80px}
pre{background:var(--pn);border:1px solid var(--bd);padding:10px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}
.mu{color:var(--mu);font-size:12px}
</style></head><body>
<header><h1>GM Command Center</h1>
<div class="note">No command transmission is enabled. Build a command, look up IDs from the active server, then copy it into the game chat.</div></header>
<div id="tabs"></div>
<main><div id="list"><input id="search" type="search" placeholder="Search all commands…" aria-label="Search commands"><div id="items"></div></div>
<div id="pane"><p class="mu">Pick a category, then a command.</p></div></main>
<script>
const $=id=>document.getElementById(id);let DATA=[],CATS=[],cat='',cur=null;
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function init(){
  const r=await fetch('/server/gm/commands');
  if(!r.ok){$('pane').textContent='Cannot load commands: '+r.status;return}
  const j=await r.json();DATA=j.commands;CATS=j.categories.concat(DATA.some(c=>c.category==='Other')?['Other']:[]);
  cat=CATS[0];tabs();list();
}
function tabs(){
  $('tabs').innerHTML=CATS.map(c=>`<button data-c="${esc(c)}" class="${c===cat?'on':''}">${esc(c)}<b>${DATA.filter(x=>x.category===c).length}</b></button>`).join('');
}
$('tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;cat=b.dataset.c;$('search').value='';tabs();list()};
$('search').oninput=list;
function list(){
  const q=$('search').value.trim().toLowerCase();
  const rows=DATA.filter(c=>q?(c.name+' '+c.description+' '+c.usage).toLowerCase().includes(q):c.category===cat);
  $('items').innerHTML=rows.map(c=>`<button class="cmd ${cur&&cur.name===c.name?'on':''}" data-n="${esc(c.name)}">!${esc(c.name)}<small>${esc(q?c.category+' · ':'')}${esc(c.description)}</small></button>`).join('')||'<p class="mu">No matches.</p>';
}
$('items').onclick=e=>{const b=e.target.closest('.cmd');if(!b)return;cur=DATA.find(c=>c.name===b.dataset.n);list();pane()};
function pane(){
  const c=cur;
  $('pane').innerHTML=`<h2 style="margin:0">!${esc(c.name)}</h2><div class="mu">${esc(c.category)} · permission ${c.permission} · ${esc(c.source_path)}</div>
  <p>${esc(c.description)}</p><div class="mu">Usage: <code>${esc(c.usage)}</code> &nbsp; (<span class="req">*</span> required, others optional)</div>
  ${c.params.map((p,i)=>`<div class="p"><label>${esc(p.label)}${p.required?' <span class="req">*</span>':''} <span class="mu">(${p.type==='i'?'number':p.type==='b'?'auto-translate':'text'})</span></label>
  <div class="row"><input class="v" data-i="${i}" autocomplete="off">${p.lookup?`<input class="s" data-i="${i}" data-k="${p.lookup}" placeholder="Search ${p.lookup} by name or id…" style="width:230px">`:''}</div>
  ${p.lookup?`<div class="res" data-r="${i}" hidden></div>`:''}</div>`).join('')}
  <pre id="out"></pre>
  <button id="copy">Copy command</button> <button disabled title="No Toolkit-to-game command transport exists yet; the native plugin only supports warp/speed.">Send to game</button>
  <p class="mu">Send is disabled: no command transmission is enabled.</p>`;
  preview();
}
function cmdText(){
  const vals=[...document.querySelectorAll('#pane input.v')].map(i=>i.value.trim());
  while(vals.length&&!vals[vals.length-1])vals.pop();
  const gaps=cur.params.filter((p,i)=>i<vals.length&&!vals[i]).map(p=>p.label);
  return {text:'!'+cur.name+(vals.length?' '+vals.map(v=>v||'0').join(' '):''),
    warn:[...cur.params.filter((p,i)=>p.required&&!vals[i]).map(p=>p.label+' is required'),...gaps.map(m=>m+' left blank (sent as 0)')]};
}
function preview(){const r=cmdText();$('out').textContent=r.text+(r.warn.length?'\n\n⚠ '+r.warn.join('\n⚠ '):'')}
let timer;
$('pane').addEventListener('input',e=>{
  const t=e.target;
  if(t.classList.contains('v'))preview();
  if(t.classList.contains('s')){clearTimeout(timer);timer=setTimeout(()=>search(t),180)}
});
async function search(t){
  const box=document.querySelector(`.res[data-r="${t.dataset.i}"]`);
  const r=await fetch(`/server/gm/lookup?kind=${t.dataset.k}&q=${encodeURIComponent(t.value)}&limit=30`);
  if(!r.ok){box.hidden=false;box.innerHTML='<div>Lookup unavailable ('+r.status+')</div>';return}
  const j=await r.json();box.hidden=false;
  box.innerHTML=j.results.map(x=>`<div data-id="${x.id}"><i>${x.id}</i><span>${esc(x.name)}</span></div>`).join('')||'<div>No results</div>';
}
$('pane').addEventListener('click',e=>{
  const d=e.target.closest('.res div[data-id]');
  if(d){const box=d.parentElement,i=box.dataset.r;document.querySelector(`input.v[data-i="${i}"]`).value=d.dataset.id;box.hidden=true;preview();return}
  if(e.target.id==='copy'){const r=cmdText();navigator.clipboard.writeText(r.text);e.target.textContent='Copied';setTimeout(()=>e.target.textContent='Copy command',1200)}
});
init();
</script></body></html>"""
