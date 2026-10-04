(() => {
  if (location.pathname !== '/itemedit') return;
  const tools = document.getElementById('effectStagingTools');
  if (!tools || typeof mergeEffectRows !== 'function') return;

  const PRESETS = {
    fire_damage:{label:'Fire damage',kind:'damage',subeffect:1,element:1,damage:25,chance:20},
    ice_damage:{label:'Ice damage',kind:'damage',subeffect:2,element:2,damage:25,chance:20},
    wind_damage:{label:'Wind damage',kind:'damage',subeffect:3,element:3,damage:25,chance:20},
    earth_damage:{label:'Earth damage',kind:'damage',subeffect:4,element:4,damage:25,chance:20},
    lightning_damage:{label:'Lightning damage',kind:'damage',subeffect:5,element:5,damage:25,chance:20},
    water_damage:{label:'Water damage',kind:'damage',subeffect:6,element:6,damage:25,chance:20},
    light_damage:{label:'Light damage',kind:'damage',subeffect:7,element:7,damage:25,chance:20},
    dark_damage:{label:'Dark damage',kind:'damage',subeffect:8,element:8,damage:25,chance:20},
    hp_drain:{label:'HP drain',kind:'drain',proc:5,subeffect:21,element:8,damage:20,chance:20},
    mp_drain:{label:'MP drain',kind:'drain',proc:6,subeffect:22,element:8,damage:10,chance:20},
    tp_drain:{label:'TP drain',kind:'drain',proc:7,subeffect:22,element:8,damage:100,chance:20},
    dispel:{label:'Dispel',kind:'simple',proc:10,subeffect:8,chance:20},
    self_buff:{label:'Self buff',kind:'status',proc:12,chance:20,power:1,duration:30,handoff:true},
    absorb_status:{label:'Absorb status',kind:'status',proc:11,chance:20,handoff:true},
    death:{label:'Instant death',kind:'simple',proc:13,subeffect:19,chance:1,handoff:true},
    nm_specific:{label:'NM-specific scripted behavior',kind:'simple',proc:14,chance:100,handoff:true},
  };

  const row = (modId, value) => ({modId, value:Number(value)||0});
  const currentLineage = () => {
    const select = document.getElementById('srv');
    const text = `${select?.value || ''} ${select?.selectedOptions?.[0]?.textContent || ''}`.toUpperCase();
    if (text.includes('LSB') || text.includes('LANDSANDBOAT')) return 'LSB';
    if (text.includes('DSP') || text.includes('DARKSTAR')) return 'DSP';
    if (text.includes('TOPAZ')) return 'TOPAZ';
    return 'UNKNOWN';
  };
  const capability = (preset, lineage) => {
    if (preset.handoff) return 'server-code-required';
    if (lineage === 'LSB') return 'row-only';
    if (lineage === 'DSP' || lineage === 'TOPAZ') return 'verify-lineage';
    return 'unsupported';
  };

  const card = document.createElement('div');
  card.id = 'weaponEffectsPresetCard';
  card.className = 'edit-card wide';
  card.style.marginBottom = '10px';
  card.innerHTML = `
    <h3>Weapon Effects <span class="hint">structured additional-effect presets; staged only, never saved directly</span></h3>
    <div style="display:grid;grid-template-columns:minmax(180px,1fr) repeat(4,minmax(90px,120px));gap:6px;align-items:end">
      <label>Preset<select id="weaponEffectPreset">${Object.entries(PRESETS).map(([k,p])=>`<option value="${k}">${p.label}</option>`).join('')}</select></label>
      <label>Chance %<input id="weaponEffectChance" type="number" min="0" max="100" value="20"></label>
      <label>Damage / amount<input id="weaponEffectDamage" type="number" value="25"></label>
      <label>Status ID<input id="weaponEffectStatus" type="number" min="0" value="0"></label>
      <label>Power<input id="weaponEffectPower" type="number" value="1"></label>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <label>Duration (s)<input id="weaponEffectDuration" type="number" min="0" value="30" style="width:90px"></label>
      <label><input id="weaponEffectConditional" type="checkbox"> conditional / latent</label>
      <input id="weaponEffectLatentId" type="number" min="0" placeholder="latent ID" style="width:100px" disabled>
      <input id="weaponEffectLatentParam" type="number" placeholder="latent param" style="width:110px" disabled>
      <span id="weaponEffectCapability" class="chip mono"></span>
      <button id="weaponEffectPrimary" type="button">Stage rows</button>
      <button id="weaponEffectCopyHandoff" type="button">Copy server handoff</button>
    </div>
    <div id="weaponEffectPreview" class="mono muted" style="font-size:10px;margin-top:6px;white-space:pre-wrap"></div>`;
  tools.parentNode.insertBefore(card, tools);

  const $ = id => document.getElementById(id);
  function values(){
    const key=$('weaponEffectPreset').value, p=PRESETS[key], proc=p.proc || 1;
    const vals={key,p,proc,chance:Number($('weaponEffectChance').value),damage:Number($('weaponEffectDamage').value),status:Number($('weaponEffectStatus').value),power:Number($('weaponEffectPower').value),duration:Number($('weaponEffectDuration').value)};
    const rows=[row(431,proc)];
    if(p.subeffect) rows.push(row(499,p.subeffect));
    if(['damage','drain'].includes(p.kind)) rows.push(row(500,vals.damage));
    rows.push(row(501,vals.chance));
    if(p.element) rows.push(row(950,p.element));
    if(['status'].includes(p.kind) && vals.status) rows.push(row(951,vals.status));
    if(['status'].includes(p.kind) && vals.power) rows.push(row(952,vals.power));
    if(['status'].includes(p.kind) && vals.duration) rows.push(row(953,vals.duration));
    return {...vals,rows};
  }
  function applyPresetDefaults(){
    const p=PRESETS[$('weaponEffectPreset').value];
    $('weaponEffectChance').value=p.chance ?? 20;
    $('weaponEffectDamage').value=p.damage ?? 0;
    $('weaponEffectPower').value=p.power ?? 1;
    $('weaponEffectDuration').value=p.duration ?? 30;
    refresh();
  }
  function refresh(){
    const v=values(), lineage=currentLineage(), cap=capability(v.p,lineage), conditional=$('weaponEffectConditional').checked;
    $('weaponEffectLatentId').disabled=!conditional; $('weaponEffectLatentParam').disabled=!conditional;
    $('weaponEffectCapability').textContent=`${lineage} · ${cap}`;
    $('weaponEffectPrimary').textContent=cap==='row-only'?'Stage rows':'Server handoff';
    $('weaponEffectPrimary').disabled=cap==='unsupported';
    $('weaponEffectCopyHandoff').style.display=cap==='row-only'?'none':'';
    $('weaponEffectPreview').textContent=`${v.p.label} · ${v.chance}%${v.damage?` · amount ${v.damage}`:''}${v.status?` · status ${v.status}`:''}\n`+
      `${conditional?'item_latents':'item_mods'}: `+v.rows.map(r=>`${r.modId}=${r.value}`).join(', ')+(cap==='row-only'?'':'\nNot auto-staged: verify/implement the selected lineage handler first.');
  }
  function handoffPayload(){
    const v=values(), lineage=currentLineage();
    return {kind:'weapon-additional-effect',lineage,preset:v.key,label:v.p.label,capability:capability(v.p,lineage),effect:{procType:v.proc,chance:v.chance,damage:v.damage,status:v.status,power:v.power,duration:v.duration},rows:v.rows,storage:$('weaponEffectConditional').checked?'item_latents':'item_mods',latentId:$('weaponEffectConditional').checked?Number($('weaponEffectLatentId').value):null,latentParam:$('weaponEffectConditional').checked?Number($('weaponEffectLatentParam').value):null,warning:'Verify proc numbering, handler semantics, stacking/overwrite rules, target, messages, and status behavior in the active server tree before implementation.'};
  }
  async function copyHandoff(){
    const text=JSON.stringify(handoffPayload(),null,2);
    try{ await navigator.clipboard.writeText(text); $('weaponEffectPreview').textContent+='\nServer handoff copied to clipboard.'; }
    catch{ $('weaponEffectPreview').textContent+='\n'+text; }
  }
  function stage(){
    const v=values(), lineage=currentLineage(), cap=capability(v.p,lineage);
    if(cap!=='row-only'){ copyHandoff(); return; }
    let rows=v.rows;
    const conditional=$('weaponEffectConditional').checked;
    if(conditional){
      const latentId=Number($('weaponEffectLatentId').value), latentParam=Number($('weaponEffectLatentParam').value);
      if(!Number.isInteger(latentId) || latentId<0){ alert('Enter a valid latent ID.'); return; }
      rows=rows.map(r=>({...r,latentId,latentParam}));
      mergeEffectRows('latents',rows);
    }else mergeEffectRows('mods',rows);
    $('weaponEffectPreview').textContent+='\nStaged through the existing Item Editor effect payload. Save Item still performs normal validation and atomic backup/journal handling.';
  }

  $('weaponEffectPreset').addEventListener('change',applyPresetDefaults);
  ['weaponEffectChance','weaponEffectDamage','weaponEffectStatus','weaponEffectPower','weaponEffectDuration','weaponEffectConditional','weaponEffectLatentId','weaponEffectLatentParam'].forEach(id=>$(id).addEventListener('input',refresh));
  document.getElementById('srv')?.addEventListener('change',refresh);
  $('weaponEffectPrimary').onclick=stage;
  $('weaponEffectCopyHandoff').onclick=copyHandoff;
  applyPresetDefaults();
})();
