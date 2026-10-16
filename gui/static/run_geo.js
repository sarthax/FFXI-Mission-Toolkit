(function(){
var $=function(i){return document.getElementById(i);};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function jget(u){return fetch(u).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});});}
var BC={missing:'#c0392b',partial:'#d68910',done:'#1e9e6a',hold:'#888'};
var F={st:'',ar:'',q:''};
function draw(){
 jget('/domains/run_geo/overview.json').then(function(d){
  var el=$('rg-body');
  var L=d.items.filter(function(x){return (!F.st||x.status===F.st)&&(!F.ar||x.area===F.ar)&&(!F.q||(x.title+' '+x.detail+' '+x.source).toLowerCase().indexOf(F.q.toLowerCase())>=0);});
  $('rg-strip').innerHTML=d.states.map(function(s){return '<div class="cpcard" style="border-color:'+BC[s]+'"><b style="color:'+BC[s]+'">'+d.counts[s]+'</b><br>'+s+'</div>';}).join('');
  el.innerHTML='<div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0"><input type="search" id="rg-q" placeholder="Search" value="'+esc(F.q)+'" style="flex:1;min-width:180px">'+
   '<select id="rg-st"><option value="">All status</option>'+d.states.map(function(s){return '<option'+(s===F.st?' selected':'')+'>'+s+'</option>';}).join('')+'</select>'+
   '<select id="rg-ar"><option value="">All areas</option>'+d.areas.map(function(s){return '<option'+(s===F.ar?' selected':'')+'>'+esc(s)+'</option>';}).join('')+'</select> <span id="rg-msg" class="muted"></span></div>'+
   '<div class="table-wrap"><table><thead><tr><th>Area</th><th>Item</th><th>Ev.</th><th>Detail</th><th>Source</th><th>Status</th><th>Note</th><th></th></tr></thead><tbody>'+
   L.map(function(x){return '<tr data-id="'+esc(x.id)+'"><td>'+esc(x.area)+'</td><td><b>'+esc(x.title)+'</b></td><td class="mono">'+esc(x.evidence)+'</td><td>'+esc(x.detail)+'</td><td class="muted">'+esc(x.source)+'</td>'+
    '<td><select data-k="status" style="color:'+BC[x.status]+'">'+d.states.map(function(s){return '<option'+(s===x.status?' selected':'')+'>'+s+'</option>';}).join('')+'</select></td>'+
    '<td><input data-k="note" value="'+esc(x.note)+'" style="width:160px"></td><td><button type="button" class="rgb">Save</button></td></tr>';}).join('')+'</tbody></table></div>';
  $('rg-q').oninput=function(){F.q=this.value;clearTimeout(draw.t);draw.t=setTimeout(draw,250);};
  $('rg-st').onchange=function(){F.st=this.value;draw();};
  $('rg-ar').onchange=function(){F.ar=this.value;draw();};
  Array.prototype.forEach.call(el.querySelectorAll('.rgb'),function(b){b.onclick=function(){var tr=b.closest('tr'),ch={};
   Array.prototype.forEach.call(tr.querySelectorAll('[data-k]'),function(i){ch[i.dataset.k]=i.value;});
   fetch('/domains/run_geo/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:tr.dataset.id,changes:ch})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.status);return j;});}).then(draw).catch(function(e){$('rg-msg').textContent='Save failed: '+e.message;});};});
 }).catch(function(e){$('rg-body').innerHTML='<span class="muted">Unavailable: '+esc(e.message)+'</span>';});
}
draw();
})();
