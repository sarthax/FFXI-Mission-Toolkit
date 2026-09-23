function unpackRGB565(color, out, offset) {
  const r = (color >> 11 & 31) << 3;
  const g = (color >> 5 & 63) << 2;
  const b = (color & 31) << 3;
  out[offset + 0] = r | r >> 5;
  out[offset + 1] = g | g >> 6;
  out[offset + 2] = b | b >> 5;
  out[offset + 3] = 255;
}
function decompressDXT1(data, width, height) {
  const rgba = new Uint8Array(width * height * 4);
  const blocksX = Math.max(1, Math.ceil(width / 4));
  const blocksY = Math.max(1, Math.ceil(height / 4));
  let src = 0;
  for (let by = 0; by < blocksY; by++) {
    for (let bx = 0; bx < blocksX; bx++) {
      const c0 = data[src] | data[src + 1] << 8;
      const c1 = data[src + 2] | data[src + 3] << 8;
      const idx = data[src + 4] | data[src + 5] << 8 | data[src + 6] << 16 | data[src + 7] << 24;
      src += 8;
      const pal = new Uint8Array(16);
      unpackRGB565(c0, pal, 0);
      unpackRGB565(c1, pal, 4);
      if (c0 > c1) {
        for (let i = 0; i < 3; i++) {
          pal[8 + i] = (2 * pal[i] + pal[4 + i]) / 3 | 0;
          pal[12 + i] = (pal[i] + 2 * pal[4 + i]) / 3 | 0;
        }
        pal[11] = 255;
        pal[15] = 255;
      } else {
        for (let i = 0; i < 3; i++) pal[8 + i] = (pal[i] + pal[4 + i]) / 2 | 0;
        pal[11] = 255;
        pal[15] = 255;
      }
      for (let py = 0; py < 4; py++) {
        for (let px = 0; px < 4; px++) {
          const x = bx * 4 + px, y = by * 4 + py;
          if (x >= width || y >= height) continue;
          const ci = idx >>> (py * 4 + px) * 2 & 3;
          const d = (y * width + x) * 4;
          rgba[d] = pal[ci * 4];
          rgba[d + 1] = pal[ci * 4 + 1];
          rgba[d + 2] = pal[ci * 4 + 2];
          rgba[d + 3] = pal[ci * 4 + 3];
        }
      }
    }
  }
  return rgba;
}
function decompressDXT3(data, width, height) {
  const rgba = new Uint8Array(width * height * 4);
  const blocksX = Math.max(1, Math.ceil(width / 4));
  const blocksY = Math.max(1, Math.ceil(height / 4));
  let src = 0;
  for (let by = 0; by < blocksY; by++) {
    for (let bx = 0; bx < blocksX; bx++) {
      const alpha = data.subarray(src, src + 8);
      src += 8;
      const c0 = data[src] | data[src + 1] << 8;
      const c1 = data[src + 2] | data[src + 3] << 8;
      const idx = data[src + 4] | data[src + 5] << 8 | data[src + 6] << 16 | data[src + 7] << 24;
      src += 8;
      const p0 = new Uint8Array(4), p1 = new Uint8Array(4);
      unpackRGB565(c0, p0, 0);
      unpackRGB565(c1, p1, 0);
      const pal = [
        [p0[0], p0[1], p0[2]],
        [p1[0], p1[1], p1[2]],
        [(2 * p0[0] + p1[0]) / 3 | 0, (2 * p0[1] + p1[1]) / 3 | 0, (2 * p0[2] + p1[2]) / 3 | 0],
        [(p0[0] + 2 * p1[0]) / 3 | 0, (p0[1] + 2 * p1[1]) / 3 | 0, (p0[2] + 2 * p1[2]) / 3 | 0]
      ];
      for (let py = 0; py < 4; py++) {
        for (let px = 0; px < 4; px++) {
          const x = bx * 4 + px, y = by * 4 + py;
          if (x >= width || y >= height) continue;
          const pi = py * 4 + px;
          const ci = idx >>> pi * 2 & 3;
          const d = (y * width + x) * 4;
          const a4 = pi % 2 === 0 ? alpha[pi >> 1] & 15 : alpha[pi >> 1] >> 4 & 15;
          rgba[d] = pal[ci][0];
          rgba[d + 1] = pal[ci][1];
          rgba[d + 2] = pal[ci][2];
          rgba[d + 3] = a4 << 4 | a4;
        }
      }
    }
  }
  return rgba;
}
const B1_HEADER_SIZE = 64;
const B1_PALETTE_ENTRIES = 256;
const B1_PALETTE_SIZE = B1_PALETTE_ENTRIES * 4;
function parseTextureBlock(reader, dataOffset, dataLength) {
  reader.seek(dataOffset);
  const flg = reader.readUint8();
  if (flg !== 161 && flg !== 129 && flg !== 177) {
    console.warn(`[TextureParser] Unsupported texture format 0x${flg.toString(16).toUpperCase()} at offset ${dataOffset}`);
    return null;
  }
  const id = reader.readString(16);
  reader.skip(4);
  const width = reader.readInt32();
  const height = reader.readInt32();
  if (width <= 0 || width > 4096 || height <= 0 || height > 4096) return null;
  if (flg === 177) {
    return parseB1Texture(reader, dataOffset, dataLength, id.trim(), width, height);
  }
  reader.skip(24);
  reader.skip(4);
  if (flg === 161) {
    const ddsType = reader.readString(4);
    const ddsSize = reader.readUint32();
    reader.skip(4);
    const pixelData = reader.readBytes(ddsSize);
    let rgba;
    if (ddsType === "3TXD") {
      rgba = decompressDXT3(pixelData, width, height);
    } else if (ddsType === "1TXD") {
      rgba = decompressDXT1(pixelData, width, height);
    } else {
      return null;
    }
    return {
      name: id.trim(),
      texture: { width, height, rgba }
    };
  }
  if (flg === 129) {
    const ddsType = reader.readString(4);
    const ddsSize = reader.readUint32();
    reader.skip(4);
    const pixelData = reader.readBytes(ddsSize);
    let rgba;
    if (ddsType === "3TXD") {
      rgba = decompressDXT3(pixelData, width, height);
    } else if (ddsType === "1TXD") {
      rgba = decompressDXT1(pixelData, width, height);
    } else {
      return null;
    }
    return {
      name: id.trim(),
      texture: { width, height, rgba }
    };
  }
  return null;
}
function parseB1Texture(reader, dataOffset, dataLength, name, width, height) {
  const paletteOffset = dataOffset + B1_HEADER_SIZE;
  const pixelOffset = paletteOffset + B1_PALETTE_SIZE;
  const pixelCount = width * height;
  if (pixelOffset + pixelCount > dataOffset + dataLength) {
    return parseB1AsDXT(reader, dataOffset, dataLength, name, width, height);
  }
  reader.seek(paletteOffset);
  const palette = reader.readBytes(B1_PALETTE_SIZE);
  reader.seek(pixelOffset);
  const indices = reader.readBytes(pixelCount);
  const rgba = new Uint8Array(pixelCount * 4);
  for (let i = 0; i < pixelCount; i++) {
    const idx = indices[i];
    const pOff = idx * 4;
    const d = i * 4;
    rgba[d + 0] = palette[pOff + 2];
    rgba[d + 1] = palette[pOff + 1];
    rgba[d + 2] = palette[pOff + 0];
    const a = palette[pOff + 3];
    rgba[d + 3] = a > 0 ? 255 : 0;
  }
  return { name, texture: { width, height, rgba } };
}
function parseB1AsDXT(reader, dataOffset, dataLength, name, width, height) {
  const blocksX = Math.max(1, Math.ceil(width / 4));
  const blocksY = Math.max(1, Math.ceil(height / 4));
  const expectedDXT3 = blocksX * blocksY * 16;
  const expectedDXT1 = blocksX * blocksY * 8;
  if (dataLength >= expectedDXT3 + B1_HEADER_SIZE) {
    const pixelOffset = dataOffset + dataLength - expectedDXT3;
    reader.seek(pixelOffset);
    const pixelData = reader.readBytes(expectedDXT3);
    return { name, texture: { width, height, rgba: decompressDXT3(pixelData, width, height) } };
  }
  if (dataLength >= expectedDXT1 + B1_HEADER_SIZE) {
    const pixelOffset = dataOffset + dataLength - expectedDXT1;
    reader.seek(pixelOffset);
    const pixelData = reader.readBytes(expectedDXT1);
    return { name, texture: { width, height, rgba: decompressDXT1(pixelData, width, height) } };
  }
  console.warn(`[TextureParser] 0xB1 texture "${name}" (${width}\xD7${height}) doesn't fit indexed or DXT layout`);
  return null;
}
function parseTextures(_reader) {
  return [];
}
export {
  decompressDXT1,
  decompressDXT3,
  parseTextureBlock,
  parseTextures,
  unpackRGB565
};
//# sourceMappingURL=TextureParser.js.map
