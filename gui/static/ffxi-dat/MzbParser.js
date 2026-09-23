const SMZB_HEADER_SIZE = 32;
const SMZB_BLOCK100_SIZE = 100;
const textDecoder = new TextDecoder("utf-8");
function parseMzbBlock(data) {
  if (data.length < SMZB_HEADER_SIZE + SMZB_BLOCK100_SIZE) return [];
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const totalRecord100 = view.getUint32(4, true) & 16777215;
  if (totalRecord100 === 0 || totalRecord100 > 2e4) {
    if (totalRecord100 > 2e4) console.warn(`MZB: totalRecord100 ${totalRecord100} too large`);
    return [];
  }
  const instances = [];
  const recordsStart = SMZB_HEADER_SIZE;
  for (let i = 0; i < totalRecord100; i++) {
    const offset = recordsStart + i * SMZB_BLOCK100_SIZE;
    if (offset + SMZB_BLOCK100_SIZE > data.length) break;
    const idBytes = data.subarray(offset, offset + 16);
    let end = idBytes.indexOf(0);
    if (end === -1) end = 16;
    const name = textDecoder.decode(idBytes.subarray(0, end)).trim();
    const fTransX = view.getFloat32(offset + 16, true);
    const fTransY = view.getFloat32(offset + 20, true);
    const fTransZ = view.getFloat32(offset + 24, true);
    const fRotX = view.getFloat32(offset + 28, true);
    const fRotY = view.getFloat32(offset + 32, true);
    const fRotZ = view.getFloat32(offset + 36, true);
    const fScaleX = view.getFloat32(offset + 40, true);
    const fScaleY = view.getFloat32(offset + 44, true);
    const fScaleZ = view.getFloat32(offset + 48, true);
    const cx = Math.cos(fRotX), sx = Math.sin(fRotX);
    const cy = Math.cos(fRotY), sy = Math.sin(fRotY);
    const cz = Math.cos(fRotZ), sz = Math.sin(fRotZ);
    const r00 = cz * cy, r01 = cz * sy * sx - sz * cx, r02 = cz * sy * cx + sz * sx;
    const r10 = sz * cy, r11 = sz * sy * sx + cz * cx, r12 = sz * sy * cx - cz * sx;
    const r20 = -sy, r21 = cy * sx, r22 = cy * cx;
    const transform = [
      r00 * fScaleX,
      r10 * fScaleX,
      r20 * fScaleX,
      0,
      r01 * fScaleY,
      r11 * fScaleY,
      r21 * fScaleY,
      0,
      r02 * fScaleZ,
      r12 * fScaleZ,
      r22 * fScaleZ,
      0,
      fTransX,
      fTransY,
      fTransZ,
      1
    ];
    instances.push({ name, transform });
  }
  return instances;
}
export {
  parseMzbBlock
};
//# sourceMappingURL=MzbParser.js.map
