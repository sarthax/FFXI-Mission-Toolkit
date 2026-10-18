//! Fetch one licensed FFXI retail patch file without updating an installation.
use ffxi_install::manifest::{self, FileSig};
use ffxi_install::patch_client::{decode_direct_payload, Server, Session, TITLE_FFXI};
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
    if !list && file.is_none() {
        return Err("usage: --list [--file SUBSTRING] OR --file MANIFEST_PATH --output DIRECTORY [--version EXACT_STAMP]".into());
    }
    let server = Server::for_title(TITLE_FFXI);
    let mut session = Session::connect(&server)?;
    let manifest_bytes = session.manifest()?;
    let manifest_text = String::from_utf8(manifest_bytes).map_err(|e| e.to_string())?;
    let manifest = manifest::parse(&manifest_text)?;
    if list {
        let filter = file.unwrap_or_default().to_lowercase();
        for entry in &manifest.files {
            if entry.path.to_lowercase().contains(&filter) {
                println!("{}  latest={}", entry.path, entry.current().stamp);
            }
        }
        return Ok(());
    }
    let requested = file.unwrap();
    let entry = manifest.files.iter().find(|e| e.path.eq_ignore_ascii_case(&requested))
        .ok_or_else(|| format!("file not listed in server manifest: {requested}"))?;
    let version = if let Some(stamp) = argument("--version", &args) {
        entry.versions.iter().find(|v| v.stamp == stamp)
            .ok_or_else(|| format!("version {stamp} is not listed for {}", entry.path))?
    } else {
        entry.current()
    };
    if version.sig.len > MAX_BYTES || version.direct_len > MAX_BYTES {
        return Err("file exceeds 128 MiB per-file safety bound".into());
    }
    let output = argument("--output", &args).ok_or("provide --output DIRECTORY")?;
    let root = PathBuf::from(output);
    let rel = relative_path(&entry.path)?;
    let dest = root.join(rel);
    if dest.exists() {
        return Err(format!("refusing to overwrite {}", dest.display()));
    }
    let payload = session.fetch(&version.direct, version.direct_len, &mut |_| {})?;
    let decoded = decode_direct_payload(&payload)?;
    let signature = FileSig::of(&decoded);
    if signature != version.sig {
        return Err(format!("manifest signature mismatch for {} at {}", entry.path, version.stamp));
    }
    let parent = dest.parent().ok_or("invalid output path")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    save_new(parent, &dest, &decoded)?;
    println!("saved {} [{}] ({} bytes)", dest.display(), version.stamp, decoded.len());
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
    fn disallows_escape_paths() {
        for value in ["../FFXiMain.dll", "/tmp/escape", "C:/bad", "ROM/../bad", "ROM\\1\\2.DAT", ""] {
            assert!(relative_path(value).is_err(), "{value}");
        }
        assert!(relative_path("ROM/119/51.DAT").is_ok());
    }
}
