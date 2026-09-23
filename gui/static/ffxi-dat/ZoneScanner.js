import { DatReader } from "./DatReader.js";
const DATHEAD_SIZE = 8;
const BLOCK_TYPE_MZB = 28;
const BLOCK_TYPE_MMB = 46;
const MAX_BLOCKS_TO_CHECK = 20;
const MIN_FILE_SIZE = 1024;
async function scanForZoneDats(readFile, resolver, onProgress, signal) {
  const results = [];
  const fileIds = [];
  for (let id = 0; id < 1e5; id++) {
    const path = resolver.resolveFileId(id);
    if (path) fileIds.push({ id, path });
  }
  const total = fileIds.length;
  onProgress?.({ current: 0, total, found: 0, message: `Scanning ${total} files...` });
  for (let i = 0; i < fileIds.length; i++) {
    if (signal?.aborted) break;
    const { path } = fileIds[i];
    if (i % 100 === 0) {
      onProgress?.({ current: i, total, found: results.length, message: `Checking ${path}...` });
    }
    try {
      const buffer = await readFile(path);
      if (!buffer || buffer.byteLength < MIN_FILE_SIZE) continue;
      if (hasZoneBlockTypes(buffer)) results.push({ modelPath: path });
    } catch {
    }
  }
  onProgress?.({ current: total, total, found: results.length, message: `Scan complete. Found ${results.length} zone DATs.` });
  return results;
}
function hasZoneBlockTypes(buffer) {
  const reader = new DatReader(buffer);
  let hasMzb = false, hasMmb = false, offset = 0;
  for (let i = 0; i < MAX_BLOCKS_TO_CHECK; i++) {
    if (offset + DATHEAD_SIZE > reader.length) break;
    reader.seek(offset);
    reader.skip(4);
    const packed = reader.readUint32();
    const type = packed & 127;
    const nextUnits = packed >> 7 & 524287;
    if (type === BLOCK_TYPE_MZB) hasMzb = true;
    if (type === BLOCK_TYPE_MMB) hasMmb = true;
    if (hasMzb && hasMmb) return true;
    if (nextUnits === 0) break;
    offset += nextUnits * 16;
  }
  return false;
}
export {
  scanForZoneDats
};
//# sourceMappingURL=ZoneScanner.js.map
