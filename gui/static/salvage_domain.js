(function(){
var D=null,sel=null,tab='tracks';
var $=function(i){return document.getElementById(i);};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function jget(u){return fetch(u).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
var SC={'done':'#1e9e6a','built':'#1e9e6a','partial':'#d68910','not built':'#c0392b','unknown':'#888'};
var VC={ok:'#1e9e6a',warn:'#d68910',bad:'#c0392b',idle:'#888'};
function chip(t,c){return '<span class="chip cpst" style="border-color:'+c+';color:'+c+'">'+esc(t)+'</span>';}
function stChip(s){return chip(s,SC[s]||'#888');}
function vChip(v){return chip(v,VC[v]||'#888');}
function dim(v){return v==null?'<span class="muted">?</span>':esc(v);}
function load(){
 return jget('/domains/salvage/overview.json').then(function(d){D=d;strip();graph();lists();if(sel)detail(sel.kind,sel.id);}).catch(function(e){$('sv-sum').innerHTML='<b style="color:#c0392b">'+esc(e.message)+'</b>';});
}
function bar(o,colors){var t=0,k;for(k in o)t+=o[k];if(!t)return '<div class="cpbar"></div>';var s='<div class="cpbar">';for(k in o)s+='<span style="width:'+(100*o[k]/t)+'%;background:'+(colors[k]||'#888')+'" title="'+esc(k)+': '+o[k]+'"></span>';return s+'</div>';}
function strip(){
 var K=[['zone','Zones'],['track','Salvage I / II tracks'],['system','Systems'],['npc','NPCs']],h='';
 K.forEach(function(k){var s=D.summary[k[0]];h+='<div class="cpcard"><b>'+k[1]+'</b> <span class="muted">'+s.total+'</span>'+(s.total?bar(s.status,SC)+'<div class="muted">build status</div>'+bar(s.validation,VC)+'<div class="muted">validation</div>':'<div class="muted">none recorded</div>')+'</div>';});
 $('sv-strip').innerHTML=h;
 $('sv-sum').innerHTML='Scanned live Topaz, the DSP target (dsp-branches) and the LandSandBoat reference. Captures tagged to Remnants/Salvage: '+D.captures.length+'.';
}
function nodeBy(kind,id){var rows={zone:D.zones,track:D.tracks,system:D.systems,npc:D.npcs}[kind]||[];for(var i=0;i<rows.length;i++)if(String(rows[i].id)===String(id))return rows[i];}
function graph(){
 var nodes=[],edges=[],pos={},colx={zone:40,track:330,system:640},rh=44,y0=40;
 D.zones.forEach(function(z,i){nodes.push({k:'zone',id:z.id,label:z.name,sub:z.captures+' captures',st:z.status,v:z.validation,x:colx.zone,y:y0+i*rh*2});});
 D.tracks.forEach(function(t,i){nodes.push({k:'track',id:t.id,label:t.name,sub:'inst '+(t.topaz_instance_id==null?'?':t.topaz_instance_id)+' · DSP '+t.dsp_status,st:t.status,v:t.validation,x:colx.track,y:y0+i*rh});});
 D.systems.forEach(function(s,i){nodes.push({k:'system',id:s.id,label:s.name,sub:'',st:s.status,v:s.validation,x:colx.system,y:y0+i*rh*1.1});});
 nodes.forEach(function(n){pos[n.k+':'+n.id]=n;});
 D.tracks.forEach(function(t){edges.push(['zone:'+t.zone,'track:'+t.id]);D.systems.forEach(function(s){if((t.level==='II')===(s.id==='salvage2'))edges.push(['track:'+t.id,'system:'+s.id]);});});
 var H=y0+Math.max(D.tracks.length,D.systems.length*1.1)*rh+20,W=860,s='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;max-width:'+W+'px;font:12px sans-serif" role="img" aria-label="Salvage graph: zones, Salvage I and II tracks, systems">';
 [['Remnants zones',colx.zone],['Tracks',colx.track],['Systems',colx.system]].forEach(function(c){s+='<text x="'+c[1]+'" y="18" font-weight="700" fill="currentColor">'+c[0]+'</text>';});
 edges.forEach(function(e){var a=pos[e[0]],b=pos[e[1]];if(!a||!b)return;var x1=a.x+170,y1=a.y+15,x2=b.x,y2=b.y+15;s+='<path d="M'+x1+','+y1+' C'+(x1+60)+','+y1+' '+(x2-60)+','+y2+' '+x2+','+y2+'" fill="none" stroke="currentColor" opacity=".25"/>';});
 nodes.forEach(function(n){var on=sel&&sel.kind===n.k&&String(sel.id)===String(n.id),c=SC[n.st]||'#888';
  s+='<g class="svn" data-k="'+n.k+'" data-id="'+esc(n.id)+'" style="cursor:pointer"><rect x="'+n.x+'" y="'+n.y+'" width="170" height="30" rx="6" fill="'+c+'" fill-opacity=".14" stroke="'+c+'" stroke-width="'+(on?3:1.4)+'" stroke-dasharray="'+(n.st==='unknown'?'4 3':'0')+'"/>'+
   '<text x="'+(n.x+6)+'" y="'+(n.y+13)+'" fill="currentColor" font-weight="600">'+esc(n.label.length>24?n.label.slice(0,23)+'…':n.label)+'</text><text x="'+(n.x+6)+'" y="'+(n.y+25)+'" fill="currentColor" opacity=".65" font-size="10">'+esc(n.sub.length>30?n.sub.slice(0,29)+'…':n.sub)+'</text>'+
   '<circle cx="'+(n.x+160)+'" cy="'+(n.y+8)+'" r="4" fill="'+(VC[n.v]||'#888')+'"><title>validation: '+esc(n.v)+'</title></circle><title>'+esc(n.label+' - '+n.st)+'</title></g>';});
 s+='</svg>';$('sv-graph').innerHTML=s;
 $('sv-graph').onclick=function(e){var g=e.target.closest('.svn');if(g)detail(g.getAttribute('data-k'),g.getAttribute('data-id'));};
}
function cells(a){return a.map(function(c){return '<td>'+c+'</td>';}).join('');}
function rr(k,id,a){return '<tr class="cprow" data-k="'+k+'" data-id="'+esc(id)+'">'+cells(a)+'</tr>';}
function lists(){
 var T=[['tracks','Tracks ('+D.tracks.length+')'],['zones','Zones ('+D.zones.length+')'],['systems','Systems ('+D.systems.length+')'],['npcs','NPCs ('+D.npcs.length+')'],['mobs','Mob / NPC scripts'],['captures','Captures ('+D.captures.length+')'],['gaps','Open questions ('+D.open_questions.length+')']];
 var h='<div class="cptabs">'+T.map(function(t){return '<button type="button" class="chip'+(tab===t[0]?' cpact':'')+'" data-t="'+t[0]+'">'+t[1]+'</button>';}).join(' ')+'</div>',b='';
 if(tab==='tracks'){
  b='<thead><tr><th>Track</th><th>Topaz inst id</th><th>Row live</th><th>DSP inst id</th><th>LSB id</th><th>Time</th><th>Registered entities</th><th>Hooks</th><th>Mob / NPC scripts</th><th>Captures</th><th>Build</th><th>DSP</th><th>Valid.</th></tr></thead><tbody>'+D.tracks.map(function(t){return rr('track',t.id,['<b>'+esc(t.name)+'</b>',dim(t.topaz_instance_id),t.topaz_row_live?'yes':'<span class="muted">commented</span>',dim(t.dsp_instance_id),dim(t.lsb_instance_id),dim(t.time_limit),t.level==='I'?(t.topaz_entities==null?'<b style="color:#c0392b">none</b>':t.topaz_entities):'<span class="muted">n/a</span>',esc(t.hooks.length+' / 8'),t.mob_scripts+' / '+t.npc_scripts,t.captures,stChip(t.status),stChip(t.dsp_status),vChip(t.validation)]);}).join('')+'</tbody>';
 }else if(tab==='zones'){
  b='<thead><tr><th>Zone</th><th>Zone.lua T / D / L</th><th>IDs T / D / L</th><th>Instance files T / D / L</th><th>Mobs T / D / L</th><th>NPCs T / D / L</th><th>Captures</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.zones.map(function(z){var i=z.info,y=function(b){return b?'yes':'no';},t=function(f){return [i.topaz,i.dsp,i.lsb].map(f).join(' / ');};return rr('zone',z.id,['<b>'+esc(z.name)+'</b>',t(function(x){return y(x.zone_lua);}),t(function(x){return y(x.ids_lua);}),t(function(x){return x.instance_files.length;}),t(function(x){return x.mobs.length;}),t(function(x){return x.npcs.length;}),z.captures,stChip(z.status),vChip(z.validation)]);}).join('')+'</tbody>';
  b+='';
 }else if(tab==='systems'){
  b='<thead><tr><th>System</th><th>Evidence / note</th><th>Needs</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.systems.map(function(s){return rr('system',s.id,['<b>'+esc(s.name)+'</b>',esc(s.note),esc((s.needs||[]).join('; ')),stChip(s.status),vChip(s.validation)]);}).join('')+'</tbody>';
 }else if(tab==='npcs'){
  b='<thead><tr><th>NPC</th><th>Zone</th><th>Role</th><th>Note</th><th>Status</th><th>Valid.</th></tr></thead><tbody>'+D.npcs.map(function(n){return rr('npc',n.id,['<b>'+esc(n.name)+'</b>',esc(n.zone),esc(n.role),esc(n.note),stChip(n.status),vChip(n.validation)]);}).join('')+'</tbody>';
  h+='<div class="muted">Only NPCs named in a capture or source are listed. The Remnants entrance/rewards NPCs are not recorded yet, none are invented.</div>';
 }else if(tab==='mobs'){
  b='<thead><tr><th>Zone</th><th>Source</th><th>Mob scripts</th><th>NPC scripts</th></tr></thead><tbody>';
  D.zones.forEach(function(z){['topaz','dsp','lsb'].forEach(function(k){var i=z.info[k];b+='<tr>'+cells([esc(z.name),k,'<span title="'+esc(i.mobs.join(', '))+'">'+i.mobs.length+'</span> '+'<span class="muted">'+esc(i.mobs.slice(0,6).join(', '))+(i.mobs.length>6?', …':'')+'</span>','<span class="muted">'+i.npcs.length+': '+esc(i.npcs.slice(0,8).join(', '))+(i.npcs.length>8?', …':'')+'</span>'])+'</tr>';});});
  b+='</tbody>';
 }else if(tab==='captures'){
  b='<thead><tr><th>#</th><th>Zone</th><th>Label</th><th>Salvage II</th></tr></thead><tbody>'+D.captures.map(function(c){return '<tr>'+cells(['<a href="/captures/'+c.id+'">#'+c.id+'</a>',esc(c.zone||'?'),esc(c.label),c.salvage2?'yes':''])+'</tr>';}).join('')+'</tbody>';
 }else{
  b='<tbody>'+D.open_questions.map(function(q){return '<tr><td>'+esc(q)+'</td></tr>';}).join('')+'</tbody>';
 }
 $('sv-lists').innerHTML=h+'<div class="table-wrap"><table>'+b+'</table></div>';
 $('sv-lists').onclick=function(e){var t=e.target.closest('[data-t]');if(t){tab=t.getAttribute('data-t');lists();return;}var r=e.target.closest('.cprow');if(r&&!e.target.closest('a'))detail(r.getAttribute('data-k'),r.getAttribute('data-id'));};
}
function detail(kind,id){
 var r=nodeBy(kind,id);if(!r)return;sel={kind:kind,id:id};
 var skip={validation:1,vnote:1,info:1,note:1,needs:1,hooks:1},h='<div style="text-align:right"><button type="button" id="sv-x">Close</button></div><h3>'+esc(r.name||r.id)+' <span class="muted">'+kind+'</span> '+stChip(r.status)+' '+vChip(r.validation)+'</h3><table class="vwkv">';
 Object.keys(r).forEach(function(k){if(skip[k]||r[k]===null||r[k]===''||typeof r[k]==='object')return;h+='<tr><td class="muted">'+esc(k.replace(/_/g,' '))+'</td><td>'+esc(r[k])+'</td></tr>';});
 if(r.hooks)h+='<tr><td class="muted">instance hooks present</td><td>'+esc(r.hooks.join(', ')||'none')+'</td></tr>';
 if(r.note)h+='<tr><td class="muted">note</td><td>'+esc(r.note)+'</td></tr>';
 if(r.needs&&r.needs.length)h+='<tr><td class="muted">needs</td><td>'+esc(r.needs.join('; '))+'</td></tr>';
 h+='</table><div style="margin-top:8px"><label>Validation <select id="sv-vs">'+['idle','ok','warn','bad'].map(function(s){return '<option'+(r.validation===s?' selected':'')+'>'+s+'</option>';}).join('')+'</select></label> <input id="sv-vn" placeholder="Note (what was checked, against what)" value="'+esc(r.vnote)+'" style="width:50%"> <button type="button" id="sv-vsave">Save mark</button> <span id="sv-vmsg" class="muted"></span></div>';
 h+='<p class="muted">ok = checked against a capture or the client, warn = partly checked, bad = known wrong, idle = not checked. Marks are saved to data/salvage/validation.json.</p>';
 var d=$('sv-detail');d.innerHTML=h;d.hidden=false;
 $('sv-x').onclick=function(){d.hidden=true;sel=null;graph();};
 $('sv-vsave').onclick=function(){fetch('/domains/salvage/mark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:kind,id:String(id),state:$('sv-vs').value,note:$('sv-vn').value})}).then(function(x){return x.json().then(function(j){if(!x.ok)throw new Error(j.detail);return j;});}).then(function(){return load();}).catch(function(e){$('sv-vmsg').textContent=e.message;});};
 graph();d.scrollIntoView({block:'nearest'});
}
document.addEventListener('DOMContentLoaded',function(){
 $('sv-rebuild').onclick=function(){$('sv-sum').textContent='Rebuilding...';fetch('/domains/salvage/rebuild',{method:'POST'}).then(load);};
 load();
});
})();
