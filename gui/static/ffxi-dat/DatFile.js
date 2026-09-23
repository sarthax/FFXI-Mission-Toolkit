import { DatReader } from "./DatReader.js";
import { parseTextureBlock } from "./TextureParser.js";
import { parseVertexBlock } from "./MeshParser.js";
import { parseSkeleton } from "./SkeletonParser.js";
import { parseAnimationDat } from "./AnimationParser.js";
const BLOCK_IMG = 32;
const BLOCK_BONE = 41;
const BLOCK_VERTEX = 42;
const BLOCK_ANIM = 43;
const DATHEAD_SIZE = 8;
const BLOCK_PADDING = 8;
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
    if (blocks.length > 500) break;
  }
  return blocks;
}
function parseDatFile(buffer, skelMatrices) {
  const reader = new DatReader(buffer);
  const blocks = parseBlockChain(reader);
  const textures = [];
  const meshes = [];
  const textureMap = /* @__PURE__ */ new Map();
  let embeddedSkeleton = null;
  for (const block of blocks) {
    if (block.type === BLOCK_IMG) {
      try {
        const start = block.dataOffset + BLOCK_PADDING;
        const len = block.dataLength - BLOCK_PADDING;
        const result = parseTextureBlock(reader, start, len);
        if (result) {
          textureMap.set(result.name, textures.length);
          textures.push(result.texture);
        }
      } catch {
      }
    }
    if (block.type === BLOCK_BONE && !embeddedSkeleton) {
      try {
        embeddedSkeleton = parseSkeleton(reader);
      } catch {
      }
    }
  }
  const matrices = embeddedSkeleton?.matrices ?? skelMatrices ?? null;
  for (const block of blocks) {
    if (block.type === BLOCK_VERTEX) {
      try {
        const start = block.dataOffset + BLOCK_PADDING;
        const len = block.dataLength - BLOCK_PADDING;
        meshes.push(...parseVertexBlock(reader, start, len, textureMap, matrices));
      } catch {
      }
    }
  }
  let animations = [];
  const hasAnimBlocks = blocks.some((b) => b.type === BLOCK_ANIM);
  if (hasAnimBlocks) {
    try {
      animations = parseAnimationDat(buffer);
    } catch {
    }
  }
  return { meshes, textures, skeleton: embeddedSkeleton, animations };
}
function parseSkeletonDat(buffer) {
  const reader = new DatReader(buffer);
  return parseSkeleton(reader);
}
export {
  BLOCK_ANIM,
  parseDatFile,
  parseSkeletonDat
};
//# sourceMappingURL=DatFile.js.map
