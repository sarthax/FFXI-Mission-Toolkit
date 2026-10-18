// The pinned upstream ffxi-install dependency pulls in unrar-sys.
// On Windows its native objects call Win32 registry, token and CryptoAPI
// functions from Advapi32; the transitive crate does not request the import
// library itself. Link it explicitly for our standalone executable/tests.
fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        println!("cargo:rustc-link-lib=advapi32");
    }
}
