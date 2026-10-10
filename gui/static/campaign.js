(function(){
var D=null,sel=null,tab='missions',F={nation:'',cat:'',st:'',q:''};
var $=function(i){return document.getElementById(i);};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function jget(u){return fetch(u).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
var SC={'done':'#1e9e6a','built':'#1e9e6a','partial':'#d68910','not built':'#c0392b','unknown':'#888'};
var VC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'};
var NATN={S:"San d'Oria",B:'Bastok',W:'Windurst'};
function chip(t,c){return '<span class="chip cpst" style="border-color:'+c+';color:'+c+'">'+esc(t)+'</span>';}
function stChip(s){return chip(s,SC[s]||'#888');}
function vChip(v){return chip(v,VC[v]||'#888');}
function ev(s){return s?'<span class="muted" title="C capture, D client DAT, W wiki, S server">['+esc(s)+']</span>':'';}
function load(){
 return jget('/domains/campaign/overview.json').then(function(d){D=d;strip();graph();lists();if(sel)detail(sel.kind,sel.id);}).catch(function(e){$('cp-sum').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});
}
function bar(o,colors){var t=0,k;for(k in o)t+=o[k];if(!t)return '<div class="cpbar"></div>';var s='<div class="cpbar">';for(k in o)s+='<span style="width:'+(100*o[k]/t)+'%;background:'+(colors[k]||'#888')+'" title="'+esc(k)+': '+o[k]+'"></span>';return s+'</div>';}
function strip(){
 var K=[['system','Systems'],['npc','NPCs'],['menu','Menu events'],['mission','Missions'],['reward','Rewards'],['quest','Quests']],h='';
 K.forEach(function(k){var s=D.summary[k[0]];h+='<div class="cpcard"><b>'+k[1]+'</b> <span class="muted">'+s.total+'</span>'+(s.total?bar(s.status,SC)+'<div class="muted">build status</div>'+bar(s.validation,VC)+'<div class="muted">validation</div>':'<div class="muted">none recorded</div>')+'</div>';});
 $('cp-strip').innerHTML=h;
 var c=D.capture_types,ct=Object.keys(c).map(function(k){return k+' '+c[k];}).join(' · ');
 $('cp-sum').innerHTML='Built '+esc(D.generated)+' from docs/campaign + curation.json. Captures tagged: '+D.captures.length+' ('+esc(ct)+'). Server checked: '+esc(D.server_root||'none')+'.';
}
function nodeBy(kind,id){var rows={system:D.systems,npc:D.npcs,menu:D.menus,mission:D.missions,reward:D.rewards}[kind]||[];for(var i=0;i<rows.length;i++)if(String(rows[i].id)===String(id))return rows[i];}
function graph(){
 var nodes=[],edges=[],pos={},colx={npc:60,system:360,cat:660,reward:940},rh=44,y0=40;
 var npcs=D.npcs.slice().sort(function(a,b){return (a.system||'').localeCompare(b.system||'');});
 npcs.forEach(function(n,i){nodes.push({k:'npc',id:n.id,label:n.name,sub:n.role,st:n.status,v:n.validation,x:colx.npc,y:y0+i*rh});});
 D.systems.forEach(function(s,i){nodes.push({k:'system',id:s.id,label:s.label,sub:'',st:s.status,v:s.validation,x:colx.system,y:y0+i*rh*1.1});});
 D.categories.forEach(function(c,i){var w={};for(var k in c.by_status)w[k]=c.by_status[k];var st=c.by_status['partial']||c.by_status['built']||c.by_status['done']?'partial':'not built';nodes.push({k:'cat',id:c.name,label:c.name,sub:c.count+' missions',st:st,v:'idle',x:colx.cat,y:y0+i*rh});});
 D.rewards.forEach(function(r,i){nodes.push({k:'reward',id:r.id,label:r.label,sub:r.kind,st:r.status,v:r.validation,x:colx.reward,y:y0+i*rh});});
 nodes.forEach(function(n){pos[n.k+':'+n.id]=n;});
 D.npcs.forEach(function(n){if(n.system)edges.push(['npc:'+n.id,'system:'+n.system]);});
 D.categories.forEach(function(c){edges.push(['system:opsmissions','cat:'+c.name]);});
 edges.push(['system:ops','system:opsmissions']);
 D.rewards.forEach(function(r){if(r.system)edges.push(['system:'+r.system,'reward:'+r.id]);});
 var H=y0+Math.max(npcs.length,D.systems.length*1.1,D.categories.length,D.rewards.length)*rh+20,W=1120,s='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;max-width:'+W+'px;font:12px sans-serif" role="img" aria-label="Campaign graph: NPCs, systems, mission categories, rewards">';
 [['NPCs',colx.npc],['Systems / menus',colx.system],['Mission categories',colx.cat],['Rewards',colx.reward]].forEach(function(c){s+='<text x="'+c[1]+'" y="18" font-weight="700" fill="currentColor">'+c[0]+'</text>';});
 edges.forEach(function(e){var a=pos[e[0]],b=pos[e[1]];if(!a||!b)return;var x1=a.x+170,y1=a.y+12,x2=b.x,y2=b.y+12;s+='<path d="M'+x1+','+y1+' C'+(x1+60)+','+y1+' '+(x2-60)+','+y2+' '+x2+','+y2+'" fill="none" stroke="currentColor" opacity=".3"/>';});
 nodes.forEach(function(n){var on=sel&&sel.kind===n.k&&String(sel.id)===String(n.id),c=SC[n.st]||'#888';
  s+='<g class="cpn" data-k="'+n.k+'" data-id="'+esc(n.id)+'" style="cursor:pointer"><rect x="'+n.x+'" y="'+n.y+'" width="170" height="30" rx="6" fill="'+c+'" fill-opacity=".14" stroke="'+c+'" stroke-width="'+(on?3:1.4)+'" stroke-dasharray="'+(n.st==='unknown'?'4 3':'0')+'"/>'+
   '<text x="'+(n.x+6)+'" y="'+(n.y+13)+'" fill="currentColor" font-weight="600">'+esc(n.label.length>24?n.label.slice(0,23)+'…':n.label)+'</text><text x="'+(n.x+6)+'" y="'+(n.y+25)+'" fill="currentColor" opacity=".65" font-size="10">'+esc(n.sub)+'</text>'+
   '<circle cx="'+(n.x+160)+'" cy="'+(n.y+8)+'" r="4" fill="'+(VC[n.v]||'#888')+'"><title>validation: '+esc(n.v)+'</title></circle><title>'+esc(n.label+' - '+n.st)+'</title></g>';});
 s+='</svg>';$('cp-graph').innerHTML=s;
 $('cp-graph').onclick=function(e){var g=e.target.closest('.cpn');if(!g)return;var k=g.getAttribute('data-k'),id=g.getAttribute('data-id');if(k==='cat'){tab='missions';F.cat=id;F.nation='';F.st='';F.q='';lists();$('cp-lists').scrollIntoView();return;}detail(k,id);};
}
function row(cells){return '<tr>'+cells.map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}
function lists(){
 var T=[['missions','Missions ('+D.missions.length+')'],['npcs','NPCs ('+D.npcs.length+')'],['menus','Menu events ('+D.menus.length+')'],['systems','Systems ('+D.systems.length+')'],['rewards','Rewards ('+D.rewards.length+')'],['captures','Captures ('+D.captures.length+')'],['gaps','Open questions ('+D.open_questions.length+')']];
 var h='<div class="cptabs">'+T.map(function(t){return '<button type="button" class="chip'+(tab===t[0]?' cpact':'')+'" data-t="'+t[0]+'">'+t[1]+'</button>';}).join(' ')+'</div>',b='';
 if(tab==='missions'){
  var cats=D.categories.map(function(c){return c.name;});
  h+='<div class="cpfilters"><input type="search" id="cp-q" placeholder="Search mission, giver, medal" value="'+esc(F.q)+'"><select id="cp-nat"><option value="">All nations</option>'+['S','B','W'].map(function(n){return '<option value="'+n+'"'+(F.nation===n?' selected':'')+'>'+NATN[n]+'</option>';}).join('')+'</select><select id="cp-cat"><option value="">All categories</option>'+cats.map(function(c){return '<option'+(F.cat===c?' selected':'')+'>'+esc(c)+'</option>';}).join('')+'</select></div>';
  var rows=D.missions.filter(function(m){return (!F.nation||m.nation===F.nation)&&(!F.cat||m.category===F.cat)&&(!F.q||(m.name+' '+m.giver+' '+m.min_medal).toLowerCase().indexOf(F.q.toLowerCase())>=0);});
  b='<thead><tr><th>Mission</th><th>Nation</th><th>Category</th><th>Min medal</th><th>Giver</th><th>Cost</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+rows.map(function(m){return '<tr class="cprow" data-k="mission" data-id="'+esc(m.id)+'">'+['<b>'+esc(m.name)+'</b> '+ev(m.ev),NATN[m.nation]||m.nation,esc(m.category),esc(m.min_medal),esc(m.giver)+' '+esc(m.giver_grid),esc(m.cost),stChip(m.status),vChip(m.validation)].map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join('')+'</tbody>';
  h+='<div class="muted">'+rows.length+' shown</div>';
 }else if(tab==='npcs'){
  b='<thead><tr><th>NPC</th><th>Role</th><th>Nation / zone</th><th>Grid</th><th>Wire id</th><th>DSP id</th><th>In server SQL</th><th>Events</th><th>Missions</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.npcs.map(function(n){return '<tr class="cprow" data-k="npc" data-id="'+esc(n.id)+'">'+[ '<b>'+esc(n.name)+'</b> '+ev(n.ev),esc(n.role),esc((n.nation||'?')+' / '+(n.zone||'?')),esc(n.grid||'?'),n.wire_id||'<span class="muted">?</span>',n.dsp_id||'<span class="muted">?</span>',n.in_server_sql===null?'<span class="muted">n/a</span>':(n.in_server_sql?'name found':'<b style="color:#c0392b">not found</b>'),esc((n.events||[]).join(', ')),n.missions||'',stChip(n.status),vChip(n.validation)].map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join('')+'</tbody>';
 }else if(tab==='menus'){
  b='<thead><tr><th>Event (csid)</th><th>NPC</th><th>Meaning</th><th>Decoded</th><th>Note</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.menus.map(function(m){var n=nodeBy('npc',m.npc);return '<tr class="cprow" data-k="menu" data-id="'+esc(m.id)+'">'+[m.event+' '+ev(m.ev),esc(n?n.name:m.npc),esc(m.label),esc(m.decoded),esc(m.note),stChip(m.status),vChip(m.validation)].map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join('')+'</tbody>';
 }else if(tab==='systems'){
  b='<thead><tr><th>System</th><th>Evidence</th><th>Gaps</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.systems.map(function(s){return '<tr class="cprow" data-k="system" data-id="'+esc(s.id)+'">'+['<b>'+esc(s.label)+'</b>',ev(s.ev),esc(s.gaps),stChip(s.status),vChip(s.validation)].map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join('')+'</tbody>';
 }else if(tab==='rewards'){
  b='<thead><tr><th>Reward</th><th>Kind</th><th>Note</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.rewards.map(function(r){return '<tr class="cprow" data-k="reward" data-id="'+esc(r.id)+'">'+['<b>'+esc(r.label)+'</b> '+ev(r.ev),esc(r.kind),esc(r.note),stChip(r.status),vChip(r.validation)].map(function(c){return '<td>'+c+'</td>';}).join('')+'</tr>';}).join('')+'</tbody>';
  h+='<div class="muted">Quests: none recorded in the research so far (none are invented here). Medal key items are unverified; see Open questions.</div>';
 }else if(tab==='captures'){
  b='<thead><tr><th>#</th><th>Type</th><th>Title</th><th>Uploader</th><th>Date</th><th>Missions</th></tr></thead><tbody>'+D.captures.map(function(c){return row(['<a href="/captures/'+c.id+'">#'+c.id+'</a>',esc(c.type)+(c.secondary?' <span class="muted">+'+esc(c.secondary)+'</span>':''),esc(c.title),esc(c.uploader),esc(c.date),esc(c.ops_missions)]);}).join('')+'</tbody>';
 }else{
  b='<tbody>'+D.open_questions.map(function(q){return row([esc(q)]);}).join('')+'</tbody>';
 }
 $('cp-lists').innerHTML=h+'<div class="table-wrap"><table>'+b+'</table></div>';
 $('cp-lists').onclick=function(e){var t=e.target.closest('[data-t]');if(t){tab=t.getAttribute('data-t');lists();return;}var r=e.target.closest('.cprow');if(r&&!e.target.closest('a'))detail(r.getAttribute('data-k'),r.getAttribute('data-id'));};
 var q=$('cp-q');if(q)q.oninput=function(){F.q=q.value;var p=q.selectionStart;lists();var q2=$('cp-q');q2.focus();q2.setSelectionRange(p,p);};
 var nt=$('cp-nat');if(nt)nt.onchange=function(){F.nation=nt.value;lists();};
 var ct=$('cp-cat');if(ct)ct.onchange=function(){F.cat=ct.value;lists();};
}
var LAB={id:'ID',name:'Name',label:'Label',role:'Role',nation:'Nation',zone:'Zone',zone_id:'Zone id',grid:'Map grid',wire_id:'Captured (wire) id',dsp_id:'DSP npc_list id',events:'Events',category:'Category',min_medal:'Min medal',giver:'Giver',giver_grid:'Giver grid',requirements:'Requirements',size:'Size',cost:'Cost',result:'Result',tiers:'Tiers',capture:'Capture state',note:'Note',gaps:'Gaps',kind:'Kind',event:'Event (csid)',decoded:'Decoded',npc:'NPC id',system:'System',ev:'Evidence'};
function detail(kind,id){
 var r=nodeBy(kind,id);if(!r)return;sel={kind:kind,id:id};
 var h='<div style="text-align:right"><button type="button" id="cp-x">Close</button></div><h3>'+esc(r.name||r.label||r.id)+' <span class="muted">'+kind+'</span> '+stChip(r.status)+' '+vChip(r.validation)+'</h3><table class="vwkv">';
 Object.keys(LAB).forEach(function(k){if(r[k]!==undefined&&r[k]!==null&&r[k]!==''&&k!=='ev')h+='<tr><td class="muted">'+LAB[k]+'</td><td>'+esc(Array.isArray(r[k])?r[k].join(', '):r[k])+'</td></tr>';});
 h+='<tr><td class="muted">Evidence</td><td>'+(esc(r.ev)||'<i>none</i>')+' <span class="muted">(C capture, D client DAT, W wiki, S server)</span></td></tr></table>';
 h+='<div style="margin-top:8px"><label>Validation <select id="cp-vs">'+['idle','ok','warn','bad'].map(function(s){return '<option'+(r.validation===s?' selected':'')+'>'+s+'</option>';}).join('')+'</select></label> <input id="cp-vn" placeholder="Note (what was checked, against what)" value="'+esc(r.vnote)+'" style="width:50%"> <button type="button" id="cp-vsave">Save mark</button> <span id="cp-vmsg" class="muted"></span></div>';
 h+='<p class="muted">ok = checked against a capture or the client, warn = partly checked, bad = known wrong, idle = not checked. Marks are saved to data/campaign/validation.json.</p>';
 var d=$('cp-detail');d.innerHTML=h;d.hidden=false;
 $('cp-x').onclick=function(){d.hidden=true;sel=null;graph();};
 $('cp-vsave').onclick=function(){fetch('/domains/campaign/mark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:kind,id:String(id),state:$('cp-vs').value,note:$('cp-vn').value})}).then(function(x){return x.json().then(function(j){if(!x.ok)throw new Error(j.detail);return j;});}).then(function(){return load();}).catch(function(e){$('cp-vmsg').textContent=e.message;});};
 graph();d.scrollIntoView({block:'nearest'});
}
document.addEventListener('DOMContentLoaded',function(){
 $('cp-rebuild').onclick=function(){$('cp-sum').textContent='Rebuilding...';fetch('/domains/campaign/rebuild',{method:'POST'}).then(load);};
 load();
});
})();
