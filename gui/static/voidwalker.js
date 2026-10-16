(function(){
var O=null,sel=null;
var TC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'};
var TONE={built:'ok',validated:'ok',done:'ok',ok:'ok',partial:'warn',open:'warn',unvalidated:'idle',untested:'idle',issue:'bad'};
var COL={CLEAR_ABYSSITE:'#bbb',COLORFUL_ABYSSITE:'#d9a',BLUE_ABYSSITE:'#4a8fd8',ORANGE_ABYSSITE:'#e08a2c',BROWN_ABYSSITE:'#8a5a2b',YELLOW_ABYSSITE:'#d8c43a',PURPLE_ABYSSITE:'#8a5ad8',GREY_ABYSSITE:'#777',BLACK_ABYSSITE:'#222'};
function $(i){return document.getElementById(i);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function chip(v){var c=TC[TONE[v]||'idle'];return '<span class="chip vwst" style="border-color:'+c+';color:'+c+'">'+esc(v)+'</span>';}
function nice(a){return a.replace('_ABYSSITE','').toLowerCase();}
var CLR=['BLUE_ABYSSITE','ORANGE_ABYSSITE','BROWN_ABYSSITE','YELLOW_ABYSSITE','PURPLE_ABYSSITE','GREY_ABYSSITE'];
function zset(name,aby){return O.nms.filter(function(x){return x.name===name&&x.abyssite===aby;}).map(function(x){return x.zone_id;}).filter(function(v,i,a){return a.indexOf(v)===i;}).sort(function(a,b){return a-b;}).join(',');}
function selOK(x){if(!sel)return true;if(sel.aby&&sel.aby.indexOf(x.abyssite)<0)return false;if(sel.nm&&x.name!==sel.nm)return false;
 if(sel.path&&x.abyssite!=='BLACK_ABYSSITE'&&zset(x.name,x.abyssite)!==sel.path)return false;return true;}
function paths(){
 var P={};O.nms.forEach(function(x){if(CLR.indexOf(x.abyssite)<0)return;var k=zset(x.name,x.abyssite);
  if(!P[k])P[k]={key:k,colour:x.abyssite,nm:x.name,zones:[],clear:[],colorful:[]};});
 var nm={};O.nms.forEach(function(x){(nm[x.name]=nm[x.name]||{aby:x.abyssite,z:zset(x.name,x.abyssite)});});
 Object.keys(nm).forEach(function(n){var v=nm[n],p=P[v.z];if(!p)return;if(v.aby==='CLEAR_ABYSSITE')p.clear.push(n);if(v.aby==='COLORFUL_ABYSSITE')p.colorful.push(n);});
 Object.keys(P).forEach(function(k){var seen={};O.nms.forEach(function(x){if(x.name===P[k].nm&&x.abyssite===P[k].colour&&!seen[x.zone]){seen[x.zone]=1;P[k].zones.push(x.zone.replace(/_/g,' '));}});});
 return Object.keys(P).map(function(k){return P[k];}).sort(function(a,b){return CLR.indexOf(a.colour)-CLR.indexOf(b.colour);});
}
function isel(c){return sel&&JSON.stringify(sel)===JSON.stringify(c);}
function box(x,y,w,h,lines,c,fill){var on=isel(c);var s='<g class="vwn" data-s=\''+esc(JSON.stringify(c)).replace(/'/g,'&#39;')+'\' style="cursor:pointer"><rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="6" fill="'+(fill||'none')+'" fill-opacity="0.18" stroke="'+(on?'#2a7de1':(fill||'#888'))+'" stroke-width="'+(on?3:1.5)+'"/>';
 lines.forEach(function(l,i){s+='<text x="'+(x+w/2)+'" y="'+(y+15+i*13)+'" text-anchor="middle" font-size="'+(i===0?11:10)+'" '+(i===0?'font-weight="700" ':'')+'fill="currentColor">'+esc(l)+'</text>';});return s+'</g>';}
function graph(){
 var P=paths(),rh=88,x0=[4,230,456,682],w=200,H=P.length*rh+44;
 var s='<svg width="900" height="'+H+'" xmlns="http://www.w3.org/2000/svg"><defs><marker id="vwm" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#888"/></marker></defs>';
 var hd=[['Clear (1253)',['CLEAR_ABYSSITE']],['Colorful (1254)',['COLORFUL_ABYSSITE']],['Path colour',CLR],['Black (1260)',['BLACK_ABYSSITE']]];
 hd.forEach(function(h,i){s+=box(x0[i],2,w,26,[h[0]],{aby:h[1]},'#888');});
 P.forEach(function(p,i){var y=36+i*rh,h=rh-12,cy=y+h/2,zl=p.zones.filter(function(z){return z.indexOf('[S]')<0;}).join(', ');
  var cl=p.clear.length>4?[p.clear.slice(0,4).join(', '),p.clear.slice(4).join(', ')]:[p.clear.join(', ')];
  s+=box(x0[0],y,w,h,['Clear: '+p.clear.length+' NM'+(p.clear.length>1?'s':'')].concat(cl,[zl.length>34?zl.slice(0,32)+'..':zl]),{aby:['CLEAR_ABYSSITE'],path:p.key},COL.CLEAR_ABYSSITE);
  s+=box(x0[1],y,w,h,['Colorful'].concat([p.colorful.join(', ')]),{aby:['COLORFUL_ABYSSITE'],path:p.key},COL.COLORFUL_ABYSSITE);
  s+=box(x0[2],y,w,h,[nice(p.colour)+' ('+O.ki[p.colour]+')',p.nm],{aby:[p.colour],path:p.key},COL[p.colour]);
  s+=box(x0[3],y,w,h,['Black','Yilbegan'],{aby:['BLACK_ABYSSITE']},COL.BLACK_ABYSSITE);
  [0,1,2].forEach(function(k){s+='<line x1="'+(x0[k]+w)+'" y1="'+cy+'" x2="'+(x0[k+1]-3)+'" y2="'+cy+'" stroke="#888" stroke-width="2" marker-end="url(#vwm)"/>';});
 });
 $('vw2-graph').innerHTML=s+'</svg><div class="muted" style="margin-top:4px">Each row is one path (zone group). Clear NMs convert to Colorful (1 in 10 on kill), then to that path\'s colour NM, then Yilbegan. Paths are not connected after Colorful. Click any box to filter the table.</div>';
 Array.prototype.forEach.call($('vw2-graph').querySelectorAll('.vwn'),function(g){g.addEventListener('click',function(){var c=JSON.parse(g.getAttribute('data-s'));sel=isel(c)?null:c;graph();table();});});
}
function strip(){
 var n=O.nms,b=n.filter(function(x){return x.status==='built';}).length,v=n.filter(function(x){return x.validation==='validated';}).length,p=n.filter(function(x){return x.validation==='partial';}).length,bad=n.filter(function(x){return x.validation==='issue';}).length;
 var dn={};n.forEach(function(x){dn[x.name]=1;});var c=[[Object.keys(dn).length,'distinct NMs'],[n.length,'NM spawns (NM x zone)'],[O.zones.length,'zones'],[b,'spawns built'],[n.length-b,'with gaps'],[v,'validated'],[p,'partly validated'],[bad,'with issues'],[O.orphans.length,'orphan scripts']];
 $('vw2-strip').innerHTML=c.map(function(x){return '<div class="cpcard"><b style="font-size:1.4em">'+x[0]+'</b><div class="muted">'+x[1]+'</div></div>';}).join('');
 $('vw2-srv').textContent=(O.db_checked?'Live DB cross-check on. ':'No DB connection: pool/spawn checks skipped. ')+'Source: '+O.root;
}
var GM=[];
function table(){
 var q=$('vw2-q').value.toLowerCase(),st=$('vw2-st').value,vs=$('vw2-vs').value,z=$('vw2-z').value,nm=$('vw2-nm').value;
 var rows=O.nms.filter(function(x){return (!q||(x.name+x.zone).toLowerCase().indexOf(q)>=0)&&(!st||x.status===st)&&(!vs||x.validation===vs)&&(!z||String(x.zone_id)===z)&&(!nm||x.name===nm)&&selOK(x);});
 $('vw2-sum').textContent='Showing '+rows.length+' of '+O.nms.length+' spawns'+(nm?' of '+nm+' in '+new Set(rows.map(function(x){return x.zone_id;})).size+' zones, paths: '+Array.from(new Set(rows.map(function(x){return nice(x.abyssite);}))).join(', '):'');
 $('vw2-tb').innerHTML=rows.map(function(x){var d=x.db;
  return '<tr class="vwr" data-k="'+esc(x.key)+'" style="cursor:pointer"><td><b>'+esc(x.name)+'</b></td><td>'+esc(x.zone)+' ('+x.zone_id+')</td><td><span style="color:'+COL[x.abyssite]+'">&#9679;</span> '+nice(x.abyssite)+' '+x.ki_id+'</td><td>'+(x.upgrade?nice(x.upgrade):'<span class="muted">final</span>')+'</td><td class="mono">'+(d?(d.hp==null?'-':d.hp):'-')+'</td><td class="vwc1">'+chip(x.status)+(x.gaps.length?' <span style="color:#c0392b" title="'+esc(x.gaps.join('; '))+'">'+x.gaps.length+'</span>':'')+'</td><td class="vwc2">'+chip(x.validation)+'</td></tr>';}).join('');
 Array.prototype.forEach.call(document.querySelectorAll('.vwr'),function(r){r.addEventListener('click',function(){detail(r.dataset.k);});});
 GM=rows;gmCmds();
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
var abySel=null;
var ACOL={Clear:'#bbbbbb',Colorful:'#dd99aa',Scarlet:'#d94a4a',Azure:'#3a8fe0',Viridian:'#3aa86a',Jade:'#35b38f',Sapphire:'#3a5ad8',Crimson:'#b02040',Emerald:'#2fb84a',Vermillion:'#e8602c',Indigo:'#5a3aa8'};
function abyRows(){var r=[];(O.abyssea_paths||O.abyssea_nms||[]).forEach(function(p){p.tiers.forEach(function(q){q.nms.forEach(function(n){r.push({zone:p.zone,tier:q.tier,name:n,pop:q.pop,drops:q.drops,colour:p.colour});});});});return r;}
function abyOK(r){var s=abySel;if(!s)return true;return (!s.zone||r.zone===s.zone)&&(!s.tier||r.tier===s.tier)&&(!s.name||r.name===s.name);}
function abyKey(c){return esc(JSON.stringify(c)).replace(/'/g,'&#39;');}
function abyGraph(){
 var P=O.abyssea_paths||O.abyssea_nms||[],rh=66,x0=[4,254,504],w=230,s='<svg width="880" height="'+(P.length*rh+34)+'" xmlns="http://www.w3.org/2000/svg">';
 ['Tier I: Clear Demilune pop','Tier II: Colorful Demilune pop','Tier III: colour KI pop, drops Atma'].forEach(function(h,i){
  var c={tier:i+1};s+='<g class="vwa" data-s=\''+abyKey(c)+'\' style="cursor:pointer"><rect x="'+x0[i]+'" y="2" width="'+w+'" height="22" rx="6" fill="'+[ACOL.Clear,ACOL.Colorful,'#888'][i]+'" fill-opacity="0.25" stroke="'+(isA(c)?'#2a7de1':'#888')+'" stroke-width="'+(isA(c)?3:1.5)+'"/><text x="'+(x0[i]+w/2)+'" y="17" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor">'+h+'</text></g>';});
 P.forEach(function(p,i){var y=30+i*rh;
  p.tiers.forEach(function(q,k){var c={zone:p.zone,tier:q.tier},nm=q.nms.join(', '),on=isA(c),col=k===0?ACOL.Clear:k===1?ACOL.Colorful:(ACOL[p.colour]||'#888');
   s+='<g class="vwa" data-s=\''+abyKey(c)+'\' style="cursor:pointer"><rect x="'+x0[k]+'" y="'+y+'" width="'+w+'" height="'+(rh-10)+'" rx="6" fill="'+col+'" fill-opacity="0.2" stroke="'+(on?'#2a7de1':col)+'" stroke-width="'+(on?3:1.5)+'"/><circle cx="'+(x0[k]+12)+'" cy="'+(y+12)+'" r="5" fill="'+col+'" stroke="#888"/><text x="'+(x0[k]+w/2)+'" y="'+(y+20)+'" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor">'+esc(nm.length>32?nm.slice(0,30)+'..':nm)+'</text><text x="'+(x0[k]+w/2)+'" y="'+(y+38)+'" text-anchor="middle" font-size="10" fill="currentColor">'+(k===0?esc(p.zone):k===1?esc(p.colour)+' ('+p.colour_ki+') drops':esc(q.drops.length>34?q.drops.slice(0,32)+'..':q.drops))+'</text></g>';
   if(k<2)s+='<line x1="'+(x0[k]+w)+'" y1="'+(y+28)+'" x2="'+(x0[k+1]-3)+'" y2="'+(y+28)+'" stroke="#888" stroke-width="2"/>';});
  var cz={zone:p.zone};s+='<g class="vwa" data-s=\''+abyKey(cz)+'\' style="cursor:pointer"><text x="'+(x0[2]+w+8)+'" y="'+(y+28)+'" font-size="11" font-weight="'+(isA(cz)?700:400)+'" fill="'+(isA(cz)?'#2a7de1':'currentColor')+'">&#9664; '+esc(p.zone)+'</text></g>';});
 $('vw2-abyg').innerHTML=s+'</svg>';
 Array.prototype.forEach.call($('vw2-abyg').querySelectorAll('.vwa'),function(g){g.addEventListener('click',function(){var c=JSON.parse(g.getAttribute('data-s'));abySel=isA(c)?null:c;['vw2-aq','vw2-anm','vw2-az','vw2-at'].forEach(function(i){$(i).value='';});abyGraph();abyDetail();});});abyDetail();
}
function isA(c){return abySel&&JSON.stringify(abySel)===JSON.stringify(c);}
function abyInit(){
 var R=abyRows(),P=O.abyssea_paths||O.abyssea_nms||[];
 var cards=[[new Set(R.map(function(r){return r.name;})).size,'Abyssea NMs'],[P.length,'zone paths'],[R.filter(function(r){return r.tier===1;}).length,'Tier I'],[R.filter(function(r){return r.tier===2;}).length,'Tier II'],[R.filter(function(r){return r.tier===3;}).length,'Tier III'],[P.length+2,'Demilune key items'],[P.length,'Atma drops'],[0,'built in DSP']];
 $('vw2-abys').innerHTML=cards.map(function(x){return '<div class="cpcard"><b style="font-size:1.4em">'+x[0]+'</b><div class="muted">'+x[1]+'</div></div>';}).join('');
 $('vw2-anm').innerHTML='<option value="">All NMs</option>'+Array.from(new Set(R.map(function(r){return r.name;}))).sort().map(function(n){return '<option>'+esc(n)+'</option>';}).join('');
 $('vw2-az').innerHTML='<option value="">All zones</option>'+P.map(function(p){return '<option>'+esc(p.zone)+'</option>';}).join('');
 ['vw2-aq','vw2-anm','vw2-az','vw2-at'].forEach(function(i){$(i).oninput=$(i).onchange=function(){abySel=null;abyGraph();abyDetail();};});
 $('vw2-ax').onclick=function(){abySel=null;['vw2-aq','vw2-anm','vw2-az','vw2-at'].forEach(function(i){$(i).value='';});abyGraph();abyDetail();};
 abyGraph();
}
function abyDetail(){var q=$('vw2-aq').value.toLowerCase(),nm=$('vw2-anm').value,z=$('vw2-az').value,tr=$('vw2-at').value,all=abyRows();
 var rows=all.filter(function(r){return abyOK(r)&&(!q||(r.name+r.zone+r.drops+r.pop).toLowerCase().indexOf(q)>=0)&&(!nm||r.name===nm)&&(!z||r.zone===z)&&(!tr||String(r.tier)===tr);});
 $('vw2-asum').textContent='Showing '+rows.length+' of '+all.length+' NMs'+(abySel?' (graph filter on)':'');
 $('vw2-atb').innerHTML=rows.map(function(r){var nx=r.tier===1?'Colorful Demilune (1565)':r.tier===2?r.colour+' Demilune':'Atma';
  return '<tr class="vwar" data-n="'+esc(r.name)+'" data-z="'+esc(r.zone)+'" style="cursor:pointer"><td><span style="color:'+(r.tier===3?ACOL[r.colour]:r.tier===2?ACOL.Colorful:ACOL.Clear)+'">&#9679;</span> <b>'+esc(r.name)+'</b></td><td>'+esc(r.zone)+'</td><td>'+r.tier+'</td><td>'+esc(r.pop)+'</td><td>'+esc(r.drops)+'</td><td>'+esc(nx)+'</td></tr>';}).join('');
 Array.prototype.forEach.call(document.querySelectorAll('.vwar'),function(tr){tr.addEventListener('click',function(){var p=(O.abyssea_paths||O.abyssea_nms||[]).filter(function(x){return x.zone===tr.dataset.z;})[0];
  $('vw2-ad').hidden=false;$('vw2-ad').innerHTML='<h3 style="margin:0">'+esc(tr.dataset.n)+'</h3><div class="muted">Abyssea - '+esc(p.zone)+', path: '+p.tiers.map(function(q){return 'Tier '+q.tier+' '+esc(q.nms.join(' / '));}).join(' &rarr; ')+'</div><div class="vwc vwc-warn">Not built in DSP. Data from FFXIclopedia/BG Wiki; spawn grid, HP and abilities are on the wiki page.'+(p.note?'<br>'+esc(p.note):'')+'</div>';});});
}
function more(){
 var n=O.npc;
 $('vw2-npc').innerHTML='<div class="vwc vwc-ok"><b>'+esc(n.name)+'</b>, '+esc(n.zone)+' ('+n.zone_id+'), '+esc(n.pos)+'. Event '+n.event+', price '+n.price+' gil.<br>'+esc(n.desc)+'<br><span class="mono">'+esc(n.script)+'</span></div>';
 $('vw2-aby').innerHTML='<div class="vwc vwc-warn">'+esc(O.abyssea)+'</div><div id="vw2-abys" class="cpcards"></div><div id="vw2-abyg" style="overflow-x:auto"></div><p class="muted">Each row is one zone path. Click a box, tier header or zone name to filter the table.</p><div><input id="vw2-aq" placeholder="Search NM, zone, drop"> <select id="vw2-anm"></select> <select id="vw2-az"></select> <select id="vw2-at"><option value="">Any tier</option><option value="1">Tier I</option><option value="2">Tier II</option><option value="3">Tier III</option></select> <button type="button" id="vw2-ax">Clear filter</button> <span id="vw2-asum" class="muted"></span></div><div class="table-wrap"><table><thead><tr><th>NM</th><th>Zone</th><th>Tier</th><th>Pop with</th><th>Drops</th><th>Next tier</th></tr></thead><tbody id="vw2-atb"></tbody></table></div><div id="vw2-ad" hidden></div>';abyInit();
 var sk=O.skills||{},ks=Object.keys(sk).sort();
 $('vw2-skills').innerHTML=ks.length?'<table><thead><tr><th>NM</th><th>Pool</th><th>List</th><th>Skills</th></tr></thead><tbody>'+ks.map(function(k){var q=sk[k];return '<tr><td>'+esc(k)+'</td><td class="mono">'+q.pool+'</td><td class="mono">'+q.list+(q.list>=9000?' (own)':'')+'</td><td>'+q.skills.map(function(s){return '<span style="color:'+(s.lua?'inherit':'#c0392b')+'" title="'+(s.lua?'Lua present':'no Lua')+'">'+esc(s.name)+'</span>';}).join(', ')+'</td></tr>';}).join('')+'</tbody></table>':'<div class="muted">No DB connection.</div>';
 var w=O.wiki||{},wk=Object.keys(w).sort(),miss=wk.filter(function(k){return w[k].indexOf('BGWiki')<0&&w[k].indexOf('FFXIclopedia')<0;});
 $('vw2-wiki').innerHTML='<div class="muted">'+wk.length+' pages checked in ffxi_zone_database.db; '+miss.length+' with no page in BG Wiki or FFXIclopedia (WikiWikiJP has no Voidwalker pages).</div><table><thead><tr><th>Page</th><th>BG Wiki</th><th>FFXIclopedia</th><th>WikiWikiJP</th></tr></thead><tbody>'+wk.map(function(k){var a=w[k];function m(x){return a.indexOf(x)>=0?'yes':'<span class="muted">-</span>';}return '<tr><td>'+esc(k)+'</td><td>'+m('BGWiki')+'</td><td>'+m('FFXIclopedia')+'</td><td>'+m('WikiWikiJP')+'</td></tr>';}).join('')+'</tbody></table>';
}
function load(){return fetch('/domains/voidwalker/overview.json').then(function(r){return r.json();}).then(function(j){O=j;strip();graph();table();extras();more();});}
function init(){
 var z=$('vw2-z');
 load().then(function(){$('vw2-nm').innerHTML='<option value="">All NMs</option>'+Array.from(new Set(O.nms.map(function(x){return x.name;}))).sort().map(function(n){return '<option>'+esc(n)+'</option>';}).join('');z.innerHTML='<option value="">All zones</option>'+O.zones.map(function(q){return '<option value="'+q.zone_id+'">'+esc(q.folder)+'</option>';}).join('');
  ['vw2-q','vw2-st','vw2-vs','vw2-z','vw2-nm'].forEach(function(i){$(i).oninput=$(i).onchange=table;});}).catch(function(e){$('vw2-sum').textContent='Failed to load: '+e.message;});
}
function gmCmds(){
 var nm=$('vw2-nm').value,zid=$('vw2-z').value,Z=(O&&O.zones)||[];
 function row(l,c){return '<tr><td>'+esc(l)+'</td><td><code>'+esc(c)+'</code></td><td><button type="button" class="vwcp" data-c="'+esc(c)+'">Copy</button></td></tr>';}
 var rows=GM;
 var h='<div class="vwc vwc-warn">Narrow the Voidwalker NMs list above (NM, zone, tier or a graph box). This list follows them. The NM is hidden until popped, so !gotoentity may refuse; use the spawnedOnly form (trailing 0) or walk to a pool position.</div>';
 if(rows.length>=O.nms.length){$('vw2-gm').innerHTML=h+'<div class="muted">Everything is showing. Narrow the filters first.</div>';return;}
 var zs=Array.from(new Set(rows.map(function(x){return x.zone_id;})));
 var keyOf={CLEAR_ABYSSITE:'!addkeyitem 1253',COLORFUL_ABYSSITE:'!addkeyitem 1254',BLACK_ABYSSITE:'!addkeyitem 1260'};
 var body='';
 zs.forEach(function(z){
  var zi=Z.filter(function(q){return q.zone_id===z;})[0]||{},zr=rows.filter(function(x){return x.zone_id===z;});
  body+='<tr><th colspan="3">'+esc(zi.folder||z)+' (zone '+z+')</th></tr>';
  var keys={};zr.forEach(function(x){if(keyOf[x.abyssite])keys[x.abyssite]=1;else if(x.ki_id)keys[x.abyssite]='!addkeyitem '+x.ki_id;});
  Object.keys(keys).forEach(function(k){body+=row('Key item for '+nice(k)+' tier',keys[k]===1?keyOf[k]:keys[k]);});
  zr.forEach(function(x){var p=x.db&&x.db.pos?' at '+x.db.pos.join(', '):'';
   body+=row('Warp to '+x.name+' (id '+x.id+')'+p,'!gotoentity '+x.id);
   body+=row('Warp spawnedOnly / check spawn: '+x.name,'!gotoentity '+x.id+' 0');
   body+=row('Is '+x.name+' spawned?','!getmobaction '+x.id);});
  (zi.pos_list||[]).forEach(function(q,i){body+=row('Pool position '+(i+1)+' of '+zi.pos_list.length,'!pos '+q.join(' ')+' '+z);});
 });
 $('vw2-gm').innerHTML=h+'<div class="muted">'+rows.length+' spawn row(s) in '+zs.length+' zone(s)</div><div class="table-wrap"><table><thead><tr><th>Purpose</th><th>Command</th><th></th></tr></thead><tbody>'+body+'</tbody></table></div>';
 Array.prototype.forEach.call(document.querySelectorAll('.vwcp'),function(b){b.onclick=function(){try{navigator.clipboard.writeText(b.dataset.c);}catch(e){}b.textContent='Copied';setTimeout(function(){b.textContent='Copy';},1200);};});
}
function tabs(){var P=Array.prototype.slice.call(document.querySelectorAll('.vwtab')),bar=$('vw2-tabs'),cur='Overworld';try{cur=localStorage.getItem('vwtab')||cur;}catch(e){}
 if(!P.some(function(p){return p.dataset.t===cur;}))cur='Overworld';
 function show(t){P.forEach(function(p){p.style.display=p.dataset.t===t?'':'none';});Array.prototype.forEach.call(bar.children,function(b){b.className='vwtb'+(b.textContent===t?' on':'');});try{localStorage.setItem('vwtab',t);}catch(e){}}
 bar.innerHTML=P.map(function(p){return '<button type="button" class="vwtb">'+esc(p.dataset.t)+'</button>';}).join('');
 Array.prototype.forEach.call(bar.children,function(b){b.onclick=function(){show(b.textContent);};});show(cur);}
tabs();
init();
})();
