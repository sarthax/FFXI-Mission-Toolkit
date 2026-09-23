var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
class FileTableResolver {
  constructor(vtable, ftable) {
    __publicField(this, "vtable");
    __publicField(this, "ftable");
    this.vtable = vtable;
    this.ftable = ftable;
  }
  /**
   * Load and parse VTABLE.DAT and FTABLE.DAT from an FFXI directory handle.
   */
  static async fromDirectory(readFile) {
    const [vtableBuffer, ftableBuffer] = await Promise.all([
      readFile("VTABLE.DAT"),
      readFile("FTABLE.DAT")
    ]);
    const vtable = new Uint8Array(vtableBuffer);
    const ftable = new Uint16Array(ftableBuffer);
    return new FileTableResolver(vtable, ftable);
  }
  /**
   * Resolve a file ID to a ROM-relative path.
   * Returns null if the file ID is not present.
   *
   * Example: resolveFileId(1234) → "ROM/28/7.dat"
   */
  resolveFileId(fileId) {
    if (fileId < 0 || fileId >= this.vtable.length) return null;
    const romNum = this.vtable[fileId];
    if (romNum === 0) return null;
    const ftableValue = this.ftable[fileId];
    const folder = ftableValue >> 7;
    const file = ftableValue & 127;
    const romDir = romNum === 1 ? "ROM" : `ROM${romNum}`;
    return `${romDir}/${folder}/${file}.dat`;
  }
  get fileCount() {
    return this.vtable.length;
  }
}
let cachedPaths = null;
async function loadModelDatPaths() {
  if (cachedPaths) return cachedPaths;
  const res = await fetch("/data/model-dat-paths.json");
  cachedPaths = await res.json();
  return cachedPaths;
}
async function modelToPath(modelId, raceId, slotId) {
  const paths = await loadModelDatPaths();
  const key = `${raceId}:${slotId}`;
  return paths[key]?.[String(modelId)] ?? null;
}
async function resolveModelPaths(slots) {
  const paths = await loadModelDatPaths();
  const result = /* @__PURE__ */ new Map();
  for (const { modelId, raceId, slotId } of slots) {
    const key = `${raceId}:${slotId}`;
    const romPath = paths[key]?.[String(modelId)];
    if (romPath) {
      result.set(key, romPath);
    }
  }
  return result;
}
export {
  FileTableResolver,
  modelToPath,
  resolveModelPaths
};
//# sourceMappingURL=FileTableResolver.js.map
