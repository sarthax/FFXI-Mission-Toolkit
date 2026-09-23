var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
class DatReader {
  constructor(buffer) {
    __publicField(this, "view");
    __publicField(this, "offset");
    this.view = new DataView(buffer);
    this.offset = 0;
  }
  get position() {
    return this.offset;
  }
  get length() {
    return this.view.byteLength;
  }
  get remaining() {
    return this.view.byteLength - this.offset;
  }
  seek(offset) {
    if (offset < 0 || offset > this.view.byteLength)
      throw new RangeError(`Seek offset ${offset} out of bounds (0-${this.view.byteLength})`);
    this.offset = offset;
  }
  skip(bytes) {
    this.seek(this.offset + bytes);
  }
  readUint8() {
    const v = this.view.getUint8(this.offset);
    this.offset += 1;
    return v;
  }
  readInt8() {
    const v = this.view.getInt8(this.offset);
    this.offset += 1;
    return v;
  }
  readUint16() {
    const v = this.view.getUint16(this.offset, true);
    this.offset += 2;
    return v;
  }
  readInt16() {
    const v = this.view.getInt16(this.offset, true);
    this.offset += 2;
    return v;
  }
  readUint32() {
    const v = this.view.getUint32(this.offset, true);
    this.offset += 4;
    return v;
  }
  readInt32() {
    const v = this.view.getInt32(this.offset, true);
    this.offset += 4;
    return v;
  }
  readFloat32() {
    const v = this.view.getFloat32(this.offset, true);
    this.offset += 4;
    return v;
  }
  readBytes(count) {
    const arr = new Uint8Array(this.view.buffer, this.view.byteOffset + this.offset, count);
    this.offset += count;
    return new Uint8Array(arr);
  }
  readString(length) {
    const bytes = this.readBytes(length);
    let end = bytes.indexOf(0);
    if (end === -1) end = length;
    return new TextDecoder("utf-8").decode(bytes.subarray(0, end));
  }
  readVec3() {
    return [this.readFloat32(), this.readFloat32(), this.readFloat32()];
  }
  readQuat() {
    return [this.readFloat32(), this.readFloat32(), this.readFloat32(), this.readFloat32()];
  }
  peekUint32() {
    return this.view.getUint32(this.offset, true);
  }
  slice(offset, length) {
    const sliced = this.view.buffer.slice(
      this.view.byteOffset + offset,
      this.view.byteOffset + offset + length
    );
    return new DatReader(sliced);
  }
}
export {
  DatReader
};
//# sourceMappingURL=DatReader.js.map
