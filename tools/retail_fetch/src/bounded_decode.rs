//! Bounded decoding of complete-file PlayOnline payloads.
use ffxi_install::lz::BitReader;
use std::io::Read;

pub fn decode_direct_bounded(payload: &[u8], expected: u64, cap: u64) -> Result<Vec<u8>, String> {
    if expected > cap || expected > usize::MAX as u64 {
        return Err("declared file exceeds decoded-size limit".into());
    }
    let (&flag, body) = payload.split_first().ok_or("empty direct payload")?;
    let decoded = match flag {
        1 => {
            if body.len() as u64 != expected {
                return Err("stored payload length differs from manifest".into());
            }
            body.to_vec()
        }
        3 => {
            let mut decoder = flate2::read::ZlibDecoder::new(body);
            let mut bounded = decoder.by_ref().take(expected + 1);
            let mut result = Vec::new();
            bounded.read_to_end(&mut result).map_err(|e| format!("zlib: {e}"))?;
            result
        }
        _ => {
            let mut reader = BitReader::new(body)?;
            let mut out = Vec::with_capacity((expected as usize).min(1024 * 1024));
            while reader.remaining() > 0 {
                if reader.read(1)? == 0 {
                    if out.len() >= expected as usize {
                        return Err("SLC expands beyond manifest length".into());
                    }
                    out.push(reader.read(8)? as u8);
                } else {
                    let distance = reader.read(16)? as usize;
                    let count = reader.read(8)? as usize;
                    if distance == 0 || distance > out.len() {
                        return Err("invalid SLC back-reference".into());
                    }
                    if count > (expected as usize).saturating_sub(out.len()) {
                        return Err("SLC expands beyond manifest length".into());
                    }
                    for _ in 0..count {
                        let byte = out[out.len() - distance];
                        out.push(byte);
                    }
                }
            }
            out
        }
    };
    if decoded.len() as u64 != expected {
        return Err(format!("decoded length {} differs from manifest length {expected}", decoded.len()));
    }
    Ok(decoded)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_stored_oversize() {
        assert!(decode_direct_bounded(b"\x01abcd", 3, 10).is_err());
        assert_eq!(decode_direct_bounded(b"\x01abc", 3, 10).unwrap(), b"abc");
    }
    #[test]
    fn rejects_invalid_slc_reference() {
        // 25 declared bits: one back-reference, 16-bit distance=1, 8-bit length=1
        assert!(decode_direct_bounded(&[2, 25, 0, 0, 0, 3, 0, 2, 0], 1, 10).is_err());
    }
    #[test]
    fn bounds_zlib_inflation() {
        use std::io::Write;
        let mut z = flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::default());
        z.write_all(&vec![b'x'; 8192]).unwrap();
        let mut wire = vec![3];
        wire.extend_from_slice(&z.finish().unwrap());
        assert!(decode_direct_bounded(&wire, 10, 128).is_err());
        assert_eq!(decode_direct_bounded(&wire, 8192, 8192).unwrap().len(), 8192);
    }
}
