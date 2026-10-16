(function(){
var O=null,sel='';
var TC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'};
var TONE={built:'ok',validated:'ok',done:'ok',ok:'ok',partial:'warn',open:'warn',unvalidated:'idle',untested:'idle',issue:'bad'};
var COL={CLEAR_ABYSSITE:'#bbb',COLORFUL_ABYSSITE:'#d9a',BLUE_ABYSSITE:'#4a8fd8',ORANGE_ABYSSITE:'#e08a2c',BROWN_ABYSSITE:'#8a5a2b',YELLOW_ABYSSITE:'#d8c43a',PURPLE_ABYSSITE:'#8a5ad8',GREY_ABYSSITE:'#777',BLACK_ABYSSITE:'#222'};
function $(i){return document.getElementById(i);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function chip(v){var c=TC[TONE[v]||'idle'];return '<span class="chip vwst" style="border-color:'+c+';color:'+c+'">'+esc(v)+'</span>';}
function nice(a){return a.replace('_ABYSSITE','').toLowerCase();}
function graph(){
 var T=O.tiers,w=170,h=64,gap=60,s='<svg width="'+(T.length*(w+gap))+'" height="170" xmlns="http://www.w3.org/2000/svg"><defs><marker id="vwm" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="#888"/></marker></defs>';
 T.forEach(function(t,i){
  var x=i*(w+gap)+4,y=40,key=t.names.join(','),on=sel===key;
  if(i<T.length-1)s+='<line x1="'+(x+w)+'" y1="'+(y+h/2)+'" x2="'+(x+w+gap-4)+'" y2="'+(y+h/2)+'" stroke="#888" stroke-width="2" marker-end="url(#vwm)"/><text x="'+(x+w+4)+'" y="'+(y+h/2-6)+'" font-size="10" fill="#888">1 in 10</text>';
  s+='<g class="vwt" data-k="'+key+'" style="cursor:pointer"><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="8" fill="none" stroke="'+(on?'#2a7de1':'#888')+'" stroke-width="'+(on?3:1.5)+'"/>';
  s+='<text x="'+(x+w/2)+'" y="'+(y+22)+'" text-anchor="middle" font-size="13" font-weight="700" fill="currentColor">'+(t.names.length>1?'Colour tier':nice(t.names[0]))+'</text>';
  s+='<text x="'+(x+w/2)+'" y="'+(y+40)+'" text-anchor="middle" font-size="11" fill="currentColor">'+t.count+' NMs, '+t.built+' built</text>';
  s+='<text x="'+(x+w/2)+'" y="'+(y+55)+'" text-anchor="middle" font-size="10" fill="#888">'+t.names.map(function(n){return O.ki[n];}).join('/')+'</text>';
  t.names.forEach(function(n,j){s+='<circle cx="'+(x+14+j*14)+'" cy="'+(y-12)+'" r="5" fill="'+COL[n]+'" stroke="#888"/>';});
  s+='</g>';
 });
 $('vw2-graph').innerHTML=s+'</svg>';
 Array.prototype.forEach.call(document.querySelectorAll('.vwt'),function(g){g.addEventListener('click',function(){sel=sel===g.dataset.k?'':g.dataset.k;graph();table();});});
}
function strip(){
 var n=O.nms,b=n.filter(function(x){return x.status==='built';}).length,v=n.filter(function(x){return x.validation==='validated';}).length,p=n.filter(function(x){return x.validation==='partial';}).length,bad=n.filter(function(x){return x.validation==='issue';}).length;
 var c=[[n.length,'NMs'],[O.zones.length,'zones'],[b,'built'],[n.length-b,'with gaps'],[v,'validated'],[p,'partly validated'],[bad,'with issues'],[O.orphans.length,'orphan scripts']];
 $('vw2-strip').innerHTML=c.map(function(x){return '<div class="cpcard"><b style="font-size:1.4em">'+x[0]+'</b><div class="muted">'+x[1]+'</div></div>';}).join('');
 $('vw2-srv').textContent=(O.db_checked?'Live DB cross-check on. ':'No DB connection: pool/spawn checks skipped. ')+'Source: '+O.root;
}
function table(){
 var q=$('vw2-q').value.toLowerCase(),st=$('vw2-st').value,vs=$('vw2-vs').value,z=$('vw2-z').value;
 var rows=O.nms.filter(function(x){return (!q||(x.name+x.zone).toLowerCase().indexOf(q)>=0)&&(!st||x.status===st)&&(!vs||x.validation===vs)&&(!z||String(x.zone_id)===z)&&(!sel||sel.split(',').indexOf(x.abyssite)>=0);});
 $('vw2-sum').textContent='Showing '+rows.length+' of '+O.nms.length+' NMs';
 $('vw2-tb').innerHTML=rows.map(function(x){var d=x.db;
  return '<tr class="vwr" data-k="'+esc(x.key)+'" style="cursor:pointer"><td><b>'+esc(x.name)+'</b></td><td>'+esc(x.zone)+' ('+x.zone_id+')</td><td><span style="color:'+COL[x.abyssite]+'">&#9679;</span> '+nice(x.abyssite)+' '+x.ki_id+'</td><td>'+(x.upgrade?nice(x.upgrade):'<span class="muted">final</span>')+'</td><td class="mono">'+(d?(d.hp==null?'-':d.hp):'-')+'</td><td class="vwc1">'+chip(x.status)+(x.gaps.length?' <span style="color:#c0392b" title="'+esc(x.gaps.join('; '))+'">'+x.gaps.length+'</span>':'')+'</td><td class="vwc2">'+chip(x.validation)+'</td></tr>';}).join('');
 Array.prototype.forEach.call(document.querySelectorAll('.vwr'),function(r){r.addEventListener('click',function(){detail(r.dataset.k);});});
}
function detail(k){
 var x=O.nms.filter(function(n){return n.key===k;})[0];if(!x)return;var d=x.db,r=x.validation_rec||{},a=r.areas||{};
 var h='<h3 style="margin:0">'+esc(x.name)+' '+chip(x.status)+' '+chip(x.validation)+'</h3><div class="muted">'+esc(x.zone)+' (zone '+x.zone_id+'), mob id '+x.id+', pops with '+nice(x.abyssite)+' abyssite ('+x.ki_id+'), upgrades to '+(x.upgrade?nice(x.upgrade):'nothing (final tier)')+'</div>';
 h+=x.gaps.length?x.gaps.map(function(g){return '<div class="vwc vwc-warn">GAP: '+esc(g)+'</div>';}).join(''):'<div class="vwc vwc-ok">No gaps found.</div>';
 h+='<h4>Live DB</h4><div class="mono">'+(d?'spawn ('+d.pos.join(', ')+'), group '+d.groupid+', pool '+esc(d.poolid)+' '+esc(d.pool_name||'?')+', HP '+esc(d.hp):'no data')+'</div>';
 var tier1=x.abyssite==='CLEAR_ABYSSITE'||x.abyssite==='COLORFUL_ABYSSITE';
 h+='<h4>Drops <span class="muted">(mob_groups.dropid '+(d&&d.dropid?d.dropid:'0')+')</span></h4>';
 if(d&&d.drops&&d.drops.length){h+='<table><thead><tr><th>Item</th><th>Id</th><th>Chance</th></tr></thead><tbody>'+d.drops.map(function(q){return '<tr><td>'+esc(q.name||'?')+'</td><td class="mono">'+q.item+'</td><td>'+(q.rate/10)+'% <span class="muted">('+q.rate+'/1000, group rate '+q.group_rate+', type '+q.type+')</span></td></tr>';}).join('')+'</tbody></table>';}
 else h+='<div class="muted">'+(tier1?'None wired. Tier 1/2 NMs only convert the abyssite on death; the reference infographic lists no drops for the clear tier.':'None wired.')+'</div>';
 h+='<h4>Validation</h4><div class="vwvgrid">'+O.areas.map(function(ar){var cv=a[ar[0]]||'untested';return '<label>'+esc(ar[1])+' <select data-a="'+ar[0]+'" class="vwsel">'+O.states.map(function(s){return '<option'+(s===cv?' selected':'')+'>'+s+'</option>';}).join('')+'</select></label>';}).join('')+'</div>';
 h+='<input id="vw2-note" placeholder="Notes" value="'+esc(r.note||'')+'" style="width:100%"><button type="button" id="vw2-all">Mark all ok</button> <button type="button" id="vw2-save">Save</button> <span id="vw2-msg" class="muted">'+(r.updated?'saved '+esc(r.updated):'never saved')+'</span>';
 $('vw2-detail').hidden=false;$('vw2-detail').innerHTML=h;$('vw2-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
 $('vw2-all').onclick=function(){Array.prototype.forEach.call(document.querySelectorAll('.vwsel'),function(e){e.value='ok';});};
 $('vw2-save').onclick=function(){var ar={};Array.prototype.forEach.call(document.querySelectorAll('.vwsel'),function(e){ar[e.dataset.a]=e.value;});
  fetch('/domains/voidwalker/validation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,areas:ar,note:$('vw2-note').value})}).then(function(r){if(!r.ok)throw new Error(r.status);return load();}).then(function(){detail(k);}).catch(function(e){$('vw2-msg').textContent='Save failed: '+e.message;});};
}
function extras(){
 var z='<table><thead><tr><th>Zone</th><th>NMs</th><th>Position slots</th><th>Text ids</th></tr></thead><tbody>'+O.zones.map(function(q){return '<tr><td>'+esc(q.folder)+' ('+q.zone_id+')</td><td>'+q.nms+'</td><td>'+q.positions+'</td><td>'+q.text+'</td></tr>';}).join('')+'</tbody></table>';
 $('vw2-zones').innerHTML=z;
 $('vw2-back').innerHTML='<table><thead><tr><th>Item</th><th>Status</th><th>Note</th></tr></thead><tbody>'+O.backlog.map(function(b){return '<tr><td>'+esc(b.title)+'</td><td>'+chip(b.status)+'</td><td class="muted">'+esc(b.note)+'</td></tr>';}).join('')+'</tbody></table>';
 $('vw2-val').innerHTML=(O.orphans.length?'<div class="vwc vwc-warn"><b>'+O.orphans.length+' scripts call voidwalker.onMobDeath but are not in voidwalker_data.lua</b> (orphans or typos):<br><span class="mono">'+O.orphans.map(esc).join('<br>')+'</span></div>':'<div class="vwc vwc-ok">No orphan NM scripts.</div>')+
  (function(){var g=O.nms.filter(function(x){return x.gaps.length;});return g.length?'<div class="vwc vwc-warn"><b>'+g.length+' NMs have gaps:</b><br>'+g.slice(0,40).map(function(x){return esc(x.name)+' ('+esc(x.zone)+'): '+esc(x.gaps.join('; '));}).join('<br>')+(g.length>40?'<br>...':'')+'</div>':'<div class="vwc vwc-ok">Every NM has script, spawn row, group and pool.</div>';})()+
  '<div class="muted">'+esc(O.note)+'</div>';
}
function more(){
 var n=O.npc;
 $('vw2-npc').innerHTML='<div class="vwc vwc-ok"><b>'+esc(n.name)+'</b>, '+esc(n.zone)+' ('+n.zone_id+'), '+esc(n.pos)+'. Event '+n.event+', price '+n.price+' gil.<br>'+esc(n.desc)+'<br><span class="mono">'+esc(n.script)+'</span></div>';
 $('vw2-aby').innerHTML='<div class="vwc vwc-warn">'+esc(O.abyssea)+'</div><table class="vwt"><tr><th>NM</th><th>Zone</th><th>Tier</th><th>Key items</th><th>Atma</th></tr>'+(O.abyssea_nms||[]).map(function(n){return '<tr><td>'+esc(n.name)+'</td><td>'+esc(n.zone)+'</td><td>'+(n.tier||'')+'</td><td>'+esc(n.keyitems.join(', '))+'</td><td>'+esc(n.atma.join(', '))+'</td></tr>';}).join('')+'</table>';
 var sk=O.skills||{},ks=Object.keys(sk).sort();
 $('vw2-skills').innerHTML=ks.length?'<table><thead><tr><th>NM</th><th>Pool</th><th>List</th><th>Skills</th></tr></thead><tbody>'+ks.map(function(k){var q=sk[k];return '<tr><td>'+esc(k)+'</td><td class="mono">'+q.pool+'</td><td class="mono">'+q.list+(q.list>=9000?' (own)':'')+'</td><td>'+q.skills.map(function(s){return '<span style="color:'+(s.lua?'inherit':'#c0392b')+'" title="'+(s.lua?'Lua present':'no Lua')+'">'+esc(s.name)+'</span>';}).join(', ')+'</td></tr>';}).join('')+'</tbody></table>':'<div class="muted">No DB connection.</div>';
 var w=O.wiki||{},wk=Object.keys(w).sort(),miss=wk.filter(function(k){return w[k].indexOf('BGWiki')<0&&w[k].indexOf('FFXIclopedia')<0;});
 $('vw2-wiki').innerHTML='<div class="muted">'+wk.length+' pages checked in ffxi_zone_database.db; '+miss.length+' with no page in BG Wiki or FFXIclopedia (WikiWikiJP has no Voidwalker pages).</div><table><thead><tr><th>Page</th><th>BG Wiki</th><th>FFXIclopedia</th><th>WikiWikiJP</th></tr></thead><tbody>'+wk.map(function(k){var a=w[k];function m(x){return a.indexOf(x)>=0?'yes':'<span class="muted">-</span>';}return '<tr><td>'+esc(k)+'</td><td>'+m('BGWiki')+'</td><td>'+m('FFXIclopedia')+'</td><td>'+m('WikiWikiJP')+'</td></tr>';}).join('')+'</tbody></table>';
}
function load(){return fetch('/domains/voidwalker/overview.json').then(function(r){return r.json();}).then(function(j){O=j;strip();graph();table();extras();more();});}
function init(){
 var z=$('vw2-z');
 load().then(function(){z.innerHTML='<option value="">All zones</option>'+O.zones.map(function(q){return '<option value="'+q.zone_id+'">'+esc(q.folder)+'</option>';}).join('');
  ['vw2-q','vw2-st','vw2-vs','vw2-z'].forEach(function(i){$(i).oninput=$(i).onchange=table;});}).catch(function(e){$('vw2-sum').textContent='Failed to load: '+e.message;});
}
init();
})();
