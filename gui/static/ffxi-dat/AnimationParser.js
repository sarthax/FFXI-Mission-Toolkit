import { DatReader } from "./DatReader.js";
const BLOCK_ANIM = 43;
const DATHEAD_SIZE = 8;
const BLOCK_PADDING = 8;
const DAT2B_HEADER_SIZE = 10;
const DAT2B_BONE_SIZE = 84;
function parseAnimationDat(buffer, debugPath) {
  const reader = new DatReader(buffer);
  const animations = [];
  let offset = 0;
  while (offset < reader.length - DATHEAD_SIZE) {
    reader.seek(offset);
    reader.skip(4);
    const packed = reader.readUint32();
    const type = packed & 127;
    const nextUnits = packed >> 7 & 524287;
    const blockSize = nextUnits * 16;
    if (type === BLOCK_ANIM) {
      try {
        const dataStart = offset + DATHEAD_SIZE + BLOCK_PADDING;
        const anim = parseAnimBlock(reader, dataStart, debugPath);
        if (anim) animations.push(anim);
      } catch (err) {
        if (debugPath) console.warn(`[AnimParser] parseAnimBlock error:`, err);
      }
    }
    if (nextUnits === 0) break;
    offset += blockSize;
    if (offset > reader.length) break;
  }
  return animations;
}
function parseAnimBlock(reader, dataStart, debugPath) {
  reader.seek(dataStart);
  reader.skip(2);
  const element = reader.readUint16();
  const frameCount = reader.readUint16();
  const speed = reader.readFloat32();
  if (element === 0 || frameCount === 0) return null;
  if (element > 500) return null;
  const poolBase = dataStart + DAT2B_HEADER_SIZE;
  const shouldLog = debugPath && typeof window !== "undefined" && !window.__animParsed;
  if (shouldLog) {
    ;
    window.__animParsed = true;
    console.log(`[AnimParser] header: element=${element} frame=${frameCount} speed=${speed} poolBase=${poolBase}`);
  }
  const bones = [];
  let loggedBone = false;
  for (let i = 0; i < element; i++) {
    const boneOffset = dataStart + DAT2B_HEADER_SIZE + i * DAT2B_BONE_SIZE;
    reader.seek(boneOffset);
    const boneIndex = reader.readInt32();
    const idx_qtx = reader.readInt32();
    const idx_qty = reader.readInt32();
    const idx_qtz = reader.readInt32();
    const idx_qtw = reader.readInt32();
    const qtx = reader.readFloat32();
    const qty = reader.readFloat32();
    const qtz = reader.readFloat32();
    const qtw = reader.readFloat32();
    const idx_tx = reader.readInt32();
    const idx_ty = reader.readInt32();
    const idx_tz = reader.readInt32();
    const tx = reader.readFloat32();
    const ty = reader.readFloat32();
    const tz = reader.readFloat32();
    const idx_sx = reader.readInt32();
    const idx_sy = reader.readInt32();
    const idx_sz = reader.readInt32();
    const sx = reader.readFloat32();
    const sy = reader.readFloat32();
    const sz = reader.readFloat32();
    if (idx_qtx & 2147483648) continue;
    if (shouldLog && !loggedBone) {
      loggedBone = true;
      const testBytePos = poolBase + idx_qtx * 4;
      reader.seek(testBytePos);
      const testFloat = reader.readFloat32();
      console.log(`[AnimParser] bone[${i}] idx=${boneIndex} idx_qtx=${idx_qtx} bytePos=${testBytePos} pool[idx_qtx]=${testFloat}`);
      console.log(`  defaults: rot=[${qtx},${qty},${qtz},${qtw}] trans=[${tx},${ty},${tz}]`);
    }
    const rotKf = readRotationKeyframes(reader, poolBase, idx_qtx, idx_qty, idx_qtz, idx_qtw, frameCount, qtx, qty, qtz, qtw);
    const transKf = readTranslationKeyframes(reader, poolBase, idx_tx, idx_ty, idx_tz, frameCount, tx, ty, tz);
    const scaleKf = readScaleKeyframes(reader, poolBase, idx_sx, idx_sy, idx_sz, frameCount, sx, sy, sz);
    bones.push({
      boneIndex,
      rotationKeyframes: rotKf,
      rotationDefault: [qtx, qty, qtz, qtw],
      translationKeyframes: transKf,
      translationDefault: [tx, ty, tz],
      scaleKeyframes: scaleKf,
      scaleDefault: [sx, sy, sz]
    });
  }
  return { frameCount, speed, bones };
}
function readPoolFloat(reader, poolBase, idx) {
  reader.seek(poolBase + idx * 4);
  return reader.readFloat32();
}
function readRotationKeyframes(reader, poolBase, idxX, idxY, idxZ, idxW, frameCount, defX, defY, defZ, defW) {
  if (idxX === 0 && idxY === 0 && idxZ === 0 && idxW === 0) return null;
  const kf = new Float32Array(frameCount * 4);
  for (let f = 0; f < frameCount; f++) {
    kf[f * 4 + 0] = idxX > 0 ? readPoolFloat(reader, poolBase, idxX + f) : defX;
    kf[f * 4 + 1] = idxY > 0 ? readPoolFloat(reader, poolBase, idxY + f) : defY;
    kf[f * 4 + 2] = idxZ > 0 ? readPoolFloat(reader, poolBase, idxZ + f) : defZ;
    kf[f * 4 + 3] = idxW > 0 ? readPoolFloat(reader, poolBase, idxW + f) : defW;
  }
  return kf;
}
function readTranslationKeyframes(reader, poolBase, idxX, idxY, idxZ, frameCount, defX, defY, defZ) {
  if (idxX === 0 && idxY === 0 && idxZ === 0) return null;
  const kf = new Float32Array(frameCount * 3);
  for (let f = 0; f < frameCount; f++) {
    kf[f * 3 + 0] = idxX > 0 ? readPoolFloat(reader, poolBase, idxX + f) : defX;
    kf[f * 3 + 1] = idxY > 0 ? readPoolFloat(reader, poolBase, idxY + f) : defY;
    kf[f * 3 + 2] = idxZ > 0 ? readPoolFloat(reader, poolBase, idxZ + f) : defZ;
  }
  return kf;
}
function readScaleKeyframes(reader, poolBase, idxX, idxY, idxZ, frameCount, defX, defY, defZ) {
  if (idxX === 0 && idxY === 0 && idxZ === 0) return null;
  const kf = new Float32Array(frameCount * 3);
  for (let f = 0; f < frameCount; f++) {
    kf[f * 3 + 0] = idxX > 0 ? readPoolFloat(reader, poolBase, idxX + f) : defX;
    kf[f * 3 + 1] = idxY > 0 ? readPoolFloat(reader, poolBase, idxY + f) : defY;
    kf[f * 3 + 2] = idxZ > 0 ? readPoolFloat(reader, poolBase, idxZ + f) : defZ;
  }
  return kf;
}
export {
  parseAnimationDat
};
//# sourceMappingURL=AnimationParser.js.map
