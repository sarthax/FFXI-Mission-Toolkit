(() => {
  if (!document.querySelector('.character-editor-page') || typeof loadInventory !== 'function') return;

  let inventoryContainers = [];
  const originalLoadInventory = loadInventory;
  const originalOpenItemBrowser = openItemBrowser;

  function safeDestinationContainers() {
    return inventoryContainers.filter(c => c.capacity !== null && c.capacity !== undefined && Number(c.location) !== 3);
  }

  async function fetchInventoryState() {
    if (!selectedChar) return [];
    const payload = await api(`/character-editor/characters/${selectedChar}/inventory.json`);
    inventoryContainers = payload?.containers || [];
    return inventoryContainers;
  }

  function ensureBagSelector() {
    const dialog = document.getElementById('itemDialog');
    if (!dialog) return null;
    let select = document.getElementById('itemLocation');
    if (!select) {
      const qty = document.getElementById('itemQty');
      const label = document.createElement('label');
      label.innerHTML = 'Bag <select id="itemLocation" style="min-width:160px"></select>';
      (qty?.closest('.ce-toolbar') || dialog).appendChild(label);
      select = label.querySelector('select');
    }
    const destinations = safeDestinationContainers();
    select.innerHTML = destinations.map(c => {
      const disabled = Number(c.capacity || 0) <= 0 || Number(c.count || 0) >= Number(c.capacity || 0);
      const text = `${c.label || c.name || `Container ${c.location}`} (${c.count}/${c.capacity})`;
      return `<option value="${Number(c.location)}" ${disabled ? 'disabled' : ''}>${esc(text)}</option>`;
    }).join('');
    if (![...select.options].some(o => !o.disabled)) {
      select.innerHTML = '<option value="0" disabled>No verified destination has free space</option>';
    } else if ([...select.options].some(o => Number(o.value) === 0 && !o.disabled)) {
      select.value = '0';
    }
    return select;
  }

  openItemBrowser = function() {
    originalOpenItemBrowser();
    const refresh = async () => {
      try {
        if (!inventoryContainers.length) await fetchInventoryState();
        ensureBagSelector();
      } catch (e) {
        console.warn('Character Editor bag selector:', e);
      }
    };
    refresh();
  };

  previewItem = async function() {
    if (!selectedChar || !selectedItem) return;
    const quantity = Number(document.getElementById('itemQty').value || 1);
    const select = ensureBagSelector();
    const location = Number(select?.value ?? 0);
    try {
      const j = await api(`/character-editor/characters/${selectedChar}/items/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({item_id:selectedItem.item_id, quantity, location})
      });
      lastPreview = j;
      const issues = (j.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      document.getElementById('itemPreview').textContent = `Destination: ${j.location_name || `location ${j.location}`} slot ${j.slot ?? 'n/a'}\nQuantity: ${j.quantity}\n${issues}`;
      document.getElementById('confirmButton').disabled = !j.ready;
    } catch (e) {
      lastPreview = null;
      document.getElementById('confirmButton').disabled = true;
      document.getElementById('itemPreview').textContent = e.message;
    }
  };

  confirmItem = async function() {
    if (!selectedChar || !selectedItem || !lastPreview?.ready) return;
    const quantity = Number(document.getElementById('itemQty').value || 1);
    const location = Number(document.getElementById('itemLocation')?.value ?? 0);
    const name = lastPreview.location_name || `location ${location}`;
    if (!confirm(`Add ${quantity} × ${selectedItem.name} to ${name}, slot ${lastPreview.slot}?`)) return;
    try {
      await api(`/character-editor/characters/${selectedChar}/items/add`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({item_id:selectedItem.item_id, quantity, location, approved:true})
      });
      document.getElementById('itemDialog')?.close();
      await selectCharacter(selectedChar);
      await loadInventory();
    } catch (e) {
      alert(e.message);
    }
  };

  async function manageInventoryRow(container, row, action) {
    if (!selectedChar || !editableOnline()) return;
    const itemId = Number(row.itemId ?? row.item_id ?? 0);
    const itemName = row.item?.name || `Item ${itemId}`;
    const body = {
      source_location:Number(container.location),
      source_slot:Number(row.slot),
      action
    };

    if (action === 'quantity') {
      const next = prompt(`New quantity for ${itemName} (current ${row.quantity}):`, String(row.quantity));
      if (next === null) return;
      body.quantity = Number(next);
    } else if (action === 'move') {
      const destinations = safeDestinationContainers().filter(c => Number(c.capacity || 0) > Number(c.count || 0));
      if (!destinations.length) {
        alert('No directly sized destination container currently has free space.');
        return;
      }
      const menu = destinations.map(c => `${c.location}: ${c.label || c.name} (${c.count}/${c.capacity})`).join('\n');
      const defaultDestination = destinations.find(c => Number(c.location) !== Number(container.location)) || destinations[0];
      const chosen = prompt(`Move ${itemName} to which location?\n\n${menu}\n\nThe first free slot will be used.`, String(defaultDestination.location));
      if (chosen === null) return;
      body.destination_location = Number(chosen);
    }

    try {
      const preview = await api(`/character-editor/characters/${selectedChar}/inventory/preview`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
      });
      const issues = (preview.issues || []).map(i => `${i.blocking ? 'BLOCK' : 'WARN'}: ${i.message}`).join('\n');
      if (!preview.ready) {
        alert(issues || 'This inventory operation is not write-ready.');
        return;
      }
      let summary = `${action.toUpperCase()} ${itemName}\nSource: ${container.label || container.name} slot ${row.slot}`;
      if (action === 'quantity') summary += `\nQuantity: ${row.quantity} → ${preview.quantity_after}`;
      if (action === 'move') summary += `\nDestination: ${preview.destination_name} slot ${preview.destination_slot}`;
      if (action === 'remove') summary += '\nThis deletes the inventory row.';
      if (issues) summary += `\n\n${issues}`;
      if (!confirm(`${summary}\n\nApply this change?`)) return;

      await api(`/character-editor/characters/${selectedChar}/inventory/apply`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...body, expected_source_fingerprint:preview.source_fingerprint, approved:true})
      });
      await selectCharacter(selectedChar);
      await loadInventory();
    } catch (e) {
      alert(e.message);
    }
  }

  async function enhanceInventory() {
    if (!selectedChar) return;
    try {
      const containers = await fetchInventoryState();
      const nodes = [...document.querySelectorAll('#inventoryContainers .ce-container')];
      const offline = editableOnline();
      nodes.forEach((node, index) => {
        const container = containers[index];
        if (!container) return;
        const header = node.querySelector('thead tr');
        if (header && !header.querySelector('.ce-inventory-actions-head')) {
          const th = document.createElement('th');
          th.className = 'ce-inventory-actions-head';
          th.textContent = 'Actions';
          header.appendChild(th);
        }
        const bodyRows = [...node.querySelectorAll('tbody tr')];
        (container.rows || []).forEach((row, rowIndex) => {
          const tr = bodyRows[rowIndex];
          if (!tr || tr.querySelector('.ce-inventory-actions')) return;
          const td = document.createElement('td');
          td.className = 'ce-inventory-actions';
          const locked = !offline || Number(container.location) === 3;
          td.innerHTML = `<div class="ce-toolbar"><button data-action="quantity" ${locked ? 'disabled' : ''}>Qty</button><button data-action="move" ${locked ? 'disabled' : ''}>Move</button><button data-action="remove" ${locked ? 'disabled' : ''}>Remove</button></div>`;
          td.querySelectorAll('button').forEach(button => button.addEventListener('click', () => manageInventoryRow(container, row, button.dataset.action)));
          tr.appendChild(td);
        });
      });
      ensureBagSelector();
      const note = document.querySelector('#pane-inventory > .ce-muted');
      if (note) note.textContent = 'Inventory administration is offline-only. Add/move destinations are limited to containers with directly verifiable capacity; Storage and Temporary Items remain protected.';
    } catch (e) {
      console.warn('Character Editor inventory management:', e);
    }
  }

  loadInventory = async function() {
    await originalLoadInventory();
    await enhanceInventory();
  };
})();
