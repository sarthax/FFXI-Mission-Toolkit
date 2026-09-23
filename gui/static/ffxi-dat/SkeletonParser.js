function quatToMatrix(qi, qj, qk, qw, tx, ty, tz) {
  const x = qi, y = qj, z = qk, w = qw;
  const x2 = x + x, y2 = y + y, z2 = z + z;
  const xx = x * x2, xy = x * y2, xz = x * z2;
  const yy = y * y2, yz = y * z2, zz = z * z2;
  const wx = w * x2, wy = w * y2, wz = w * z2;
  return [
    1 - yy - zz,
    xy + wz,
    xz - wy,
    0,
    xy - wz,
    1 - xx - zz,
    yz + wx,
    0,
    xz + wy,
    yz - wx,
    1 - xx - yy,
    0,
    tx,
    ty,
    tz,
    1
  ];
}
function mat4Multiply(a, b) {
  const r = new Array(16).fill(0);
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 4; j++)
      for (let k = 0; k < 4; k++)
        r[i * 4 + j] += a[i * 4 + k] * b[k * 4 + j];
  return r;
}
function mat4TransformPoint(m, x, y, z, w) {
  return [
    x * m[0] + y * m[4] + z * m[8] + w * m[12],
    x * m[1] + y * m[5] + z * m[9] + w * m[13],
    x * m[2] + y * m[6] + z * m[10] + w * m[14]
  ];
}
const BONE_SIZE = 30;
function parseSkeleton(reader) {
  let offset = 0;
  while (offset < reader.length - 8) {
    reader.seek(offset + 4);
    const packed = reader.readUint32();
    const type = packed & 127;
    const next = packed >> 7 & 524287;
    if (type === 41) {
      const dataStart = offset + 16;
      reader.seek(dataStart);
      reader.skip(2);
      const noBone = reader.readInt16();
      if (noBone <= 0 || noBone > 200) return null;
      const bones = [];
      const matrices = [];
      for (let i = 0; i < noBone; i++) {
        const boneOffset = dataStart + 4 + i * BONE_SIZE;
        reader.seek(boneOffset);
        const parentRaw = reader.readUint8();
        const parent = i === 0 ? 255 : parentRaw;
        reader.skip(1);
        const qi = reader.readFloat32();
        const qj = reader.readFloat32();
        const qk = reader.readFloat32();
        const qw = reader.readFloat32();
        const tx = reader.readFloat32();
        const ty = reader.readFloat32();
        const tz = reader.readFloat32();
        bones.push({
          parentIndex: parent === 255 ? -1 : parent,
          position: [tx, ty, tz],
          rotation: [qi, qj, qk, qw]
        });
        const local = quatToMatrix(qi, qj, qk, qw, tx, ty, tz);
        if (parent === 255) {
          matrices.push(local);
        } else {
          matrices.push(mat4Multiply(local, matrices[parent]));
        }
      }
      return { bones, matrices };
    }
    if (next === 0) break;
    offset += next * 16;
    if (offset > reader.length) break;
  }
  return null;
}
const SKELETON_PATHS = {
  1: "ROM/27/82.dat",
  // Hume Male
  2: "ROM/32/58.dat",
  // Hume Female
  3: "ROM/37/31.dat",
  // Elvaan Male
  4: "ROM/42/4.dat",
  // Elvaan Female
  5: "ROM/46/93.dat",
  // Tarutaru Male
  6: "ROM/46/93.dat",
  // Tarutaru Female (shares with Male)
  7: "ROM/51/89.dat",
  // Mithra
  8: "ROM/56/59.dat"
  // Galka
};
export {
  SKELETON_PATHS,
  mat4TransformPoint,
  parseSkeleton
};
//# sourceMappingURL=SkeletonParser.js.map
