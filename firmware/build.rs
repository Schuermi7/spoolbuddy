fn main() {
    // Ensure the build is rerun if linker script changes
    println!("cargo:rerun-if-changed=build.rs");
}
