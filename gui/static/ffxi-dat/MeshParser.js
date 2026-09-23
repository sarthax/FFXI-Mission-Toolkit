import { mat4TransformPoint } from "./SkeletonParser.js";
function applyMirrorFlag(m, flg) {
  const result = [...m];
  if (flg === 1) {
    result[0] = -m[0];
    result[1] = -m[1];
    result[2] = -m[2];
    result[3] = -m[3];
  } else if (flg === 2) {
    result[4] = -m[4];
    result[5] = -m[5];
    result[6] = -m[6];
    result[7] = -m[7];
  } else if (flg === 3) {
    result[8] = -m[8];
    result[9] = -m[9];
    result[10] = -m[10];
    result[11] = -m[11];
  }
  return result;
}
function triangleStripToList(stripIndices) {
  const triangles = [];
  for (let i = 0; i < stripIndices.length - 2; i++) {
    const a = stripIndices[i], b = stripIndices[i + 1], c = stripIndices[i + 2];
    if (a === b || b === c || a === c) continue;
    if (i % 2 === 0) triangles.push(a, b, c);
    else triangles.push(a, c, b);
  }
  return triangles;
}
function readDat2AHeader(reader) {
  return {
    ver: reader.readUint8(),
    nazo: reader.readUint8(),
    type: reader.readUint16(),
    flip: reader.readUint16(),
    offsetPoly: reader.readUint32(),
    polySuu: reader.readUint16(),
    offsetBoneTbl: reader.readUint32(),
    boneTblSuu: reader.readUint16(),
    offsetWeight: reader.readUint32(),
    weightSuu: reader.readUint16(),
    offsetBone: reader.readUint32(),
    boneSuu: reader.readUint16(),
    offsetVertex: reader.readUint32(),
    vertexSuu: reader.readUint16(),
    offsetPolyLoad: reader.readUint32(),
    polyLoadSuu: reader.readUint16()
  };
}
function parsePolygonCommands(reader, headerOffset, offsetPoly, polySuu) {
  const faces = [];
  let textureName = null;
  let pos = headerOffset + offsetPoly * 2;
  const endPos = headerOffset + (offsetPoly + polySuu) * 2;
  while (pos < endPos && pos < reader.length - 4) {
    reader.seek(pos);
    const wf = reader.readUint16();
    if (wf === 65535) break;
    if ((wf & 33008) === 32784) {
      pos += 46;
      continue;
    }
    if ((wf & 33008) === 32768) {
      reader.seek(pos + 2);
      textureName = reader.readString(16).trim();
      pos += 18;
      continue;
    }
    if (wf === 84) {
      reader.seek(pos + 2);
      const ws = reader.readUint16();
      pos += 4;
      for (let k = 0; k < ws; k++) {
        reader.seek(pos);
        faces.push(readFaceUV(reader));
        pos += 30;
      }
      continue;
    }
    if (wf === 21587) {
      reader.seek(pos + 2);
      const ws = reader.readUint16();
      pos += 4;
      reader.seek(pos);
      const firstFace = readFaceUV(reader);
      pos += 30;
      const stripVerts = [
        { idx: firstFace.i1, u: firstFace.u1, v: firstFace.v1 },
        { idx: firstFace.i2, u: firstFace.u2, v: firstFace.v2 },
        { idx: firstFace.i3, u: firstFace.u3, v: firstFace.v3 }
      ];
      for (let k = 0; k < ws - 1; k++) {
        reader.seek(pos);
        const idx = reader.readInt16();
        const u = reader.readFloat32();
        const v = reader.readFloat32();
        stripVerts.push({ idx, u, v });
        pos += 10;
      }
      for (let k = 0; k < stripVerts.length - 2; k++) {
        const a = stripVerts[k], b = stripVerts[k + 1], c = stripVerts[k + 2];
        if (a.idx === b.idx || b.idx === c.idx || a.idx === c.idx) continue;
        if (k % 2 === 0) {
          faces.push({ i1: a.idx, i2: b.idx, i3: c.idx, u1: a.u, v1: a.v, u2: b.u, v2: b.v, u3: c.u, v3: c.v });
        } else {
          faces.push({ i1: a.idx, i2: c.idx, i3: b.idx, u1: a.u, v1: a.v, u2: c.u, v2: c.v, u3: b.u, v3: b.v });
        }
      }
      continue;
    }
    if (wf === 17235) {
      reader.seek(pos + 2);
      const ws = reader.readUint16();
      pos += ws * 20 + 12;
      continue;
    }
    if (wf === 67) {
      reader.seek(pos + 2);
      const ws = reader.readUint16();
      pos += ws * 10 + 4;
      continue;
    }
    break;
  }
  return { faces, textureName };
}
function readFaceUV(reader) {
  return {
    i1: reader.readInt16(),
    i2: reader.readInt16(),
    i3: reader.readInt16(),
    u1: reader.readFloat32(),
    v1: reader.readFloat32(),
    u2: reader.readFloat32(),
    v2: reader.readFloat32(),
    u3: reader.readFloat32(),
    v3: reader.readFloat32()
  };
}
function resolveBoneIdx(tblIdx, boneTbl, isIndirect) {
  return isIndirect ? boneTbl[tblIdx] ?? 0 : tblIdx;
}
function transformVertices(noB1, noB2, mv1Data, mv2Data, boneAssign, boneTbl, skelMatrices, flip, isIndirect) {
  const verts = [];
  for (let i = 0; i < noB1; i++) {
    const src = mv1Data[i];
    let x = src.x, y = src.y, z = src.z;
    if (i < boneAssign.length) {
      const b3 = boneAssign[i];
      const tblIdx = flip ? b3.rightL : b3.leftL;
      const boneIdx = resolveBoneIdx(tblIdx, boneTbl, isIndirect);
      if (boneIdx < skelMatrices.length) {
        let m = skelMatrices[boneIdx];
        if (flip) m = applyMirrorFlag(m, b3.flgL);
        const t = mat4TransformPoint(m, x, y, z, 1);
        x = t[0];
        y = t[1];
        z = t[2];
      }
    }
    verts.push({ x, y, z, nx: src.nx, ny: src.ny, nz: src.nz });
  }
  for (let i = 0; i < noB2; i++) {
    const src = mv2Data[i];
    const bIdx = noB1 + i;
    let px = src.x1, py = src.y1, pz = src.z1;
    if (bIdx < boneAssign.length) {
      const b3 = boneAssign[bIdx];
      const tblIdxL = flip ? b3.rightL : b3.leftL;
      const tblIdxH = flip ? b3.rightH : b3.leftH;
      const boneIdxL = resolveBoneIdx(tblIdxL, boneTbl, isIndirect);
      const boneIdxH = resolveBoneIdx(tblIdxH, boneTbl, isIndirect);
      px = 0;
      py = 0;
      pz = 0;
      if (boneIdxL < skelMatrices.length) {
        let m = skelMatrices[boneIdxL];
        if (flip) m = applyMirrorFlag(m, b3.flgL);
        const t = mat4TransformPoint(m, src.x1, src.y1, src.z1, src.w1);
        px += t[0];
        py += t[1];
        pz += t[2];
      }
      if (boneIdxH < skelMatrices.length) {
        let m = skelMatrices[boneIdxH];
        if (flip) m = applyMirrorFlag(m, b3.flgH);
        const t = mat4TransformPoint(m, src.x2, src.y2, src.z2, src.w2);
        px += t[0];
        py += t[1];
        pz += t[2];
      }
    }
    verts.push({ x: px, y: py, z: pz, nx: src.nx1, ny: src.ny1, nz: src.nz1 });
  }
  return verts;
}
function expandFaces(rawVerts, faces, reverseWinding, perVertexBoneIndices, perVertexBoneWeights, dualBone) {
  const n = faces.length * 3;
  const positions = new Float32Array(n * 3);
  const normals = new Float32Array(n * 3);
  const uvs = new Float32Array(n * 2);
  const boneIndices = new Uint8Array(n * 4);
  const boneWeights = new Float32Array(n * 4);
  let dbLocalPos1;
  let dbLocalPos2;
  let dbWeights;
  if (dualBone) {
    dbLocalPos1 = new Float32Array(n * 3);
    dbLocalPos2 = new Float32Array(n * 3);
    dbWeights = new Float32Array(n * 2);
  }
  for (let f = 0; f < faces.length; f++) {
    const face = faces[f];
    const base = f * 3;
    const fi = reverseWinding ? [face.i1, face.i3, face.i2] : [face.i1, face.i2, face.i3];
    const fu = reverseWinding ? [[face.u1, face.v1], [face.u3, face.v3], [face.u2, face.v2]] : [[face.u1, face.v1], [face.u2, face.v2], [face.u3, face.v3]];
    for (let v = 0; v < 3; v++) {
      const srcIdx = fi[v];
      const vert = rawVerts[srcIdx];
      if (!vert) continue;
      const idx = base + v;
      positions[idx * 3] = vert.x;
      positions[idx * 3 + 1] = vert.y;
      positions[idx * 3 + 2] = vert.z;
      normals[idx * 3] = vert.nx;
      normals[idx * 3 + 1] = vert.ny;
      normals[idx * 3 + 2] = vert.nz;
      uvs[idx * 2] = fu[v][0];
      uvs[idx * 2 + 1] = fu[v][1];
      if (perVertexBoneIndices && perVertexBoneWeights) {
        boneIndices[idx * 4] = perVertexBoneIndices[srcIdx * 4];
        boneIndices[idx * 4 + 1] = perVertexBoneIndices[srcIdx * 4 + 1];
        boneIndices[idx * 4 + 2] = perVertexBoneIndices[srcIdx * 4 + 2];
        boneIndices[idx * 4 + 3] = perVertexBoneIndices[srcIdx * 4 + 3];
        boneWeights[idx * 4] = perVertexBoneWeights[srcIdx * 4];
        boneWeights[idx * 4 + 1] = perVertexBoneWeights[srcIdx * 4 + 1];
        boneWeights[idx * 4 + 2] = perVertexBoneWeights[srcIdx * 4 + 2];
        boneWeights[idx * 4 + 3] = perVertexBoneWeights[srcIdx * 4 + 3];
      }
      if (dualBone && dbLocalPos1 && dbLocalPos2 && dbWeights) {
        dbLocalPos1[idx * 3] = dualBone.localPos1[srcIdx * 3];
        dbLocalPos1[idx * 3 + 1] = dualBone.localPos1[srcIdx * 3 + 1];
        dbLocalPos1[idx * 3 + 2] = dualBone.localPos1[srcIdx * 3 + 2];
        dbLocalPos2[idx * 3] = dualBone.localPos2[srcIdx * 3];
        dbLocalPos2[idx * 3 + 1] = dualBone.localPos2[srcIdx * 3 + 1];
        dbLocalPos2[idx * 3 + 2] = dualBone.localPos2[srcIdx * 3 + 2];
        dbWeights[idx * 2] = dualBone.weights[srcIdx * 2];
        dbWeights[idx * 2 + 1] = dualBone.weights[srcIdx * 2 + 1];
      }
    }
  }
  return { positions, normals, uvs, boneIndices, boneWeights, dualBoneLocalPos1: dbLocalPos1, dualBoneLocalPos2: dbLocalPos2, dualBoneWeights: dbWeights };
}
function buildSkinningArrays(noB1, noB2, boneAssign, boneTbl, isIndirect, flip) {
  const totalVerts = noB1 + noB2;
  const boneIndices = new Uint8Array(totalVerts * 4);
  const boneWeights = new Float32Array(totalVerts * 4);
  for (let i = 0; i < noB1; i++) {
    if (i < boneAssign.length) {
      const b3 = boneAssign[i];
      const tblIdx = flip ? b3.rightL : b3.leftL;
      const boneIdx = resolveBoneIdx(tblIdx, boneTbl, isIndirect);
      boneIndices[i * 4] = boneIdx;
      boneWeights[i * 4] = 1;
    }
  }
  for (let i = 0; i < noB2; i++) {
    const bIdx = noB1 + i;
    if (bIdx < boneAssign.length) {
      const b3 = boneAssign[bIdx];
      const tblIdxL = flip ? b3.rightL : b3.leftL;
      const tblIdxH = flip ? b3.rightH : b3.leftH;
      boneIndices[bIdx * 4 + 0] = resolveBoneIdx(tblIdxL, boneTbl, isIndirect);
      boneIndices[bIdx * 4 + 1] = resolveBoneIdx(tblIdxH, boneTbl, isIndirect);
      boneWeights[bIdx * 4 + 0] = 1;
      boneWeights[bIdx * 4 + 1] = 1;
    }
  }
  return { boneIndices, boneWeights };
}
function buildDualBoneArrays(noB1, noB2, mv1Data, mv2Data, boneAssign, flip) {
  if (noB2 === 0) return null;
  const total = noB1 + noB2;
  const localPos1 = new Float32Array(total * 3);
  const localPos2 = new Float32Array(total * 3);
  const weights = new Float32Array(total * 2);
  for (let i = 0; i < noB1; i++) {
    let x = mv1Data[i].x, y = mv1Data[i].y, z = mv1Data[i].z;
    if (flip && i < boneAssign.length) {
      const flg = boneAssign[i].flgL;
      if (flg === 1) x = -x;
      else if (flg === 2) y = -y;
      else if (flg === 3) z = -z;
    }
    localPos1[i * 3] = x;
    localPos1[i * 3 + 1] = y;
    localPos1[i * 3 + 2] = z;
    weights[i * 2] = 1;
    weights[i * 2 + 1] = 0;
  }
  for (let i = 0; i < noB2; i++) {
    const idx = noB1 + i;
    const src = mv2Data[i];
    let x1 = src.x1, y1 = src.y1, z1 = src.z1;
    let x2 = src.x2, y2 = src.y2, z2 = src.z2;
    if (flip && idx < boneAssign.length) {
      const b3 = boneAssign[idx];
      if (b3.flgL === 1) x1 = -x1;
      else if (b3.flgL === 2) y1 = -y1;
      else if (b3.flgL === 3) z1 = -z1;
      if (b3.flgH === 1) x2 = -x2;
      else if (b3.flgH === 2) y2 = -y2;
      else if (b3.flgH === 3) z2 = -z2;
    }
    localPos1[idx * 3] = x1;
    localPos1[idx * 3 + 1] = y1;
    localPos1[idx * 3 + 2] = z1;
    localPos2[idx * 3] = x2;
    localPos2[idx * 3 + 1] = y2;
    localPos2[idx * 3 + 2] = z2;
    weights[idx * 2] = src.w1;
    weights[idx * 2 + 1] = src.w2;
  }
  return { localPos1, localPos2, weights };
}
function parseVertexBlock(reader, dataOffset, _dataLength, textureMap, skelMatrices) {
  reader.seek(dataOffset);
  const hdr = readDat2AHeader(reader);
  const modelType = hdr.type & 127;
  const isCloth = modelType === 1;
  reader.seek(dataOffset + hdr.offsetWeight * 2);
  const noB1 = reader.readUint16();
  const noB2 = reader.readUint16();
  const boneTbl = [];
  reader.seek(dataOffset + hdr.offsetBoneTbl * 2);
  for (let i = 0; i < hdr.boneTblSuu; i++) boneTbl.push(reader.readUint16());
  const boneAssign = [];
  reader.seek(dataOffset + hdr.offsetBone * 2);
  for (let i = 0; i < hdr.boneSuu / 2; i++) {
    const low = reader.readUint16(), high = reader.readUint16();
    boneAssign.push({
      leftL: low & 127,
      rightL: low >> 7 & 127,
      flgL: low >> 14 & 3,
      leftH: high & 127,
      rightH: high >> 7 & 127,
      flgH: high >> 14 & 3
    });
  }
  const mv1Size = isCloth ? 12 : 24;
  const vertexByteOffset = dataOffset + hdr.offsetVertex * 2;
  const mv1Data = [];
  reader.seek(vertexByteOffset);
  for (let i = 0; i < noB1; i++) {
    const x = reader.readFloat32(), y = reader.readFloat32(), z = reader.readFloat32();
    if (isCloth) {
      mv1Data.push({ x, y, z, nx: 0, ny: 1, nz: 0 });
    } else {
      mv1Data.push({ x, y, z, nx: reader.readFloat32(), ny: reader.readFloat32(), nz: reader.readFloat32() });
    }
  }
  const mv2Data = [];
  reader.seek(vertexByteOffset + noB1 * mv1Size);
  for (let i = 0; i < noB2; i++) {
    const x1 = reader.readFloat32(), x2 = reader.readFloat32();
    const y1 = reader.readFloat32(), y2 = reader.readFloat32();
    const z1 = reader.readFloat32(), z2 = reader.readFloat32();
    const w1 = reader.readFloat32(), w2 = reader.readFloat32();
    let nx1 = 0, ny1 = 1, nz1 = 0;
    if (!isCloth) {
      nx1 = reader.readFloat32();
      reader.skip(4);
      ny1 = reader.readFloat32();
      reader.skip(4);
      nz1 = reader.readFloat32();
      reader.skip(4);
    }
    mv2Data.push({ x1, x2, y1, y2, z1, z2, w1, w2, nx1, ny1, nz1 });
  }
  const { faces, textureName } = parsePolygonCommands(reader, dataOffset, hdr.offsetPoly, hdr.polySuu);
  if (faces.length === 0) return [];
  const materialIndex = textureName ? textureMap.get(textureName) ?? 0 : 0;
  const meshes = [];
  if (!skelMatrices) {
    const rawVerts = [
      ...mv1Data,
      ...mv2Data.map((s) => ({ x: s.x1, y: s.y1, z: s.z1, nx: s.nx1, ny: s.ny1, nz: s.nz1 }))
    ];
    const { positions, normals, uvs } = expandFaces(rawVerts, faces, false);
    meshes.push({
      vertices: positions,
      normals,
      uvs,
      indices: new Uint16Array(positions.length / 3),
      boneIndices: new Uint8Array(0),
      boneWeights: new Float32Array(0),
      materialIndex
    });
  } else {
    const isIndirect = !!(hdr.type & 128);
    const origVerts = transformVertices(noB1, noB2, mv1Data, mv2Data, boneAssign, boneTbl, skelMatrices, false, isIndirect);
    const skin = buildSkinningArrays(noB1, noB2, boneAssign, boneTbl, isIndirect, false);
    const dualBone = buildDualBoneArrays(noB1, noB2, mv1Data, mv2Data, boneAssign, false);
    const orig = expandFaces(origVerts, faces, false, skin.boneIndices, skin.boneWeights, dualBone);
    meshes.push({
      vertices: orig.positions,
      normals: orig.normals,
      uvs: orig.uvs,
      indices: new Uint16Array(orig.positions.length / 3),
      boneIndices: orig.boneIndices,
      boneWeights: orig.boneWeights,
      materialIndex,
      dualBoneLocalPos1: orig.dualBoneLocalPos1,
      dualBoneLocalPos2: orig.dualBoneLocalPos2,
      dualBoneWeights: orig.dualBoneWeights
    });
    if (hdr.flip !== 0) {
      const hasDualBone = noB2 > 0;
      const mirrorVerts = transformVertices(noB1, noB2, mv1Data, mv2Data, boneAssign, boneTbl, skelMatrices, true, isIndirect);
      const mirrorSkin = buildSkinningArrays(noB1, noB2, boneAssign, boneTbl, isIndirect, hasDualBone);
      const mirrorDualBone = buildDualBoneArrays(noB1, noB2, mv1Data, mv2Data, boneAssign, true);
      const mirror = expandFaces(mirrorVerts, faces, true, mirrorSkin.boneIndices, mirrorSkin.boneWeights, mirrorDualBone);
      meshes.push({
        vertices: mirror.positions,
        normals: mirror.normals,
        uvs: mirror.uvs,
        indices: new Uint16Array(mirror.positions.length / 3),
        boneIndices: mirror.boneIndices,
        boneWeights: mirror.boneWeights,
        materialIndex,
        dualBoneLocalPos1: mirror.dualBoneLocalPos1,
        dualBoneLocalPos2: mirror.dualBoneLocalPos2,
        dualBoneWeights: mirror.dualBoneWeights
      });
    }
  }
  return meshes;
}
function parseMeshes(_reader) {
  return [];
}
export {
  parseMeshes,
  parseVertexBlock,
  triangleStripToList
};
//# sourceMappingURL=MeshParser.js.map
