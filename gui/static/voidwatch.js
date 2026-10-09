(function(){
var O=null,OF={officers:[],areas:[],states:[]},sel={path:'',tier:''};
var $=function(i){return document.getElementById(i);};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function num(n){return n==null?'?':Number(n).toLocaleString();}
function jget(u){return fetch(u).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
function load(){
 jget('/domains/voidwatch/officers.json').catch(function(){return {officers:[],areas:[],states:[]};}).then(function(o){OF=o;return jget('/domains/voidwatch/overview.json');}).then(function(d){O=d;offTable();npcFix();backlogTable();warpTable();$('vw-srv').textContent='Server: '+d.server.name+' ('+d.server.environment+') '+d.server.root;graph();table();})
 .catch(function(e){$('vw-sum').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});
}
function bucket(p,t){return O.nms.filter(function(x){return x.path===p&&x.tier===t;});}
function graph(){
 var P=Object.keys(O.paths),T=O.tiers,cw=150,rh=84,x0=70,yo=90,y0=174,W=x0+P.length*cw+20,H=y0+T.length*rh,s='',cx={};
 var un=O.nms.filter(function(x){return !x.path||!x.tier||P.indexOf(x.path)<0||T.indexOf(x.tier)<0;});
 s+='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;max-width:'+W+'px;font:12px sans-serif" role="img" aria-label="Voidwatch path and tier progression">';
 s+='<defs><marker id="vwa" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="currentColor" opacity=".6"/></marker></defs>';
 var mon=!sel.path&&!sel.tier;
 s+='<g class="vwp" data-p="" style="cursor:pointer"><rect x="4" y="4" width="62" height="40" rx="8" fill="currentColor" fill-opacity=".12" stroke="currentColor" stroke-width="'+(mon?3:1.5)+'"/><text x="35" y="21" text-anchor="middle" font-weight="700" fill="currentColor">All</text><text x="35" y="36" text-anchor="middle" font-size="9" fill="currentColor" opacity=".7">'+O.nms.length+' VWNM</text><title>Show every Voidwatch NM</title></g>';
 s+='<g class="vwoff" style="cursor:pointer"><rect x="2" y="'+(yo-12)+'" width="62" height="24" rx="5" fill="currentColor" fill-opacity=".06" stroke="currentColor" stroke-width=".8"/><text x="8" y="'+(yo+4)+'" fill="currentColor" font-weight="700">Officers</text><title>Jump to the officer list</title></g>';
 T.forEach(function(t,i){var ton=!sel.path&&sel.tier===t;s+='<g class="vwt" data-t="'+t+'" style="cursor:pointer"><rect x="2" y="'+(y0+i*rh-12)+'" width="62" height="24" rx="5" fill="currentColor" fill-opacity="'+(ton?.2:.06)+'" stroke="currentColor" stroke-width="'+(ton?2.5:.8)+'"/><text x="8" y="'+(y0+i*rh+4)+'" fill="currentColor" font-weight="700">Tier '+t+'</text><title>Show tier '+t+' across all paths</title></g>';});
 P.forEach(function(p,j){cx[p]=x0+j*cw+cw/2;
  var pn=O.nms.filter(function(x){return x.path===p;}),pon=sel.path===p&&!sel.tier;
  s+='<g class="vwp" data-p="'+p+'" style="cursor:pointer"><rect x="'+(cx[p]-60)+'" y="4" width="120" height="40" rx="8" fill="'+O.paths[p].color+'" fill-opacity=".25" stroke="'+O.paths[p].color+'" stroke-width="'+(pon?3:1.5)+'"/><text x="'+cx[p]+'" y="21" text-anchor="middle" font-weight="700" fill="currentColor">'+esc(p)+' ('+pn.length+')</text><text x="'+cx[p]+'" y="36" text-anchor="middle" fill="currentColor" opacity=".7" font-size="9">'+esc(O.paths[p].officer)+'</text><title>Show every '+esc(p)+' NM, all tiers</title></g>';
  var of=OF.officers.filter(function(q){return q.role==='start'&&q.path===p;})[0];
  if(of){var oc=VC[of.validation];s+='<g class="vwo" data-id="'+of.id+'" style="cursor:pointer"><rect x="'+(cx[p]-34)+'" y="'+(yo-18)+'" width="68" height="40" rx="7" fill="'+O.paths[p].color+'" fill-opacity=".1" stroke="'+oc+'" stroke-width="2" stroke-dasharray="'+(of.status==='built'?'0':'4 3')+'"/><text x="'+cx[p]+'" y="'+(yo-1)+'" text-anchor="middle" font-weight="700" fill="currentColor">Officer</text><text x="'+cx[p]+'" y="'+(yo+14)+'" text-anchor="middle" font-size="10" fill="currentColor" opacity=".75">'+esc(of.status)+'</text><title>'+esc(of.name+' - '+of.status+', '+of.validation)+'</title></g>';
   s+='<line x1="'+cx[p]+'" y1="'+(yo+22)+'" x2="'+cx[p]+'" y2="'+(y0-24)+'" stroke="currentColor" opacity=".5" marker-end="url(#vwa)"/>';}
  T.forEach(function(t,i){
   if(i<T.length-1){var adv=O.paths[p].advance[t+'>'+T[i+1]];
    if(adv)s+='<line x1="'+cx[p]+'" y1="'+(y0+i*rh+22)+'" x2="'+cx[p]+'" y2="'+(y0+(i+1)*rh-24)+'" stroke="currentColor" opacity=".5" marker-end="url(#vwa)"/><text x="'+(cx[p]+6)+'" y="'+(y0+i*rh+rh/2+4)+'" font-size="9" fill="currentColor" opacity=".6">'+esc(adv==='unknown'?'?':adv.replace('Atmacite Refiner','refiner'))+'</text>';}
  });});
 O.unlocks.forEach(function(e){var a=cx[e[0]],b=cx[e[1]];if(a==null||b==null)return;
  s+='<path d="M'+a+','+(yo-26)+' Q'+((a+b)/2)+','+(yo-60)+' '+b+','+(yo-26)+'" fill="none" stroke="'+O.paths[e[0]].color+'" stroke-dasharray="4 3" opacity=".6" marker-end="url(#vwa)"/>';});
 P.forEach(function(p){T.forEach(function(t,i){var b=bucket(p,t),on=(sel.path===p||!sel.path)&&sel.tier===t;
  var x=cx[p]-34,y=y0+i*rh-18,built=b.filter(function(n){return n.status==='built';}).length,none=!b.length;
  s+='<g class="vwn" data-p="'+p+'" data-t="'+t+'" style="cursor:'+(none?'default':'pointer')+'"><rect x="'+x+'" y="'+y+'" width="68" height="40" rx="7" fill="'+(none?'none':O.paths[p].color)+'" fill-opacity="'+(none?0:.2)+'" stroke="'+O.paths[p].color+'" stroke-width="'+(on?3:1)+'" stroke-dasharray="'+(none?'3 3':'0')+'" opacity="'+(none?.35:1)+'"/>';
  s+='<text x="'+cx[p]+'" y="'+(y+17)+'" text-anchor="middle" font-weight="700" fill="currentColor">'+(none?'-':b.length+' NM')+'</text>';
  if(!none)s+='<text x="'+cx[p]+'" y="'+(y+32)+'" text-anchor="middle" font-size="10" fill="currentColor" opacity=".75">'+built+' built</text>';
  s+='<title>'+esc(p+' '+t+': '+b.map(function(n){return n.name;}).join(', '))+'</title></g>';});});
 s+='</svg>';
 $('vw-graph').innerHTML=s;
 $('vw-unas').innerHTML=un.length?'<b>'+un.length+' NMs have no path/tier recorded yet</b> and are not placed on the graph; use the "Unassigned" filter.':'';
 Array.prototype.forEach.call(document.querySelectorAll('.vwp'),function(g){g.addEventListener('click',function(){var p=g.dataset.p;sel={path:p,tier:''};$('vw-pa').value=p;$('vw-st').value='';$('vw-vs').value='';$('vw-q').value='';graph();table();});});
 Array.prototype.forEach.call(document.querySelectorAll('.vwn'),function(g){g.addEventListener('click',function(){var p=g.dataset.p,t=g.dataset.t;if(!bucket(p,t).length)return;
  if(sel.path===p&&sel.tier===t)sel={path:'',tier:''};else sel={path:p,tier:t};$('vw-pa').value=sel.path;graph();table();});});
 Array.prototype.forEach.call(document.querySelectorAll('.vwo'),function(g){g.addEventListener('click',function(){openOfficer(g.dataset.id);});});
 Array.prototype.forEach.call(document.querySelectorAll('.vwoff'),function(g){g.addEventListener('click',function(){$('vw-off').scrollIntoView({behavior:'smooth',block:'start'});});});
 Array.prototype.forEach.call(document.querySelectorAll('.vwt'),function(g){g.addEventListener('click',function(){var t=g.dataset.t;sel=(!sel.path&&sel.tier===t)?{path:'',tier:''}:{path:'',tier:t};$('vw-pa').value='';$('vw-st').value='';$('vw-vs').value='';$('vw-q').value='';graph();table();});});
}
function table(){
 var t=$('vw-q').value.toLowerCase(),st=$('vw-st').value,vs=$('vw-vs').value,pa=$('vw-pa').value;
 var rows=O.nms.filter(function(x){var un=!x.path||!x.tier;
  return (!t||(x.name+x.zone).toLowerCase().indexOf(t)>=0)&&(!st||x.status===st)&&(!vs||x.validation===vs)&&(!pa||(pa==='__un'?un:x.path===pa))&&(!sel.tier||x.tier===sel.tier);});
 var po=Object.keys(O.paths);rows.sort(function(a,b){var pa_=po.indexOf(a.path),pb=po.indexOf(b.path);pa_=pa_<0?99:pa_;pb=pb<0?99:pb;var ta=O.tiers.indexOf(a.tier),tb=O.tiers.indexOf(b.tier);ta=ta<0?99:ta;tb=tb<0?99:tb;return pa_-pb||ta-tb||a.name.localeCompare(b.name);});
 var lastg='';
 $('vw-tb').innerHTML=rows.map(function(x){var g=(x.path||'Unassigned')+(x.tier?' '+x.tier:''),gh='';if(g!==lastg){lastg=g;gh='<tr><td colspan="7" style="background:rgba(128,128,128,.15);font-weight:700;padding:3px 8px">'+esc(g)+'</td></tr>';}
  var warn=(!x.has_pool?'<span title="no mob_pools row in the active DB" style="color:#c0392b">no pool</span> ':'')+(x.status==='built'&&!x.has_script?'<span title="tracker says built but no script found" style="color:#c0392b">no script</span> ':'');
  return gh+'<tr class="vwr" data-n="'+esc(x.name)+'" style="cursor:pointer"><td><b>'+esc(x.name)+'</b></td><td>'+esc(x.zone)+' ('+(x.zone_id==null?'?':x.zone_id)+')</td><td>'+esc(x.path||'-')+' '+esc(x.tier||'')+'</td><td class="mono">'+num(x.hp)+'</td><td>'+(x.ki_id?esc(x.ki_name)+' ('+x.ki_id+')':'<span class="muted">unknown</span>')+'</td><td class="vwc1">'+vchip(x.status)+' '+warn+'</td><td class="vwc2">'+vchip(x.validation)+'</td></tr>';}).join('');
 var b=O.nms.filter(function(x){return x.status==='built';}).length,v=O.nms.filter(function(x){return x.validation==='validated';}).length,bi=O.nms.filter(function(x){return x.validation==='issue';}).length;
 $('vw-sum').textContent=O.nms.length+' NMs: '+b+' built / '+(O.nms.length-b)+' not built; '+v+' validated / '+(O.nms.length-v)+' not ('+bi+' with issues); showing '+rows.length+(sel.tier?' ('+(sel.path||'all paths')+' '+sel.tier+')':'');
 Array.prototype.forEach.call(document.querySelectorAll('.vwr'),function(r){r.addEventListener('click',function(){openNm(r.dataset.n);});});
}
var VC={validated:'#1e9e6a',partial:'#d68910',issue:'#c0392b',unvalidated:'#888'};
var TONE={validated:'ok',ok:'ok',done:'ok',built:'ok',complete:'ok',partial:'warn','needs-work':'warn',incomplete:'warn',issue:'bad',bad:'bad',missing:'bad','not built':'bad',unvalidated:'idle',untested:'idle',hold:'idle','n/a':'idle'};
var TC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'};
function tc(v){return TC[TONE[v]||'idle'];}
function vchip(v){return '<span class="chip vwst" style="border-color:'+tc(v)+';color:'+tc(v)+'">'+esc(v)+'</span>';}
function vsel(v,states,k){return '<select data-k="'+k+'" class="vwst" style="color:'+tc(v)+';border-color:'+tc(v)+'">'+states.map(function(st){return '<option'+(st===v?' selected':'')+'>'+st+'</option>';}).join('')+'</select>';}
function kv(o,keys){return '<table class="vwkv">'+keys.map(function(k){return '<tr><td class="muted">'+esc(k[1])+'</td><td class="mono">'+esc(o[k[0]])+'</td></tr>';}).join('')+'</table>';}
function openNm(name){
 $('vw-detail').hidden=false;$('vw-dbody').innerHTML='<p class="muted">Loading '+esc(name)+'...</p>';$('vw-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
 jget('/domains/voidwatch/nm.json?name='+encodeURIComponent(name)).then(detail).catch(function(e){$('vw-dbody').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});
}
function itemName(d,id){return d.items[id]?d.items[id].replace(/_/g,' '):'item '+id;}
function backlogTable(){
 var el=$('vw-backlog');if(!el)return;
 jget('/domains/voidwatch/backlog.json').then(function(d){
  var BC={missing:'#c0392b',partial:'#d68910',done:'#1e9e6a',hold:'#888'};var f=el.dataset.f||'';
  var L=d.items.filter(function(x){return !f||x.status===f;});
  el.innerHTML='<h3 style="margin:8px 0 2px">Voidwatch systems backlog <span class="muted">('+d.states.map(function(s){return d.counts[s]+' '+s;}).join(' / ')+')</span></h3>'+
  '<div class="muted">Refiner, atmacites, lights/weakness and rewards: systems around the NMs. Evidence tags: C capture, V client, W/F/J/B sources, H hypothesis, D design guess.</div>'+
  '<div><select id="vw-bf"><option value="">All</option>'+d.states.map(function(s){return '<option'+(s===f?' selected':'')+'>'+s+'</option>';}).join('')+'</select> <span id="vw-bmsg" class="muted"></span></div>'+
  '<div class="table-wrap"><table><thead><tr><th>Area</th><th>Item</th><th>Ev.</th><th>Detail</th><th class="vwc1">Status</th><th class="vwc2">Validation</th><th>Note</th><th></th></tr></thead><tbody>'+
  L.map(function(x){return '<tr data-id="'+x.id+'"><td>'+esc(x.area)+'</td><td>'+esc(x.title)+'</td><td class="mono">'+esc(x.evidence)+'</td><td>'+esc(x.detail)+'</td><td class="vwc1">'+vsel(x.status,d.states,'status')+'</td><td class="vwc2"><span class="muted">-</span></td>'+'<td><input data-k="note" value="'+esc(x.note)+'" style="width:160px"></td><td><button type="button" class="vwb">Save</button></td></tr>';}).join('')+'</tbody></table></div>';
  $('vw-bf').onchange=function(){el.dataset.f=this.value;backlogTable();};
  Array.prototype.forEach.call(el.querySelectorAll('.vwb'),function(b){b.onclick=function(){var tr=b.closest('tr'),ch={};Array.prototype.forEach.call(tr.querySelectorAll('[data-k]'),function(i){ch[i.dataset.k]=i.value;});
   fetch('/domains/voidwatch/backlog/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:tr.dataset.id,changes:ch})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(){backlogTable();}).catch(function(e){$('vw-bmsg').textContent='Save failed: '+e.message;});};});
 }).catch(function(e){el.innerHTML='<span class="muted">Backlog unavailable: '+esc(e.message)+'</span>';});
}
function stripPanel(wd){
 var el=$('vw-strip');if(!el||!O)return;
 var nm=O.nms,nb=nm.filter(function(x){return x.status==='built';}).length,nv=nm.filter(function(x){return x.validation==='validated';}).length,ni=nm.filter(function(x){return x.validation==='issue';}).length;
 var of=(OF&&OF.officers)||[],ob=of.filter(function(x){return x.status==='built';}).length,ov=of.filter(function(x){return x.validation==='validated';}).length,og=of.reduce(function(a,x){return a+(x.gaps||[]).length;},0);
 var noopt=wd.warps.filter(function(w){return w.option==null;}).length,nocoord=wd.warps.filter(function(w){return w.option!=null&&!w.complete;}).length,unv=wd.warps.filter(function(w){return w.complete&&w.validation!=='ok';}).length;
 function card(t,v,sub,c){return '<div class="vwval" style="flex:1;min-width:150px;margin:0"><div class="muted">'+t+'</div><div style="font-size:1.5em;font-weight:700;color:'+c+'">'+v+'</div><div class="muted">'+sub+'</div></div>';}
 var next=[];
 if(ni)next.push(ni+' NM(s) with validation issues: open them from the table below.');
 if(og)next.push(og+' gap(s) across the officer/refiner/purveyor NPCs (open each row).');
 if(noopt)next.push(noopt+' warp destination(s) have no option id: walk the refiner menu and paste the server log lines into "Paste from server log".');
 if(nocoord)next.push(nocoord+' warp(s) have an option but no landing zone/coordinates: stand at the landing spot, run !logpos, paste it.');
 if(unv)next.push(unv+' warp(s) are complete but not validated: test the teleport, then mark ok so Export Lua includes them.');
 if(nm.length-nb)next.push((nm.length-nb)+' NM(s) not built yet.');
 el.innerHTML='<div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">'+
  card('NMs built',nb+'/'+nm.length,nv+' validated, '+ni+' with issues',nb===nm.length?TC.ok:TC.warn)+
  card('NPCs built',ob+'/'+of.length,ov+' validated',ob===of.length?TC.ok:TC.warn)+
  card('Warps live',wd.ok+'/'+wd.total,wd.complete+' complete',wd.ok===wd.total?TC.ok:TC.warn)+'</div>'+
  (next.length?'<div class="vwval" style="margin:0 0 8px"><b>Next steps</b><ul style="margin:4px 0">'+next.map(function(t){return '<li>'+esc(t)+'</li>';}).join('')+'</ul></div>':'');
}
function warpTable(){
 var el=$('vw-warps');if(!el)return;
 jget('/domains/voidwatch/warps.json').then(function(d){
  var f=el.dataset.f||'';var L=d.warps.filter(function(w){return !f||(w.era+' '+w.set+' '+w.stone+' '+w.menu).toLowerCase().indexOf(f.toLowerCase())>=0;});
  var inp=function(w,k,wd){return '<input data-k="'+k+'" value="'+esc(w[k]==null?'':w[k])+'" style="width:'+wd+'px" class="mono">';};
  el.innerHTML='<h3 style="margin:8px 0 2px">Atmacite Refiner warp checklist <span class="muted">('+d.ok+' ok / '+d.complete+' complete / '+d.total+' destinations)</span></h3>'+
  '<div class="muted">Option = (destId*65536)+2 from the server log line; blank fields can be filled in here. Only complete AND ok entries are written to <span class="mono">'+esc(d.lua)+'</span>. Wiki source [W]; option [C-log]; coordinates are candidate zoneline arrival rows [DB] until validated in game.</div>'+
  '<div><input id="vw-wf" placeholder="filter (era / set / stone / zone)" value="'+esc(f)+'"> <button type="button" id="vw-wexp">Export Lua</button> <span id="vw-wmsg" class="muted"></span></div>'+
  '<details class="vwval"><summary><b>Paste from server log</b> <span class="muted">(fills one entry from a [VWO refiner] unhandled option line or a LOGPOS line)</span></summary>'+
  '<select id="vw-wik"><option value="option">Refiner option line</option><option value="logpos">!logpos line</option></select> into <select id="vw-wii">'+d.warps.map(function(w){return '<option value="'+w.id+'">'+w.id+' '+esc(w.set)+' '+esc(w.stone)+' '+w.tier+' - '+esc(w.menu)+(w.option==null?' (no option)':'')+'</option>';}).join('')+'</select> <button type="button" id="vw-wigo">Import</button><br>'+
  '<textarea id="vw-wit" rows="3" style="width:100%" class="mono" placeholder="paste the log line(s); the first match is used"></textarea></details>'+
  '<div class="table-wrap"><table><thead><tr><th>Era</th><th>Set</th><th>Needs</th><th>Menu entry</th><th>Landing zone</th><th>Option</th><th>x</th><th>y</th><th>z</th><th>rot</th><th>Landing note [W]</th><th class="vwc1">Status</th><th class="vwc2">Validation</th><th>Note</th><th></th></tr></thead><tbody>'+
  L.map(function(w){return '<tr data-id="'+w.id+'"><td>'+esc(w.era)+'</td><td>'+esc(w.set)+'</td><td>'+esc(w.stone)+' '+w.tier+'</td><td>'+esc(w.menu)+'</td><td>'+inp(w,'zone',150)+(w.zone_id==null&&w.zone?' <span style="color:#c0392b">?id</span>':w.zone_id!=null?' <span class="muted">'+w.zone_id+'</span>':'')+'</td><td>'+inp(w,'option',80)+'</td><td>'+inp(w,'x',70)+'</td><td>'+inp(w,'y',60)+'</td><td>'+inp(w,'z',70)+'</td><td>'+inp(w,'rot',36)+'</td><td>'+inp(w,'landing_note',200)+'</td><td class="vwc1">'+vchip(w.complete?'complete':'incomplete')+'</td><td class="vwc2">'+vsel(w.validation,d.states,'validation')+'</td><td>'+inp(w,'note',140)+'</td><td><button type="button" class="vww">Save</button></td></tr>';}).join('')+'</tbody></table></div>';
  $('vw-wigo').onclick=function(){fetch('/domains/voidwatch/warps/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:$('vw-wik').value,id:$('vw-wii').value,text:$('vw-wit').value})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(){warpTable();}).catch(function(e){$('vw-wmsg').textContent='Import failed: '+e.message;});};
  stripPanel(d);
  $('vw-wf').onchange=function(){el.dataset.f=this.value;warpTable();};
  $('vw-wexp').onclick=function(){fetch('/domains/voidwatch/warps/export-lua',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(j){$('vw-wmsg').textContent='Wrote '+j.entries+' live entries to '+j.path;}).catch(function(e){$('vw-wmsg').textContent='Export failed: '+e.message;});};
  Array.prototype.forEach.call(el.querySelectorAll('.vww'),function(b){b.onclick=function(){var tr=b.closest('tr'),ch={};Array.prototype.forEach.call(tr.querySelectorAll('[data-k]'),function(i){ch[i.dataset.k]=i.value;});
   fetch('/domains/voidwatch/warps/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:tr.dataset.id,changes:ch})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(){warpTable();}).catch(function(e){$('vw-wmsg').textContent='Save failed: '+e.message;});};});
 }).catch(function(e){el.innerHTML='<span class="muted">Warp checklist unavailable: '+esc(e.message)+'</span>';});
}
function offTable(){
 var el=$('vw-off');if(!el)return;var L=OF.officers;
 if(!L.length){el.innerHTML='<span class="muted">Officer data unavailable.</span>';return;}
 var b=L.filter(function(x){return x.status==='built';}).length,v=L.filter(function(x){return x.validation==='validated';}).length;
 el.innerHTML='<h3 style="margin:8px 0 2px">Voidwatch NPCs (officers, refiners, purveyors) <span class="muted">(no path can start without them)</span></h3><div class="muted">'+L.length+' officer/quest NPCs: '+b+' built / '+(L.length-b)+' not built; '+v+' validated / '+(L.length-v)+' not</div>'+
 '<div class="table-wrap"><table><thead><tr><th>Officer</th><th>Zones</th><th>Path</th><th>Key item</th><th>DB npc</th><th>Script</th><th class="vwc1">Status</th><th class="vwc2">Validation</th></tr></thead><tbody>'+L.map(function(x){
  var n=x.zones_live.filter(function(z){return z.npcs.length;}).length,sc=x.zones_live.filter(function(z){return z.script;}).length,t=x.zones_live.length;
  return '<tr class="vwor" data-id="'+x.id+'" style="cursor:pointer"><td><b>'+esc(x.name)+'</b>'+' <span class="chip">'+esc(x.role_label||x.role)+'</span>'+'</td><td>'+esc(x.zones.join(', '))+' <span class="muted">'+esc(x.grid)+'</span></td><td>'+esc(x.path)+'</td><td>'+(x.ki?esc(x.ki)+(x.ki_id!=null?' ('+x.ki_id+')':' <span style="color:#c0392b">missing</span>'):'-')+'</td><td>'+n+'/'+t+'</td><td>'+sc+'/'+t+'</td><td class="vwc1">'+vchip(x.status)+'</td><td class="vwc2">'+vchip(x.validation)+'</td></tr>';}).join('')+'</tbody></table></div>';
 Array.prototype.forEach.call(el.querySelectorAll('.vwor'),function(r){r.addEventListener('click',function(){openOfficer(r.dataset.id);});});
}
function openOfficer(id){
 var x=OF.officers.filter(function(q){return q.id===id;})[0];if(!x)return;
 $('vw-detail').hidden=false;$('vw-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
 var va=x.validation_rec,h='<h3 style="margin:0">'+esc(x.name)+' <span class="chip">'+esc(x.status)+'</span> <span class="chip">'+esc(x.path)+' path</span> <span class="chip">'+esc(x.role_label||x.role)+'</span></h3>';
 h+='<div class="muted">Source: ffxiclopedia Voidwatch Ops [W]. '+(x.quest?'Quest: '+esc(x.quest)+'. ':'')+esc(x.note||'')+'</div>';
 h+=x.impl_note?'<div class="vwc vwc-warn"><b>Build status:</b> '+esc(x.impl_note)+(x.slice?' <span class="muted">['+esc(x.slice)+']</span>':'')+'</div>':'';
 h+=x.gaps.length?x.gaps.map(function(g){return '<div class="vwc vwc-warn">GAP: '+esc(g)+'</div>';}).join(''):'<div class="vwc vwc-ok">No gaps found.</div>';
 h+='<h4>Key item</h4><div class="mono">'+(x.ki?esc(x.ki)+' = '+(x.ki_id==null?'not defined':x.ki_id)+' (this server keyitems.lua; ids drift from the client, verify with id_bridge before relying on it)':'none (sub-quest NPC)')+'</div>';
 h+='<h4>Zones <span class="muted">(each location is validated on its own; overall roll-up: </span>'+vchip(x.validation)+'<span class="muted">)</span></h4>'+x.zones_live.map(function(z){var zr=z.validation_rec||{};
  return '<div class="vwval" data-zone="'+esc(z.zone)+'"><b>'+esc(z.zone)+'</b> <span class="muted">zone '+(z.zone_id==null?'?':z.zone_id)+'</span> '+vchip(z.validation)+' <span class="muted">'+(zr.updated?'saved '+esc(zr.updated):'never saved')+'</span>'+
  '<div class="mono">'+(z.npcs.length?z.npcs.map(function(n){return '#'+n.npcid+' "'+esc(n.display)+'" at ('+n.x+', '+n.y+', '+n.z+') rot '+n.rot+' flag '+n.flag;}).join('<br>'):'<span style="color:#c0392b">no npc_list row</span>')+'</div>'+
  '<div class="mono">'+(z.script?esc(z.script):'<span style="color:#c0392b">no script</span>')+'</div>'+
  '<div class="vwvgrid">'+OF.zone_areas.map(function(a){var cv=(zr.areas||{})[a[0]]||'untested';return '<label>'+esc(a[1])+' <select data-a="'+a[0]+'" class="vwzsel">'+OF.states.map(function(st){return '<option'+(st===cv?' selected':'')+'>'+st+'</option>';}).join('')+'</select></label>';}).join('')+'</div>'+
  '<input class="vwznote" placeholder="Notes (observed position, issues)" value="'+esc(zr.note||'')+'" style="width:100%"><button type="button" class="vwzall">Mark all ok</button> <button type="button" class="vwzsave">Save this zone</button> <span class="vwzmsg muted"></span></div>';}).join('');
 $('vw-dbody').innerHTML=h;
 Array.prototype.forEach.call(document.querySelectorAll('#vw-dbody .vwval[data-zone]'),function(box){
  box.querySelector('.vwzall').onclick=function(){Array.prototype.forEach.call(box.querySelectorAll('.vwzsel'),function(e){e.value='ok';});};
  box.querySelector('.vwzsave').onclick=function(){var ar={};Array.prototype.forEach.call(box.querySelectorAll('.vwzsel'),function(e){ar[e.dataset.a]=e.value;});
   fetch('/domains/voidwatch/officer-zone-validation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:x.id,zone:box.dataset.zone,areas:ar,note:box.querySelector('.vwznote').value})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(){
    return jget('/domains/voidwatch/officers.json');}).then(function(o){OF=o;offTable();if(O)graph();openOfficer(x.id);}).catch(function(err){box.querySelector('.vwzmsg').textContent='Save failed: '+err.message;});};});
}
function nmKey(n){return n.replace(/[\s\-']+/g,'_');}
function bj(o){return esc(JSON.stringify(o));}
function dropsPanel(d,ps){
 jget('/domains/voidwatch/drops.json').then(function(c){
  var ov=c.overrides,e=(ov.nm[nmKey(d.name)])||{add:{},remove:[]},nm=function(i){return d.items[i]?d.items[i].replace(/_/g,' '):(c.items[i]?String(c.items[i]).replace(/_/g,' '):'item '+i);};
  var sc=(ps&&ps.drop_rates.length)?ps.drop_rates.map(function(r){return [r[0],r[1]+'%'];}):((ps&&ps.drops)||[]).map(function(i){return [i,'rare pool'];});
  var h='';
  if(!c.wired)h+='<div class="vwc vwc-warn">voidwatch.lua does not require voidwatch_drops, so overrides will have no effect.</div>';
  h+='<div class="table-wrap"><table><tr><th>item id</th><th>item</th><th>rate</th><th>source</th><th></th></tr>';
  sc.forEach(function(r){var rm=e.remove.indexOf(r[0])>=0;h+='<tr style="'+(rm?'opacity:.5;text-decoration:line-through':'')+'"><td>'+r[0]+'</td><td>'+esc(nm(r[0]))+'</td><td>'+esc(r[1])+'</td><td>script</td><td>'+(rm?'<button type="button" class="vwd" data-b="'+bj({op:'restore',item:r[0]})+'">Restore</button>':'<button type="button" class="vwd" data-b="'+bj({op:'remove',item:r[0]})+'">Remove</button>')+'</td></tr>';});
  Object.keys(e.add).forEach(function(i){h+='<tr><td>'+i+'</td><td>'+esc(nm(i))+'</td><td>'+e.add[i]+'%</td><td>added</td><td><button type="button" class="vwd" data-b="'+bj({op:'unadd',item:+i})+'">Delete</button></td></tr>';});
  if(!sc.length&&!Object.keys(e.add).length)h+='<tr><td colspan="5" class="muted">no drops</td></tr>';
  h+='</table></div><div>Add drop: item id <input id="vw-di" size="7"> rate % <input id="vw-dr" size="5" value="5"> <button type="button" id="vw-dadd">Preview add</button></div>';
  var eff=c.placeholder_pool.filter(function(i){return ov.poolRemove.indexOf(i)<0;}).concat(ov.pool);
  h+='<details><summary>Shared Pyxis filler pool ('+eff.length+' items, applies to every Voidwatch NM)</summary><div class="table-wrap"><table><tr><th>item id</th><th>item</th><th></th></tr>';
  eff.forEach(function(i){h+='<tr><td>'+i+'</td><td>'+esc(nm(i))+'</td><td><button type="button" class="vwd" data-b="'+bj({op:'pool_remove',item:i})+'">Remove</button></td></tr>';});
  ov.poolRemove.forEach(function(i){h+='<tr style="opacity:.5"><td>'+i+'</td><td>'+esc(nm(i))+'</td><td>removed <button type="button" class="vwd" data-b="'+bj({op:'pool_restore',item:i})+'">Restore</button></td></tr>';});
  h+='</table></div><div>Add to pool: item id <input id="vw-pi" size="7"> <button type="button" id="vw-padd">Preview add</button></div></details>';
  $('vw-drops').innerHTML=h;
  function post(b){return fetch('/domains/voidwatch/drops/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
  function run(b){b.scope=d.name;b.dry_run=true;$('vw-dapply').innerHTML='';$('vw-dres').textContent='Planning...';
   post(b).then(function(j){$('vw-dres').textContent='PREVIEW (nothing written): '+j.op+' '+j.item+' '+j.item_name+'\n'+(j.diff||'(no change)');
    if(j.unchanged)return;
    $('vw-dapply').innerHTML='<button type="button" id="vw-dgo">Apply this change</button> <span class="muted">uses the write confirmation field in the Edit section below</span>';
    $('vw-dgo').onclick=function(){b.dry_run=false;b.confirmation=$('vw-conf').value;
     post(b).then(function(){$('vw-dres').textContent='APPLIED to voidwatch_drops.lua (takes effect when the script is deployed and reloaded).';$('vw-dapply').innerHTML='';setTimeout(function(){dropsPanel(d,ps);},600);})
     .catch(function(er){$('vw-dres').textContent='Refused: '+er.message;});};})
   .catch(function(er){$('vw-dres').textContent='Refused: '+er.message;});}
  Array.prototype.forEach.call(document.querySelectorAll('.vwd'),function(btn){btn.onclick=function(){run(JSON.parse(btn.dataset.b));};});
  $('vw-dadd').onclick=function(){run({op:'add',item:$('vw-di').value,rate:$('vw-dr').value});};
  $('vw-padd').onclick=function(){run({op:'pool_add',item:$('vw-pi').value});};
 }).catch(function(e){$('vw-drops').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});
}
function detail(d){
 var t=d.tracker,s=d.script,ps=s?s.parsed:null,h='';
 h+='<h3 style="margin:0">'+esc(d.name)+' <span class="chip">'+esc(t.status)+'</span> <span class="chip">'+esc((t.path||'no path')+' '+(t.tier||''))+'</span> <span class="chip">'+esc(t.zone)+'</span></h3>';
 var va=d.validation;
 h+='<div class="vwval"><b>Validation</b> '+vchip(va.status)+' <span class="muted">'+(va.updated?'last saved '+esc(va.updated):'never saved')+'</span><div class="vwvgrid">'+d.areas.map(function(a){var cv=(va.areas||{})[a[0]]||'untested';return '<label>'+esc(a[1])+' <select data-a="'+a[0]+'" class="vwsel">'+d.states.map(function(st){return '<option'+(st===cv?' selected':'')+'>'+st+'</option>';}).join('')+'</select></label>';}).join('')+'</div><textarea id="vw-note" rows="2" placeholder="Notes (what was tested / what is wrong)" style="width:100%">'+esc(va.note||'')+'</textarea><div><button type="button" id="vw-save">Save validation</button> <button type="button" id="vw-allok">Mark all ok</button> <span id="vw-saved" class="muted"></span></div></div>';
 h+='<div>'+d.checks.map(function(c){return '<div class="vwc vwc-'+c.level+'">'+esc(c.level.toUpperCase())+': '+esc(c.msg)+'</div>';}).join('')+'</div>';
 d.pools.forEach(function(p){
  h+='<h4>Pool '+p.poolid+' <span class="muted">skill list '+p.skill_list_id+', spell list '+p.spellList+', family '+p.familyid+(p.family?' ('+esc(p.family.family)+')':'')+'</span></h4>';
  h+='<div class="vwcols"><div>'+kv(p,[['mJob','Main job'],['sJob','Sub job'],['cmbDelay','Melee delay'],['cmbDmgMult','Damage mult %'],['aggro','Aggro'],['true_detection','True detect'],['links','Links'],['behavior','Behavior'],['immunity','Immunity'],['flag','Flag'],['entityFlags','entityFlags']])+'</div>';
  h+='<div>'+p.groups.map(function(g){return '<b>Group '+g.groupid+'</b>'+kv(g,[['zoneid','Zone'],['HP','HP'],['MP','MP'],['minLevel','Min level'],['maxLevel','Max level'],['respawntime','Respawn (s)'],['spawntype','Spawn type'],['dropid','mob_droplist id']])+
   '<div class="muted">Spawn points: '+(g.spawns.length?g.spawns.map(function(sp){return '#'+sp.mobid+' ('+sp.x+', '+sp.y+', '+sp.z+')';}).join('; '):'none')+'</div>';}).join('')+'</div>';
  if(p.family)h+='<div><b>Family base</b>'+kv(p.family,[['HP','HP'],['STR','STR'],['DEX','DEX'],['VIT','VIT'],['AGI','AGI'],['INT','INT'],['MND','MND'],['CHR','CHR'],['ATT','ATT'],['DEF','DEF'],['ACC','ACC'],['EVA','EVA']])+'</div>';
  h+='</div>';
  h+='<h4>Skills ('+p.skills.length+')</h4>'+(p.skills.length?'<div class="table-wrap"><table><tr><th>id</th><th>name</th><th>AoE</th><th>range</th><th>flag</th><th>param</th><th>SC</th></tr>'+p.skills.map(function(k){return '<tr><td>'+k.id+'</td><td>'+esc(k.name)+'</td><td>'+k.aoe+'</td><td>'+k.distance+'</td><td>'+k.flag+'</td><td>'+k.param+'</td><td>'+[k.sc1,k.sc2,k.sc3].join('/')+'</td></tr>';}).join('')+'</table></div>':'<span class="muted">none</span>');
  h+='<h4>Spells ('+p.spells.length+')</h4>'+(p.spell_list_pools>50?'<div class="vwval" style="border-color:#c0392b"><b>Generic list:</b> spell list '+p.spellList+' is shared by '+p.spell_list_pools+' mob pools (DSP default caster list), not specific to this NM. If this NM should not cast, set mob_pools.spellList=0 for poolid '+p.poolid+': <code>UPDATE mob_pools SET spellList=0 WHERE poolid='+p.poolid+';</code></div>':'')+(p.spells.length?'<div class="table-wrap"><table><tr><th>id</th><th>name</th><th>levels</th></tr>'+p.spells.map(function(k){return '<tr><td>'+k.id+'</td><td>'+esc(k.name)+'</td><td>'+k.min+'-'+k.max+'</td></tr>';}).join('')+'</table></div>':'<span class="muted">none (spellList '+p.spellList+')</span>');
  if(p.mods.length)h+='<h4>Pool mods</h4><div class="mono">'+p.mods.map(function(m){return (m.is_mob_mod?'mobmod ':'mod ')+m.modid+' = '+m.value;}).join('<br>')+'</div>';
 });
 h+='<h4>Drops <span class="muted">(script + overrides in voidwatch_drops.lua; not mob_droplist)</span></h4><div id="vw-drops" class="muted">Loading drops...</div><pre id="vw-dres" class="mono" style="white-space:pre-wrap"></pre><div id="vw-dapply"></div>';
 h+='<h4>Script</h4>';
 if(s){h+='<div class="muted">'+esc(s.path)+' ('+s.lines+' lines)'+(s.in_active_root?'':' - feature checkout only')+'</div>'+
  kv({region:ps.region||'-',stage:ps.stage||'-',time:ps.time_limit_s?ps.time_limit_s+' s':'-',hooks:ps.hooks.join(', ')||'-',ki:ps.key_items.join(', ')||'-',tags:Object.keys(ps.tags).map(function(k){return k+':'+ps.tags[k];}).join(' ')||'-'},[['region','Region'],['stage','Stage'],['time','Time limit'],['hooks','Hooks'],['ki','Key items'],['tags','Source tags']])+
  (ps.mods.length?'<div class="mono">'+ps.mods.map(function(m){return esc(m.call+' '+m.mod+' = '+m.value);}).join('<br>')+'</div>':'')+
  (ps.header.length?'<div class="muted">'+ps.header.map(esc).join('<br>')+'</div>':'')+
  '<details><summary>Lua source</summary><pre class="mono" style="max-height:420px;overflow:auto">'+esc(s.source)+'</pre></details>';
 } else h+='<span class="muted">No mob script found in the DSP checkouts.</span>';
 h+='<h4>Rift NPCs</h4>'+(d.rifts.length?'<div class="mono">'+d.rifts.map(function(r){return r.npc+' at ('+r.pos.join(', ')+') '+(r.live?'live: '+esc(r.live.name):'<span style="color:#c0392b">not in DB</span>');}).join('<br>')+'</div>':'<span class="muted">none</span>');
 h+='<h4>Known gaps (tracker)</h4><div class="muted">'+esc(t.gaps||'-')+'</div>';

 h+='<h4>Edit (live DSP database)</h4><div class="muted">Change values, press Preview to see the exact SQL, then Apply. Writes are gated: type the active profile name shown in the error if prompted. Drops are edited in the Drops section above.</div>';
 var forms=[];
 d.pools.forEach(function(p){
  forms.push({t:'mob_pools',k:p.poolid,label:'Pool '+p.poolid+' ('+p.name+')',f:[['mJob','Main job',p.mJob],['sJob','Sub job',p.sJob],['cmbDelay','Melee delay',p.cmbDelay],['cmbDmgMult','Dmg mult %',p.cmbDmgMult],['aggro','Aggro 0/1',p.aggro],['true_detection','True detect 0/1',p.true_detection],['links','Links 0/1',p.links],['skill_list_id','Skill list id',p.skill_list_id],['spellList','Spell list id',p.spellList]]});
  p.groups.forEach(function(g){
   forms.push({t:'mob_groups',k:g.groupid,label:'Group '+g.groupid,f:[['HP','HP',g.HP],['MP','MP',g.MP],['minLevel','Min level',g.minLevel],['maxLevel','Max level',g.maxLevel],['respawntime','Respawn (s)',g.respawntime]]});
   g.spawns.forEach(function(sp){forms.push({t:'mob_spawn_points',k:sp.mobid,label:'Spawn #'+sp.mobid,f:[['pos_x','X',sp.x],['pos_y','Y (inverted)',sp.y],['pos_z','Z',sp.z],['pos_rot','Rot',sp.rot]]});});
  });
 });
 h+=forms.map(function(fm,i){return '<details class="vwef" data-i="'+i+'"><summary>'+esc(fm.label)+' <span class="muted">'+fm.t+'</span></summary><div class="vwvgrid">'+fm.f.map(function(c){return '<label>'+esc(c[1])+' <input class="vwin" data-c="'+c[0]+'" data-o="'+esc(c[2])+'" value="'+esc(c[2])+'" style="width:100%"></label>';}).join('')+'</div><button type="button" class="vwprev" data-i="'+i+'">Preview SQL</button> <button type="button" class="vwapply" data-i="'+i+'">Apply</button></details>';}).join('');
 h+='<div class="vwval"><label>Write confirmation <input id="vw-conf" placeholder="active profile name (only needed to Apply)" style="width:60%"></label><pre id="vw-eres" class="mono" style="white-space:pre-wrap;margin:6px 0 0"></pre></div>';
 $('vw-dbody').innerHTML=h;
 dropsPanel(d,ps);
 Array.prototype.forEach.call(document.querySelectorAll('.vwprev,.vwapply'),function(btn){btn.onclick=function(){
  var fm=forms[btn.dataset.i],det=btn.parentNode,ch={},apply=btn.classList.contains('vwapply');
  Array.prototype.forEach.call(det.querySelectorAll('.vwin'),function(e){if(e.value!==e.dataset.o)ch[e.dataset.c]=e.value;});
  if(!Object.keys(ch).length){$('vw-eres').textContent='No fields changed.';return;}
  $('vw-eres').textContent=apply?'Applying...':'Planning...';
  fetch('/domains/voidwatch/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({table:fm.t,key:fm.k,changes:ch,dry_run:!apply,confirmation:$('vw-conf').value})})
  .then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});})
  .then(function(j){$('vw-eres').textContent=(j.applied?'APPLIED ('+j.rows+' row)\n':'PREVIEW (nothing written)\n')+'before: '+JSON.stringify(j.before)+'\n'+j.sql+(j.warnings.length?'\nWARN: '+j.warnings.join('\nWARN: '):'')+(j.applied?'\n(reload the zone / restart the map server for live mobs to pick this up)':'');
    if(j.applied){setTimeout(function(){openNm(d.name);jget('/domains/voidwatch/overview.json').then(function(o){O=o;graph();table();});},1800);}})
  .catch(function(e){$('vw-eres').textContent='Refused: '+e.message;});};});
 $('vw-allok').onclick=function(){Array.prototype.forEach.call(document.querySelectorAll('.vwsel'),function(e){e.value='ok';});};
 $('vw-save').onclick=function(){var ar={};Array.prototype.forEach.call(document.querySelectorAll('.vwsel'),function(e){ar[e.dataset.a]=e.value;});
  fetch('/domains/voidwatch/validation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:d.name,areas:ar,note:$('vw-note').value})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(function(j){
   $('vw-saved').textContent='Saved: '+j.status;var n=O.nms.filter(function(x){return x.name===d.name;})[0];if(n)n.validation=j.status;table();}).catch(function(e){$('vw-saved').textContent='Save failed: '+e.message;});};
}
document.addEventListener('DOMContentLoaded',function(){
 ['vw-q','vw-st','vw-vs','vw-pa'].forEach(function(i){$(i).addEventListener('input',function(){
  if(i==='vw-pa'){var v=$('vw-pa').value;sel={path:v==='__un'?'':v,tier:''};if(O)graph();}
  if(O)table();});});
 $('vw-close').addEventListener('click',function(){$('vw-detail').hidden=true;});
 load();
});
function npcFix(){
 var el=$('vw-npcfix');if(!el)return;
 function post(b){return fetch('/domains/voidwatch/npcfix',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
 jget('/domains/voidwatch/npcfix.json').then(function(d){
  var h='<h3 style="margin:8px 0 2px">NPC row fixes <span class="muted">(npc_list; dry-run first, apply is behind the write gate and logged)</span></h3>';
  d.fixes.forEach(function(f,i){
   h+='<div class="vwval"><b>'+esc(f.title)+'</b> '+(f.done?'<span class="chip">done</span>':'')+'<div class="muted">'+esc(f.evidence)+'</div>'+(f.done?'':'<pre class="mono vwsql">'+esc(f.plan_result?f.plan_result.sql:'')+'</pre><button type="button" data-fix="'+i+'">Dry-run</button> <button type="button" data-fixgo="'+i+'" hidden>Apply</button>')+'<pre class="mono vwfres" data-r="'+i+'" style="white-space:pre-wrap"></pre></div>';
  });
  h+='<div class="vwval"><b>Open questions (need in-game data)</b><ul>'+d.open.map(function(t){return '<li>'+esc(t)+'</li>';}).join('')+'</ul></div>';
  h+='<div class="vwval"><b>Add / delete a row</b><br><select id="nf-npc">'+d.names.map(function(n){return '<option>'+n+'</option>';}).join('')+'</select> zone <input id="nf-zone" placeholder="Qufim_Island" size="18"> x <input id="nf-x" size="7"> y <input id="nf-y" size="7"> z <input id="nf-z" size="7"> rot <input id="nf-rot" size="4"> <button type="button" id="nf-ins">Dry-run insert</button><br>delete npcid <input id="nf-del" size="10"> <button type="button" id="nf-delb">Dry-run delete</button> <button type="button" id="nf-go" hidden>Apply last plan</button><pre id="nf-res" class="mono" style="white-space:pre-wrap"></pre></div>';
  h+='<div class="vwval"><label>Write confirmation <input id="nf-conf" placeholder="active profile name (only needed to Apply)" style="width:60%"></label></div>';
  el.innerHTML=h;
  var last=null;
  function show(node,j){node.textContent=(j.applied?'APPLIED ('+j.rows+' row)\n':'DRY RUN\n')+j.sql+'\n'+(j.warnings||[]).join('\n');}
  function run(b,node,goBtn){b.dry_run=true;post(b).then(function(j){last=b;show(node,j);goBtn.hidden=false;}).catch(function(e){goBtn.hidden=true;node.textContent='Refused: '+e.message;});}
  function apply(node,goBtn){var b=Object.assign({},last,{dry_run:false,confirmation:$('nf-conf').value});post(b).then(function(j){show(node,j);goBtn.hidden=true;npcFix();}).catch(function(e){node.textContent='Apply failed: '+e.message;});}
  el.querySelectorAll('[data-fix]').forEach(function(btn){var i=+btn.dataset.fix,node=el.querySelector('[data-r="'+i+'"]'),go=el.querySelector('[data-fixgo="'+i+'"]');
   btn.onclick=function(){run(Object.assign({},d.fixes[i].plan),node,go);};go.onclick=function(){apply(node,go);};});
  var res=$('nf-res'),gob=$('nf-go');
  $('nf-ins').onclick=function(){run({kind:'insert',npc:$('nf-npc').value,zone:$('nf-zone').value.trim(),x:$('nf-x').value,y:$('nf-y').value,z:$('nf-z').value,rot:$('nf-rot').value},res,gob);};
  $('nf-delb').onclick=function(){run({kind:'delete',npcid:$('nf-del').value},res,gob);};
  gob.onclick=function(){apply(res,gob);};
 }).catch(function(e){el.innerHTML='<p class="muted">NPC fixes unavailable: '+esc(e.message)+'</p>';});
}
})();
