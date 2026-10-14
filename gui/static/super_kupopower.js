(function(){
var D=null,tab='zones',Q='',open={};
var $=function(i){return document.getElementById(i);};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function jget(u){return fetch(u).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
function jpost(u,b){return fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
var VC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'},SC={'wiki':'#888','visited':'#d68910','verified':'#1e9e6a','bad':'#c0392b','done':'#1e9e6a','partial':'#d68910','not built':'#c0392b'};
function chip(t,c){return '<span class="chip cpst" style="border-color:'+c+';color:'+c+'">'+esc(t)+'</span>';}
function sel(cls,val,opts,blank){return '<select class="'+cls+'">'+(blank?'<option value="">'+blank+'</option>':'')+opts.map(function(o){var v=o[0],l=o[1];return '<option value="'+esc(v)+'"'+(String(v)===String(val)?' selected':'')+'>'+esc(l)+'</option>';}).join('')+'</select>';}
function load(){return jget('/domains/super_kupopower/overview.json').then(function(d){D=d;draw();}).catch(function(e){$('kp-sum').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});}
function tabletOpts(){return D.tablets.map(function(t){return [t.id,t.name.replace('Tablet of ','')];});}
function itemTxt(it){return it?'<span class="mono">'+it.id+'</span> <span class="muted">['+esc(it.src)+']</span>':'<span class="muted">not in DSP item_basic.sql</span>';}
function vsel(kind,r){return sel('kv',r.validation,[['idle','idle'],['ok','ok'],['warn','warn'],['bad','bad']])+' <input class="kn" placeholder="note" value="'+esc(r.vnote)+'" style="width:160px"> <button type="button" class="kb" data-k="'+kind+'" data-id="'+esc(r.id)+'">Mark</button>';}
function draw(){
 var s=D.summary;
 $('kp-sum').innerHTML='Built '+esc(D.generated)+'. Sources: [W] ffxiclopedia (read 2026-10-12), [S] LSB mog_tablets.lua skeleton, [D] zone database. LSB has stub functions and one Valkurm location only; Topaz has nothing.';
 $('kp-strip').innerHTML=[['Zones',s.zones],['Wiki/custom spots',s.spots],['With coordinates',s.with_coords],['Verified',s.verified],['Powers',D.powers.length],['Tablets',D.tablets.length]].map(function(c){return '<div class="cpcard"><b>'+c[1]+'</b><div class="muted">'+c[0]+'</div></div>';}).join('');
 var T=[['zones','Zones & spots'],['tablets','Tablets & rewards'],['powers','Super Kupowers'],['npcs','NPCs'],['globals','Global / zone changes']];
 $('kp-tabs').innerHTML=T.map(function(t){return '<button type="button" class="chip kt'+(tab===t[0]?' cpact':'')+'" data-t="'+t[0]+'">'+t[1]+'</button>';}).join('');
 var b=$('kp-body');
 b.innerHTML=({zones:zonesV,tablets:tabletsV,powers:powersV,npcs:npcsV,globals:globalsV})[tab]();
 wire();
}
function zonesV(){
 var h='<div><input id="kp-q" placeholder="filter zone / grid / note" value="'+esc(Q)+'" style="width:260px"> <span class="muted">Wiki spots are grid squares reported by players; pick the tablet, stand on the spot, run !logpos and paste x y z.</span></div>';
 var q=Q.toLowerCase();
 D.zones.forEach(function(z){
  var rows=z.wiki_spots.concat(z.custom||[]).filter(function(s){return !q||(z.name+' '+s.grid+' '+s.wiki+' '+(s.note||'')).toLowerCase().indexOf(q)>=0;});
  if(q&&!rows.length)return;
  var nc=z.wiki_spots.concat(z.custom||[]).filter(function(s){return s.x!=null;}).length;
  h+='<details data-z="'+z.zoneid+'"'+(open[z.zoneid]||q?' open':'')+'><summary><b>'+esc(z.name)+'</b> <span class="muted">zone '+z.zoneid+' &middot; '+z.wiki_spots.length+' wiki spots &middot; '+nc+' with coordinates</span></summary>';
  h+='<table class="grid"><tr><th>Grid</th><th>Wiki note [W]</th><th>Tablet</th><th>X</th><th>Y (inv)</th><th>Z</th><th>Status</th><th>Note</th><th></th></tr>';
  rows.forEach(function(s){
   h+='<tr data-id="'+esc(s.id)+'"><td class="mono">'+esc(s.grid)+'</td><td>'+esc(s.wiki||'')+'</td><td>'+sel('st',s.tablet||'',tabletOpts(),'?')+'</td>'+
   ['x','y','z'].map(function(k){return '<td><input class="c" data-k="'+k+'" value="'+esc(s[k]==null?'':s[k])+'" size="7"></td>';}).join('')+
   '<td>'+sel('ss',s.status||'wiki',[['wiki','wiki'],['visited','visited'],['verified','verified'],['bad','bad']])+'</td><td><input class="sn" value="'+esc(s.note||'')+'" size="18"></td><td><button type="button" class="sb">Save</button>'+(String(s.id).indexOf('-c')>0?' <button type="button" class="sd">Delete</button>':'')+' <span class="muted sm"></span></td></tr>';
  });
  h+='</table><div class="muted">Add spot: grid <input class="ng" size="6" placeholder="G-8"> x <input class="nx" size="6"> y <input class="ny" size="6"> z <input class="nz" size="6"> '+sel('nt','',tabletOpts(),'tablet?')+' <button type="button" class="na">Add</button> <span class="muted nm"></span></div></details>';
 });
 return h;
}
function tabletsV(){
 var h='<p class="muted">'+esc(D.tablet_note)+' Retail pays Kupofried\'s Ring ('+itemTxt(D.kupofried_ring.item)+') plus a per-tablet second reward. Ids are looked up by exact name in the DSP item_basic.sql only; blank means no match, not "does not exist in the client".</p>';
 h+='<table class="grid"><tr><th>Tablet</th><th>LSB idx [S]</th><th>Current reward [W]</th><th>DSP item id</th><th>History</th><th>Validation</th></tr>';
 D.tablets.forEach(function(t){h+='<tr><td>'+esc(t.name)+'</td><td class="mono">'+t.lsb_index+'</td><td>'+esc(t.reward)+'</td><td>'+itemTxt(t.reward_item)+'</td><td>'+t.history.map(function(x){return esc(x.era)+': '+esc(x.reward)+(x.item?' ('+x.item.id+')':'');}).join('<br>')+'</td><td>'+vsel('tablet',t)+'</td></tr>';});
 h+='</table>';
 if(D.missing_items.length)h+='<p class="muted">No DSP item match: '+D.missing_items.map(esc).join(', ')+'</p>';
 return h;
}
function powersV(){
 var h='<p class="muted">3 random powers are active for one week; all 11 during Adventurer Appreciation Campaigns. LSB power numbers [S] shown as a reference only.</p><table class="grid"><tr><th>Power</th><th>LSB #</th><th>Effect [W]</th><th>Scope</th><th>Touches</th><th>DSP status</th><th>Validation</th></tr>';
 D.powers.forEach(function(p){h+='<tr><td><b>'+esc(p.name)+'</b></td><td class="mono">'+p.lsb_power+'</td><td>'+esc(p.effect)+'</td><td>'+esc(p.scope)+'</td><td>'+p.touches.map(esc).join(', ')+'</td><td>'+chip(p.impl,SC[p.impl]||'#888')+' '+esc(p.impl_note)+'</td><td>'+vsel('power',p)+'</td></tr>';});
 h+='</table><h4>Retired</h4><ul>'+D.retired_powers.map(function(r){return '<li>'+esc(r.name)+' <span class="muted">('+esc(r.when)+') '+esc(r.fate)+'</span></li>';}).join('')+'</ul>';
 h+='<p class="muted">Casket link: Myriad Mystery Boxes feeds <span class="mono">kupowersMMBPower</span> in caskets.lua (currently a commented stub); Treasure Hound maps to Gilfinder/Treasure Hunter +1 under Signet.</p>';
 return h;
}
function npcsV(){
 var h='<table class="grid"><tr><th>NPC / prop</th><th>Role</th><th>Zone</th><th>DSP id</th><th>Status</th><th>Note</th><th>Validation</th></tr>';
 D.npcs.forEach(function(n){h+='<tr><td><b>'+esc(n.name)+'</b></td><td>'+esc(n.role)+'</td><td class="mono">'+(n.zone==null?'unknown':n.zone)+'</td><td class="mono">'+(n.dsp_npcid==null?'-':n.dsp_npcid)+'</td><td>'+chip(n.status,SC[n.status]||'#888')+'</td><td>'+esc(n.note)+'</td><td>'+vsel('npc',n)+'</td></tr>';});
 return h+'</table>';
}
function globalsV(){
 var h='<table class="grid"><tr><th>Area</th><th>Detail [W]</th><th>Hook</th><th>Validation</th></tr>';
 D.globals.forEach(function(g){h+='<tr><td><b>'+esc(g.label)+'</b></td><td>'+esc(g.detail)+'</td><td>'+esc(g.hook)+'</td><td>'+vsel('global',g)+'</td></tr>';});
 return h+'</table>';
}
function wire(){
 var q=$('kp-q');if(q)q.addEventListener('input',function(){Q=q.value;var p=q.selectionStart;draw();var n=$('kp-q');n.focus();n.setSelectionRange(p,p);});
 document.querySelectorAll('.kt').forEach(function(b){b.onclick=function(){tab=b.dataset.t;draw();};});
 document.querySelectorAll('details[data-z]').forEach(function(d){d.addEventListener('toggle',function(){open[d.dataset.z]=d.open;});});
 document.querySelectorAll('.kb').forEach(function(b){b.onclick=function(){var tr=b.closest('tr');jpost('/domains/super_kupopower/mark',{kind:b.dataset.k,id:b.dataset.id,state:tr.querySelector('.kv').value,note:tr.querySelector('.kn').value}).then(load).catch(function(e){alert(e.message);});};});
 document.querySelectorAll('.sb').forEach(function(b){b.onclick=function(){var tr=b.closest('tr'),m=tr.querySelector('.sm'),body={id:tr.dataset.id,tablet:tr.querySelector('.st').value,status:tr.querySelector('.ss').value,note:tr.querySelector('.sn').value};
  tr.querySelectorAll('.c').forEach(function(i){body[i.dataset.k]=i.value;});
  jpost('/domains/super_kupopower/spot',body).then(function(){m.textContent='saved';return load();}).catch(function(e){m.textContent=e.message;m.style.color='#c0392b';});};});
 document.querySelectorAll('.sd').forEach(function(b){b.onclick=function(){if(!confirm('Delete this custom spot?'))return;jpost('/domains/super_kupopower/spot',{id:b.closest('tr').dataset.id,delete:true}).then(load).catch(function(e){alert(e.message);});};});
 document.querySelectorAll('.na').forEach(function(b){b.onclick=function(){var d=b.closest('details'),g=function(c){return d.querySelector(c).value;},m=d.querySelector('.nm');
  jpost('/domains/super_kupopower/spot',{id:'new',zoneid:d.dataset.z,grid:g('.ng'),x:g('.nx'),y:g('.ny'),z:g('.nz'),tablet:g('.nt'),status:g('.nx')?'visited':'wiki'}).then(function(){open[d.dataset.z]=true;return load();}).catch(function(e){m.textContent=e.message;m.style.color='#c0392b';});};});
}
$('kp-rebuild').onclick=function(){jpost('/domains/super_kupopower/rebuild',{}).then(load).catch(function(e){alert(e.message);});};
load();
})();
