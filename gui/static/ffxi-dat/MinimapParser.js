import { DatReader } from "./DatReader.js";
import { decompressDXT1, decompressDXT3 } from "./TextureParser.js";
const DATHEAD_SIZE = 8;
const BLOCK_PADDING = 8;
function parseMinimapDat(buffer) {
  const reader = new DatReader(buffer);
  let offset = 0;
  while (offset < reader.length - DATHEAD_SIZE) {
    reader.seek(offset);
    reader.skip(4);
    const packed = reader.readUint32();
    const type = packed & 127;
    const nextUnits = packed >> 7 & 524287;
    const blockSize = nextUnits * 16;
    if (nextUnits === 0) break;
    if (type === 32) {
      const dataOffset = offset + DATHEAD_SIZE + BLOCK_PADDING;
      const dataLength = blockSize - DATHEAD_SIZE - BLOCK_PADDING;
      if (dataLength > 0) {
        const texture = parseMinimapTextureBlock(reader, dataOffset, dataLength);
        if (texture) return texture;
      }
    }
    offset += blockSize;
  }
  return null;
}
const B1_HEADER_SIZE = 64;
const B1_PALETTE_ENTRIES = 256;
const B1_PALETTE_SIZE = B1_PALETTE_ENTRIES * 4;
function parseMinimapTextureBlock(reader, dataOffset, dataLength) {
  reader.seek(dataOffset);
  const flg = reader.readUint8();
  if (flg === 161 || flg === 129) {
    return parseA1Style(reader, dataOffset);
  }
  if (flg !== 177) return null;
  reader.seek(dataOffset + 21);
  const width = reader.readInt32();
  const height = reader.readInt32();
  if (width <= 0 || width > 2048 || height <= 0 || height > 2048) return null;
  const paletteOffset = dataOffset + B1_HEADER_SIZE;
  const pixelOffset = paletteOffset + B1_PALETTE_SIZE;
  const pixelCount = width * height;
  if (pixelOffset + pixelCount > dataOffset + dataLength) {
    return parseB1AsDXT(reader, dataOffset, dataLength, width, height);
  }
  reader.seek(paletteOffset);
  const palette = reader.readBytes(B1_PALETTE_SIZE);
  reader.seek(pixelOffset);
  const indices = reader.readBytes(pixelCount);
  const rgba = new Uint8Array(pixelCount * 4);
  for (let y = 0; y < height; y++) {
    const srcRow = y * width;
    const dstRow = (height - 1 - y) * width;
    for (let x = 0; x < width; x++) {
      const idx = indices[srcRow + x];
      const pOff = idx * 4;
      const d = (dstRow + x) * 4;
      rgba[d + 0] = palette[pOff + 2];
      rgba[d + 1] = palette[pOff + 1];
      rgba[d + 2] = palette[pOff + 0];
      const a = palette[pOff + 3];
      rgba[d + 3] = a > 0 ? 255 : 0;
    }
  }
  return { width, height, rgba };
}
function parseB1AsDXT(reader, dataOffset, dataLength, width, height) {
  const blocksX = Math.max(1, Math.ceil(width / 4));
  const blocksY = Math.max(1, Math.ceil(height / 4));
  const expectedDXT3 = blocksX * blocksY * 16;
  const expectedDXT1 = blocksX * blocksY * 8;
  if (dataLength >= expectedDXT3 + B1_HEADER_SIZE) {
    const pixelOffset = dataOffset + dataLength - expectedDXT3;
    reader.seek(pixelOffset);
    const pixelData = reader.readBytes(expectedDXT3);
    return { width, height, rgba: decompressDXT3(pixelData, width, height) };
  }
  if (dataLength >= expectedDXT1 + B1_HEADER_SIZE) {
    const pixelOffset = dataOffset + dataLength - expectedDXT1;
    reader.seek(pixelOffset);
    const pixelData = reader.readBytes(expectedDXT1);
    return { width, height, rgba: decompressDXT1(pixelData, width, height) };
  }
  return null;
}
function parseA1Style(reader, dataOffset) {
  reader.seek(dataOffset + 1);
  reader.skip(16);
  reader.skip(4);
  const width = reader.readInt32();
  const height = reader.readInt32();
  reader.skip(24);
  reader.skip(4);
  if (width <= 0 || width > 2048 || height <= 0 || height > 2048) return null;
  const ddsType = reader.readString(4);
  const ddsSize = reader.readUint32();
  reader.skip(4);
  if (ddsSize === 0) return null;
  const pixelData = reader.readBytes(ddsSize);
  let rgba;
  if (ddsType === "3TXD") {
    rgba = decompressDXT3(pixelData, width, height);
  } else if (ddsType === "1TXD") {
    rgba = decompressDXT1(pixelData, width, height);
  } else {
    return null;
  }
  return { width, height, rgba };
}
export {
  parseMinimapDat
};
//# sourceMappingURL=MinimapParser.js.map
