(() => {
  if (!document.querySelector('.character-editor-page')) return;

  const style = document.createElement('style');
  style.id = 'characterEditorDenseUxStyles';
  style.textContent = `
    main.character-editor-page{padding:6px 8px 18px}
    .character-editor-page .ce-grid{grid-template-columns:240px minmax(0,1fr);gap:7px}
    .character-editor-page .ce-card{padding:7px}
    .character-editor-page .ce-list{max-height:78vh}
    .character-editor-page .ce-row{padding:4px 6px}
    .character-editor-page .ce-tabs{gap:3px;margin:6px 0}
    .character-editor-page .ce-tab{padding:4px 7px;font-size:11px}
    .character-editor-page .ce-data-block{margin:5px 0}
    .character-editor-page .ce-data-block>summary{padding:3px 0}
    .character-editor-page .ce-dense-field-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:4px 6px;margin-top:5px}
    .character-editor-page .ce-field-cell{display:flex;flex-direction:column;gap:2px;min-width:0;padding:4px 5px;border:1px solid var(--border,#333);border-radius:4px;background:rgba(127,127,127,.035)}
    .character-editor-page .ce-field-label{font-size:9px;text-transform:uppercase;letter-spacing:.035em;opacity:.62;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .character-editor-page .ce-field-value{font-size:12px;min-height:24px;display:flex;align-items:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .character-editor-page .ce-field-cell .ce-edit-input{width:100%;min-width:0;padding:3px 5px;font-size:12px;min-height:25px}
    .character-editor-page .ce-field-cell .ce-field-note{display:none}
    .character-editor-page .ce-dense-row-card{padding:6px;margin:4px 0}
    .character-editor-page .ce-dense-row-head{display:flex;align-items:center;gap:6px;min-height:20px}
    .character-editor-page .ce-dense-row-head strong{font-size:12px}
    .character-editor-page .ce-edit-actions{margin-top:5px}
    .character-editor-page .ce-edit-actions button{padding:3px 7px;font-size:11px}
    .character-editor-page .ce-raw-storage{margin:4px 0;border:1px dashed var(--border,#444);border-radius:5px;padding:4px 6px;opacity:.82}
    .character-editor-page .ce-raw-storage>summary{cursor:pointer;font-size:11px}
    .character-editor-page .ce-raw-storage .ce-card{margin-top:5px;max-height:100px;overflow:auto;font-size:10px}
    .character-editor-page .ce-inventory-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:6px;align-items:start}
    .character-editor-page details.ce-container{margin:0;padding:5px;min-width:0}
    .character-editor-page details.ce-container>summary{cursor:pointer;display:flex;gap:5px;align-items:center;font-weight:700;font-size:12px;padding:2px}
    .character-editor-page .ce-inventory-scroll{max-height:285px;overflow:auto;margin-top:4px;border:1px solid var(--border,#333);border-radius:4px}
    .character-editor-page .ce-inventory-scroll table{min-width:420px}
    .character-editor-page .ce-inventory-scroll th,.character-editor-page .ce-inventory-scroll td{padding:3px 4px;font-size:11px}
    .character-editor-page .ce-inventory-scroll th{font-size:9px}
    .character-editor-page .ce-icon{width:22px;height:22px}
    .character-editor-page .ce-inventory-name{line-height:1.15}
    .character-editor-page .ce-inventory-name strong{font-size:11px}
    .character-editor-page .ce-inventory-name .mono{font-size:9px}
    .character-editor-page .ce-inventory-actions .ce-toolbar{gap:2px;flex-wrap:nowrap}
    .character-editor-page .ce-inventory-actions button{padding:2px 4px;font-size:9px}
    .character-editor-page #categoryDescription{font-size:11px;margin:3px 0 5px}
    @media(max-width:1150px){.character-editor-page .ce-inventory-grid{grid-template-columns:1fr}}
    @media(max-width:900px){.character-editor-page .ce-grid{grid-template-columns:1fr}.character-editor-page .ce-list{max-height:25vh}}
  `;
  document.head.appendChild(style);

  const denseTables = new Set(['chars','char_jobs','char_exp','char_profile','char_stats','char_points','char_storage','char_unlocks']);
  const originalRenderScalarRow = window.renderScalarRow;

  function denseScalarRow(table,row,index,editable){
    const editMap=Object.fromEntries((editable||[]).map(f=>[f.name,f]));
    const fields=Object.entries(row).map(([k,v])=>{
      const meta=editMap[k];
      if(meta){
        const step=/(float|double|decimal|numeric)/i.test(meta.sql_type||'')?'any':'1';
        return `<label class="ce-field-cell"><span class="ce-field-label" title="${esc(k)} · ${esc(meta.sql_type||'')}">${esc(k)}</span><input class="ce-edit-input" data-table="${esc(table)}" data-row="${index}" data-field="${esc(k)}" data-original="${esc(v??'')}" type="${inputType(meta.sql_type)}" step="${step}" value="${esc(v??'')}" oninput="this.classList.toggle('ce-changed',this.value!==this.dataset.original)"></label>`;
      }
      return `<div class="ce-field-cell"><span class="ce-field-label" title="${esc(k)}">${esc(k)}</span><span class="ce-field-value mono" title="${esc(pretty(v))}">${esc(pretty(v))}</span></div>`;
    }).join('');
    const enabled=editableOnline()&&(editable||[]).length>0;
    const action=(editable||[]).length?`<div class="ce-edit-actions"><button ${enabled?'':'disabled'} onclick="previewScalarRow('${esc(table)}',${index},this)">Preview changes</button><span class="ce-muted">${enabled?'Offline write · preview required':'Character must be verifiably offline'}</span></div>`:'';
    return `<div class="ce-card ce-dense-row-card"><div class="ce-dense-row-head"><strong>${esc(rowLabel(table,row,index))}</strong><span class="sp"></span>${(editable||[]).length?pill(`${editable.length} editable`,'ok'):pill('read only')}</div><div class="ce-dense-field-grid">${fields}</div>${action}</div>`;
  }

  window.renderScalarRow=function(table,row,index,editable){
    const fieldCount=Object.keys(row||{}).length;
    if(denseTables.has(table)||fieldCount>=7) return denseScalarRow(table,row,index,editable);
    return originalRenderScalarRow(table,row,index,editable);
  };

  window.loadCategory=async function(key){
    if(!selectedChar)return;
    const tab=(selectedCharacterData?.tabs||[]).find(t=>t.key===key)||{};
    document.getElementById('categoryDescription').textContent=tab.description||'';
    const box=document.getElementById('categoryData');
    box.innerHTML='<div class="ce-muted">Loading…</div>';
    try{
      const j=await api(`/character-editor/characters/${selectedChar}/categories/${encodeURIComponent(key)}.json`);
      activeCategoryData=j;
      let html='';
      for(const [table,rows] of Object.entries(j.tables||{})){
        const editable=j.editors?.[table]||[];
        const open=(rows||[]).length<=8||denseTables.has(table)?' open':'';
        html+=`<details class="ce-data-block"${open}><summary>${esc(table)} · ${(rows||[]).length} row(s) ${editable.length?pill(editable.length+' editable fields','ok'):pill('read only')}</summary>`;
        (rows||[]).forEach((r,i)=>{html+=window.renderScalarRow(table,r,i,editable)});
        html+='</details>';
      }
      for(const [cap,p] of Object.entries(j.packed||{})){
        const decoded=Boolean(p.decoded);
        const badge=decoded?pill('semantic editor available','ok'):pill('raw storage only','warn');
        html+=`<details class="ce-raw-storage"><summary>Advanced physical storage · ${esc(cap)} · ${esc(p.location)} ${badge}</summary><div class="ce-muted" style="margin:4px 0">${decoded?'Decoded state is presented by the purpose-built editor above. Raw bytes are kept here only for diagnostics.':'No semantic renderer is available for this field yet.'}</div><div class="ce-card mono">${esc(pretty(p.value))}</div></details>`;
      }
      box.innerHTML=html||'<div class="ce-muted">No physical values detected for this category on the connected server.</div>';
    }catch(e){box.textContent=e.message}
  };

  window.loadInventory=async function(){
    if(!selectedChar)return;
    const box=document.getElementById('inventoryContainers');
    box.innerHTML='<div class="ce-muted">Loading…</div>';
    try{
      const j=await api(`/character-editor/characters/${selectedChar}/inventory.json`);
      const cards=(j.containers||[]).map(c=>{
        const cap=c.capacity===null||c.capacity===undefined?'capacity runtime/unknown':`${c.count}/${c.capacity}`;
        const rows=(c.rows||[]).map(r=>{
          const it=r.item||{},id=r.itemId??r.item_id??0,extra=r.extra&&r.extra.bytes!==undefined?`${r.extra.bytes}b`:'';
          return `<tr><td>${id?`<img class="ce-icon" src="/itemedit/${id}/icon.png" onerror="this.style.display='none'">`:''}</td><td>${esc(r.slot)}</td><td class="ce-inventory-name"><strong>${esc(it.name||('Item '+id))}</strong><div class="mono ce-muted">${esc(id)}</div></td><td>${esc(r.quantity)}</td><td class="ce-muted">${esc(extra)}</td></tr>`;
        }).join('')||'<tr><td colspan="5" class="ce-muted">Empty</td></tr>';
        const open=Number(c.count||0)>0?' open':'';
        return `<details class="ce-container ce-card"${open}><summary><span>${esc((c.label||c.name||'Container').replaceAll('_',' '))}</span>${pill(cap,c.capacity!==null&&c.count>=c.capacity?'warn':'')}<span class="sp"></span><span class="ce-muted">loc ${esc(c.location)}</span></summary><div class="ce-inventory-scroll"><table class="ce-table"><thead><tr><th></th><th>Slot</th><th>Item</th><th>Qty</th><th>Extra</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
      }).join('');
      box.innerHTML=`<div class="ce-inventory-grid">${cards}</div>`;
    }catch(e){box.textContent=e.message}
  };
})();
