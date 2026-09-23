import { DatReader } from "./DatReader.js";
import { parseTextureBlock } from "./TextureParser.js";
import { decodeMzb, decodeMmb } from "./ZoneDecrypt.js";
import { parseMzbBlock } from "./MzbParser.js";
import { parseMmbBlock } from "./MmbParser.js";
const DATHEAD_SIZE = 8;
const BLOCK_PADDING = 8;
const BLOCK_LIMIT = 2e3;
const BLOCK_IMG = 32;
const BLOCK_MZB = 28;
const BLOCK_MMB = 46;
function parseBlockChain(reader) {
  const blocks = [];
  let offset = 0;
  while (offset < reader.length - DATHEAD_SIZE) {
    reader.seek(offset);
    const name = reader.readString(4);
    const packed = reader.readUint32();
    const type = packed & 127;
    const nextUnits = packed >> 7 & 524287;
    const blockSize = nextUnits * 16;
    blocks.push({
      name,
      type,
      nextUnits,
      dataOffset: offset + DATHEAD_SIZE,
      dataLength: Math.max(0, blockSize - DATHEAD_SIZE)
    });
    if (nextUnits === 0) break;
    offset += blockSize;
    if (blocks.length > BLOCK_LIMIT) break;
  }
  return blocks;
}
function readMmbName(decryptedData) {
  if (decryptedData.length < 32) return "";
  const bytes = decryptedData.slice(16, 32);
  let end = bytes.indexOf(0);
  if (end === -1) end = 16;
  return new TextDecoder("utf-8").decode(bytes.subarray(0, end)).trim();
}
function parseTexturesFromDat(buffer) {
  const reader = new DatReader(buffer);
  const blocks = parseBlockChain(reader);
  const result = /* @__PURE__ */ new Map();
  const imgBlocks = blocks.filter((b) => b.type === BLOCK_IMG);
  for (const block of imgBlocks) {
    try {
      const parsed = parseTextureBlock(reader, block.dataOffset + BLOCK_PADDING, block.dataLength - BLOCK_PADDING);
      if (parsed && !result.has(parsed.name)) {
        result.set(parsed.name, parsed.texture);
      }
    } catch {
    }
  }
  return result;
}
function parseZoneFile(buffer, onProgress, supplementalTextures) {
  const reader = new DatReader(buffer);
  const blocks = parseBlockChain(reader);
  onProgress?.(`Block chain: ${blocks.length} blocks`);
  const textures = [];
  const prefabs = [];
  const instances = [];
  const imgBlocks = blocks.filter((b) => b.type === BLOCK_IMG);
  onProgress?.(`Parsing ${imgBlocks.length} textures...`);
  const textureNameMap = /* @__PURE__ */ new Map();
  const duplicateNames = [];
  for (const block of imgBlocks) {
    try {
      const result = parseTextureBlock(reader, block.dataOffset + BLOCK_PADDING, block.dataLength - BLOCK_PADDING);
      if (result) {
        if (textureNameMap.has(result.name)) {
          duplicateNames.push(`"${result.name}" (first=${textureNameMap.get(result.name)}, dup=${textures.length}, ${result.texture.width}\xD7${result.texture.height})`);
        } else {
          textureNameMap.set(result.name, textures.length);
          textures.push(result.texture);
        }
      }
    } catch {
    }
  }
  onProgress?.(`Textures: ${textures.length} parsed (${textureNameMap.size} named)`);
  console.log("[ZoneFile] textureNameMap entries:", Array.from(textureNameMap.keys()).sort());
  if (duplicateNames.length > 0) {
    console.warn(`[ZoneFile] ${duplicateNames.length} duplicate texture names (last wins):`, duplicateNames);
  }
  console.log("[ZoneFile] First textures:", textures.slice(0, 10).map((t, i) => {
    const r = t.rgba[0], g = t.rgba[1], b = t.rgba[2], a = t.rgba[3];
    return `[${i}] ${t.width}\xD7${t.height} px0=(${r},${g},${b},${a})`;
  }));
  if (supplementalTextures) {
    let added = 0;
    for (const [name, tex] of supplementalTextures) {
      if (!textureNameMap.has(name)) {
        textureNameMap.set(name, textures.length);
        textures.push(tex);
        added++;
      }
    }
    if (added > 0) {
      onProgress?.(`Supplemental textures: ${added} added from companion DATs`);
      console.log(`[ZoneFile] ${added} supplemental textures merged, total now ${textures.length}`);
    }
  }
  const mmbBlocks = blocks.filter((b) => b.type === BLOCK_MMB);
  onProgress?.(`Parsing ${mmbBlocks.length} MMB blocks...`);
  const mmbNameMap = /* @__PURE__ */ new Map();
  const skyObjectNames = /* @__PURE__ */ new Set(["sunsphere", "moonsphere"]);
  for (let i = 0; i < mmbBlocks.length; i++) {
    const block = mmbBlocks[i];
    const start = block.dataOffset + BLOCK_PADDING;
    const len = block.dataLength - BLOCK_PADDING;
    if (len <= 0) continue;
    try {
      const blockData = new Uint8Array(buffer, start, len);
      const decryptedData = decodeMmb(blockData);
      const name = readMmbName(decryptedData);
      if (skyObjectNames.has(name)) continue;
      const meshes = parseMmbBlock(decryptedData);
      for (const mesh of meshes) {
        if (!mesh.textureName) {
          mesh.materialIndex = -1;
          continue;
        }
        const texIdx = textureNameMap.get(mesh.textureName);
        if (texIdx !== void 0) {
          mesh.materialIndex = texIdx;
        } else {
          mesh.materialIndex = -1;
        }
      }
      if (meshes.length > 0) {
        const startIdx = prefabs.length;
        prefabs.push(...meshes);
        let arr = mmbNameMap.get(name);
        if (!arr) {
          arr = [];
          mmbNameMap.set(name, arr);
        }
        arr.push({ startIdx, count: meshes.length });
      }
    } catch {
    }
  }
  const texUsage = /* @__PURE__ */ new Map();
  for (const p of prefabs) {
    if (p.materialIndex >= 0) texUsage.set(p.materialIndex, (texUsage.get(p.materialIndex) || 0) + 1);
  }
  let fallbackTexIdx = -1;
  let fallbackMax = 0;
  for (const [idx, count] of texUsage) {
    if (count > fallbackMax) {
      fallbackMax = count;
      fallbackTexIdx = idx;
    }
  }
  if (fallbackTexIdx >= 0) {
    let count = 0;
    for (const p of prefabs) {
      if (p.materialIndex === -1) {
        p.materialIndex = fallbackTexIdx;
        count++;
      }
    }
    if (count > 0) console.log(`[ZoneFile] ${count} untextured meshes \u2192 fallback texture[${fallbackTexIdx}]`);
  }
  onProgress?.(`MMB: ${prefabs.length} meshes from ${mmbBlocks.length} blocks, ${mmbNameMap.size} unique names`);
  const mzbBlocks = blocks.filter((b) => b.type === BLOCK_MZB);
  onProgress?.(`Parsing ${mzbBlocks.length} MZB blocks...`);
  let mzbTotal = 0;
  let mzbMatched = 0;
  for (const block of mzbBlocks) {
    const start = block.dataOffset + BLOCK_PADDING;
    const len = block.dataLength - BLOCK_PADDING;
    if (len <= 0) continue;
    try {
      const blockData = new Uint8Array(buffer, start, len);
      const decryptedData = decodeMzb(blockData);
      const rawInstances = parseMzbBlock(decryptedData);
      mzbTotal += rawInstances.length;
      for (const inst of rawInstances) {
        const mappings = mmbNameMap.get(inst.name);
        if (!mappings) continue;
        mzbMatched++;
        for (const mapping of mappings) {
          for (let m = 0; m < mapping.count; m++) {
            instances.push({
              meshIndex: mapping.startIdx + m,
              transform: inst.transform
            });
          }
        }
      }
    } catch (err) {
      onProgress?.(`Warning: MZB parse failed \u2014 ${err}`);
    }
  }
  const unmatchedCount = { total: mzbTotal, matched: mzbMatched };
  onProgress?.(`Instances: ${instances.length} (${unmatchedCount.matched}/${unmatchedCount.total} MZB entries matched MMB names)`);
  onProgress?.(`Result: ${prefabs.length} prefabs, ${instances.length} instances, ${textures.length} textures`);
  return { prefabs, instances, textures };
}
export {
  parseTexturesFromDat,
  parseZoneFile
};
//# sourceMappingURL=ZoneFile.js.map
