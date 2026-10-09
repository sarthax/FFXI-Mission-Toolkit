/* Reusable, read-only item search component for workbench item surfaces.
 * Consumers provide their endpoint and selection callback, preserving
 * module-specific rules and write-preview boundaries.
 */
(() => {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,
    char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const itemId = row => Number(row.item_id ?? row.id);
  const displayName = row => String(row.name || row.item_name || ('Item #' + itemId(row))).replace(/_/g,' ');
  const iconSrc = id => '/itemedit/' + Number(id) + '/icon.png';
  function rowHtml(row) {
    const id=itemId(row);
    return '<span class="ahc-item-cell"><img class="ahc-item-icon" alt="" loading="lazy" src="' +
      iconSrc(id) + '" onerror="this.style.display=\'none\'"><span><b>' +
      escapeHtml(displayName(row)) + '</b><small> #' + id +
      (row.category_path ? ' · ' + escapeHtml(row.category_path) : '') +
      '</small></span></span>';
  }
  function bind({input, results, endpoint, onSelect, request, debounceMs=180, limit=25}) {
    if (!input || !results || typeof request !== 'function' || typeof onSelect !== 'function')
      throw Error('Item picker requires input, results, request and onSelect');
    let seq=0, timer=null, rows=[];
    async function search() {
      const query=input.value.trim(), mine=++seq;
      if(query.length<2 && !/^\d+$/.test(query)) { results.hidden=true; rows=[]; return; }
      try {
        const data=await request(endpoint+encodeURIComponent(query)+'&limit='+limit);
        if(mine!==seq)return;
        rows=data.rows || [];
        results.innerHTML=rows.map((row,i)=>'<div data-item-choice="'+i+'" role="option">'+rowHtml(row)+'</div>').join('') ||
          '<div class="mut">No matching items.</div>';
        results.hidden=false;
      } catch(error) { if(mine===seq){results.textContent=error.message;results.hidden=false;} }
    }
    input.addEventListener('input',()=>{
      ++seq;clearTimeout(timer);timer=setTimeout(search,debounceMs);
    });
    results.addEventListener('click',event=>{
      const target=event.target.closest('[data-item-choice]');
      if(!target)return;
      const item=rows[Number(target.dataset.itemChoice)];
      if(item){onSelect(item);results.hidden=true;}
    });
    input.addEventListener('keydown',event=>{
      if(event.key==='Escape')results.hidden=true;
      if(event.key==='Enter' && !results.hidden && rows.length){
        event.preventDefault();
        const query=input.value.toLowerCase().trim();
        const item=rows.find(row=>String(itemId(row))===query ||
          displayName(row).toLowerCase()===query) || rows[0];
        onSelect(item);results.hidden=true;
      }
    });
    return {search};
  }
  window.WorkbenchItemPicker=Object.freeze({bind,rowHtml,iconSrc,itemId,displayName,escapeHtml});
})();
