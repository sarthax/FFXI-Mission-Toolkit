import { DatReader } from "./DatReader.js";
import { triangleStripToList } from "./MeshParser.js";
function parseMmbBlock(data) {
  const reader = new DatReader(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength));
  const meshes = [];
  if (data.length < 60) return meshes;
  const id0 = reader.readUint8();
  const id1 = reader.readUint8();
  const id2 = reader.readUint8();
  const packed = reader.readUint32();
  reader.skip(9);
  const isMmbType = id0 === 77 && id1 === 77 && id2 === 66;
  const d3 = data[4];
  const vertexStride = d3 === 2 ? 48 : 36;
  reader.skip(16);
  const pieces = reader.readInt32();
  reader.skip(24);
  const offsetBlockHeader = reader.readUint32();
  if (pieces <= 0 || pieces > 200) return meshes;
  const currentPos = reader.position;
  const offsets = [];
  if (offsetBlockHeader === 0) {
    if (pieces !== 0) {
      for (let i = 0; i < 8; i++) {
        if (reader.remaining < 4) break;
        const off = reader.readUint32();
        if (off !== 0) offsets.push(off);
      }
    } else {
      offsets.push(currentPos);
    }
  } else {
    offsets.push(offsetBlockHeader);
    const maxRange = offsetBlockHeader - currentPos;
    if (maxRange > 0) {
      for (let i = 0; i < maxRange; i += 4) {
        if (reader.remaining < 4) break;
        const off = reader.readUint32();
        if (off !== 0) offsets.push(off);
      }
    }
  }
  let offsetIdx = 0;
  for (let piece = 0; piece < pieces; piece++) {
    if (offsetIdx < offsets.length) {
      reader.seek(offsets[offsetIdx++]);
    }
    if (reader.remaining < 32) break;
    const numModel = reader.readInt32();
    reader.skip(28);
    if (numModel <= 0 || numModel > 50) break;
    for (let k = 0; k < numModel; k++) {
      if (reader.remaining < 20) break;
      const textureName = reader.readString(16).trim();
      const vertexCount = reader.readUint16();
      const blending = reader.readUint16();
      if (vertexCount === 0 || reader.remaining < vertexCount * vertexStride + 4) break;
      const vertices = [];
      const normals = [];
      const colors = [];
      const uvs = [];
      for (let v = 0; v < vertexCount; v++) {
        vertices.push(reader.readFloat32(), reader.readFloat32(), reader.readFloat32());
        if (vertexStride === 48) {
          reader.skip(12);
        }
        normals.push(reader.readFloat32(), reader.readFloat32(), reader.readFloat32());
        const colorVal = reader.readUint32();
        const b = (colorVal & 255) / 255;
        const g = (colorVal >> 8 & 255) / 255;
        const r = (colorVal >> 16 & 255) / 255;
        const a = (colorVal >> 24 & 255) / 255;
        colors.push(r, g, b, a);
        uvs.push(reader.readFloat32(), reader.readFloat32());
      }
      if (reader.remaining < 4) break;
      const numIndices = reader.readUint32() & 65535;
      if (numIndices === 0 || reader.remaining < numIndices * 2) break;
      const rawIndices = [];
      for (let j = 0; j < numIndices; j++) {
        rawIndices.push(reader.readUint16());
      }
      if (numIndices % 2 !== 0) reader.skip(2);
      const isTriList = isMmbType && (packed & 127) === 0 || !isMmbType && d3 === 2;
      let triIndices;
      if (isTriList) {
        triIndices = rawIndices;
      } else {
        triIndices = triangleStripToList(rawIndices);
      }
      if (triIndices.length === 0) continue;
      meshes.push({
        vertices,
        normals,
        colors,
        uvs,
        indices: triIndices,
        materialIndex: 0,
        textureName,
        blending
      });
    }
  }
  return meshes;
}
export {
  parseMmbBlock
};
//# sourceMappingURL=MmbParser.js.map
