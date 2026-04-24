// Thin entry point — delegates entirely to lib.rs so mobile targets work.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    health_os_lib::run();
}