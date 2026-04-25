// `src-tauri/src/lib.rs` - The wait loop can be implemented like this if you want to explicitly block:

use std::net::TcpStream;
use std::time::{Duration, Instant};

fn wait_for_backend() -> bool {
    let start = Instant::now();
    let timeout = Duration::from_secs(10);
    
    while start.elapsed() < timeout {
        if TcpStream::connect("127.0.0.1:5000").is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    false
}
