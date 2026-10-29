//! Fetch one licensed FFXI retail patch file without updating an installation.
use ffxi_install::manifest::{self, FileSig};
mod bounded_decode;
use bounded_decode::decode_direct_bounded;
use ffxi_install::patch_client::{Server, Session, TITLE_FFXI};
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::io::Write;
use std::path::{Component, Path, PathBuf};

const MAX_BYTES: u64 = 128 * 1024 * 1024;

fn relative_path(input: &str) -> Result<PathBuf, String> {
    if input.is_empty() || input.contains('\\') || input.contains(':') || input.contains('\0') {
        return Err("invalid manifest path".into());
    }
    let path = Path::new(input);
    if !path.components().all(|c| matches!(c, Component::Normal(_))) {
        return Err("manifest path must be relative without dot or parent components".into());
    }
    Ok(path.to_owned())
}

fn argument(name: &str, args: &[String]) -> Option<String> {
    args.windows(2).find(|x| x[0] == name).map(|x| x[1].clone())
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().skip(1).collect();
    let file = argument("--file", &args);
    let list = args.iter().any(|x| x == "--list");
    let history = args.iter().any(|x| x == "--history");
    let plan = args.iter().any(|x| x == "--plan");
    let export = args.iter().any(|x| x == "--export-history-json");
    if [history, list, plan, export].iter().filter(|&&enabled| enabled).count() > 1 {
        return Err("choose only one of --list, --history, --plan, or --export-history-json".into());
    }
    if (history || plan) && file.is_none() {
        return Err("--history and --plan require --file MANIFEST_PATH".into());
    }
    if !list && !export && file.is_none() {
        return Err("usage: --list [--file SUBSTRING] OR --file MANIFEST_PATH --output DIRECTORY [--version EXACT_STAMP]".into());
    }
    let server = Server::for_title(TITLE_FFXI);
    let mut session = Session::connect(&server)?;
    let manifest_bytes = session.manifest()?;
    let manifest_text = String::from_utf8(manifest_bytes).map_err(|e| e.to_string())?;
    let manifest = manifest::parse(&manifest_text)?;
    if export {
        // Complete observation of the server's currently advertised history.
        // The caller is responsible for immutable snapshot storage and provenance.
        println!("{{\n  \"schema\": 1,\n  \"source\": \"playonline-patch-manifest:ffxi\",\n  \"files\": [");
        for (i, entry) in manifest.files.iter().enumerate() {
            if i > 0 { println!(","); }
            print!("    {{\"file\": \"{}\", \"versions\": [", json_escape(&entry.path));
            for (j, v) in entry.versions.iter().enumerate() {
                if j > 0 { print!(","); }
                print!("{{\"stamp\":\"{}\",\"decoded_bytes\":{},\"transfer_bytes\":{},\"server_path\":\"{}\"}}",
                    json_escape(&v.stamp), v.sig.len, v.direct_len, json_escape(&v.direct));
            }
            print!("]}}");
        }
        println!("\n  ]\n}}");
        return Ok(());
    }
    if list {
        let filter = file.unwrap_or_default().to_lowercase();
        for entry in &manifest.files {
            if entry.path.to_lowercase().contains(&filter) {
                if let Some(latest) = entry.versions.last() {
                    println!("{}  latest={}", entry.path, latest.stamp);
                }
            }
        }
        return Ok(());
    }
    let requested = file.unwrap();
    let entry = manifest.files.iter().find(|e| e.path.eq_ignore_ascii_case(&requested))
        .ok_or_else(|| format!("file not listed in server manifest: {requested}"))?;
    if history {
        for version in &entry.versions {
            println!("{}  {}  {} bytes  direct={} bytes", entry.path, version.stamp, version.sig.len, version.direct_len);
        }
        return Ok(());
    }
    let version = if let Some(stamp) = argument("--version", &args) {
        entry.versions.iter().find(|v| v.stamp == stamp)
            .ok_or_else(|| format!("version {stamp} is not listed for {}", entry.path))?
    } else {
        entry.current()
    };
    if version.sig.len > MAX_BYTES || version.direct_len > MAX_BYTES {
        return Err("file exceeds 128 MiB per-file safety bound".into());
    }
    if plan {
        let safe_path = relative_path(&entry.path)?;
        println!("plan: {} version={} decoded_bytes={} transfer_bytes={} server_path={} (nothing downloaded)",
            safe_path.display(), version.stamp, version.sig.len, version.direct_len, version.direct);
        return Ok(());
    }
    let output = argument("--output", &args).ok_or("provide --output DIRECTORY")?;
    let root = PathBuf::from(output);
    let rel = relative_path(&entry.path)?;
    let dest = root.join(rel);
    if dest.exists() {
        return Err(format!("refusing to overwrite {}", dest.display()));
    }
    // Never trust a manifest-supplied server path without checking its syntax.
    let _ = relative_path(&version.direct)?;
    let payload = session.fetch(&version.direct, version.direct_len, &mut |_| {})?;
    let decoded = decode_direct_bounded(&payload, version.sig.len, MAX_BYTES)?;
    validate_decoded_size(decoded.len(), version.sig.len)?;
    verify_signature(&decoded, &version.sig, &entry.path, &version.stamp)?;
    let parent = dest.parent().ok_or("invalid output path")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let sha256 = format!("{:x}", Sha256::digest(&decoded));
    save_new(parent, &dest, &decoded)?;
    // Written only after size and manifest-signature validation and a successful publish.
    let sidecar = PathBuf::from(format!("{}.provenance.json", dest.display()));
    let record = provenance_json(&entry.path, &version.stamp, version.sig.len, decoded.len() as u64, &sha256, unix_now());
    save_new(parent, &sidecar, record.as_bytes())?;
    println!("saved {} [{}] ({} bytes) SHA-256={}", dest.display(), version.stamp, decoded.len(), sha256);
    Ok(())
}

fn verify_signature(decoded: &[u8], expected: &FileSig, path: &str, stamp: &str) -> Result<(), String> {
    if FileSig::of(decoded) != *expected {
        return Err(format!("manifest signature mismatch for {path} at {stamp}"));
    }
    Ok(())
}

fn unix_now() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// Civil UTC date-time from a unix timestamp (Howard Hinnant's algorithm).
fn utc_iso(secs: u64) -> String {
    let days = (secs / 86400) as i64;
    let rem = secs % 86400;
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z.rem_euclid(146097);
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + if m <= 2 { 1 } else { 0 };
    format!("{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, rem % 3600 / 60, rem % 60)
}

fn json_escape(v: &str) -> String {
    v.chars().flat_map(|c| match c {
        '"' => "\\\"".chars().collect::<Vec<_>>(),
        '\\' => "\\\\".chars().collect(),
        c if (c as u32) < 0x20 => format!("\\u{:04x}", c as u32).chars().collect(),
        c => vec![c],
    }).collect()
}

/// Provenance sidecar. Contains no local filesystem paths. Indexer fields are
/// filled in later by the Toolkit, not by this tool.
fn provenance_json(file: &str, stamp: &str, expected: u64, actual: u64, sha256: &str, when: u64) -> String {
    format!(
        "{{
  \"schema\": 1,
  \"file\": \"{}\",
  \"retail_version\": \"{}\",
  \"source\": \"playonline-patch-manifest:ffxi\",
  \"retrieved_utc\": \"{}\",
  \"expected_decoded_bytes\": {},
  \"actual_decoded_bytes\": {},
  \"sha256\": \"{}\",
  \"manifest_signature_verified\": true,
  \"manifest_signature_kind\": \"legacy FileSig (length, byte sum, md5 prefix); not cryptographic\",
  \"downloader\": \"ffxi-retail-selective {}\",
  \"indexer\": null,
  \"index_result\": null
}}
",
        json_escape(file), json_escape(stamp), utc_iso(when), expected, actual, sha256, env!("CARGO_PKG_VERSION"))
}

fn validate_decoded_size(actual: usize, expected: u64) -> Result<(), String> {
    if actual as u64 > MAX_BYTES || actual as u64 != expected {
        return Err(format!("decoded file size mismatch or over limit: got {actual}, expected {expected}"));
    }
    Ok(())
}

fn save_new(parent: &Path, dest: &Path, decoded: &[u8]) -> Result<(), String> {
    let mut tmp = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    tmp.write_all(decoded).map_err(|e| e.to_string())?;
    tmp.flush().map_err(|e| e.to_string())?;
    // Linking is atomic and fails if the destination already exists, including
    // dangling symlinks. NamedTempFile owns and cleans up its exclusive staging file.
    fs::hard_link(tmp.path(), &dest)
        .map_err(|e| format!("cannot create destination safely: {e}"))?;
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("retail selective fetch failed: {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn publishes_without_replacing_existing_files() {
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("FFXiMain.dll");
        save_new(dir.path(), &dest, b"first").unwrap();
        assert!(save_new(dir.path(), &dest, b"second").is_err());
        assert_eq!(fs::read(&dest).unwrap(), b"first");
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
    }

    #[cfg(unix)]
    #[test]
    fn refuses_dangling_destination_symlink() {
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("FFXiMain.dll");
        let target = dir.path().join("missing");
        std::os::unix::fs::symlink(&target, &dest).unwrap();
        assert!(save_new(dir.path(), &dest, b"data").is_err());
        assert!(!target.exists());
        assert!(fs::symlink_metadata(&dest).unwrap().file_type().is_symlink());
    }

    #[test]
    fn sha256_fingerprint_is_stable() {
        assert_eq!(format!("{:x}", Sha256::digest(b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }

    #[test]
    fn rejects_incorrect_decoded_size() {
        assert!(validate_decoded_size(3, 3).is_ok());
        assert!(validate_decoded_size(4, 3).is_err());
        assert!(validate_decoded_size(3, MAX_BYTES + 1).is_err());
    }

    #[test]
    fn disallows_escape_paths() {
        for value in ["../FFXiMain.dll", "/tmp/escape", "C:/bad", "ROM/../bad", "ROM\\1\\2.DAT", ""] {
            assert!(relative_path(value).is_err(), "{value}");
        }
        assert!(relative_path("ROM/119/51.DAT").is_ok());
    }

    #[test]
    fn signature_mismatch_is_rejected() {
        let good = FileSig::of(b"hello world");
        assert!(verify_signature(b"hello world", &good, "f", "1").is_ok());
        assert!(verify_signature(b"hello w0rld", &good, "f", "1").is_err());
        assert!(verify_signature(b"hello world!", &good, "f", "1").is_err());
    }

    #[test]
    fn provenance_has_expected_fields_and_no_paths() {
        let j = provenance_json("FFXiMain.dll", "30261006_0", 3, 3, "ab", 1791195206);
        assert!(j.contains("\"retrieved_utc\": \"2026-10-05T"), "{j}");
        assert!(j.contains("\"manifest_signature_verified\": true"));
        assert!(!j.contains("D:") && !j.contains(":\\"));
        assert_eq!(utc_iso(0), "1970-01-01T00:00:00Z");
    }

    #[test]
    fn closed_port_fails_fast() {
        let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = l.local_addr().unwrap().port();
        drop(l);
        let mut server = Server::for_title(TITLE_FFXI);
        server.host = "127.0.0.1".into();
        server.port = port;
        assert!(Session::connect(&server).is_err());
    }

    #[cfg(windows)]
    #[test]
    fn refuses_dangling_destination_symlink_windows() {
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("FFXiMain.dll");
        let target = dir.path().join("missing");
        // Symlink creation needs Developer Mode or elevation; skip when unavailable.
        if std::os::windows::fs::symlink_file(&target, &dest).is_err() {
            eprintln!("skipped: cannot create symlink without privilege");
            return;
        }
        assert!(save_new(dir.path(), &dest, b"data").is_err());
        assert!(!target.exists());
    }
}
