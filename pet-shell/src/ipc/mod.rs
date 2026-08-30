pub mod client;
pub mod pet {
    include!(concat!(env!("OUT_DIR"), "/pet.rs"));
}
