// HealthOS Posture Monitor — Tauri Rust core
// System tray, autostart, and Python backend launch.

use tauri::Manager;
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::menu::{Menu, MenuItem};
use std::sync::Mutex;
use std::process::{Child, Command};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

// We store both types of processes since dev mode uses std::process::Child (python script)
// while production uses tauri_plugin_shell::process::CommandChild (sidecar binary).
struct BackendProcess {
    std_child: Mutex<Option<Child>>,
    sidecar_child: Mutex<Option<CommandChild>>,
}

/// Spawn the Python AI backend — tries bundled sidecar first, falls back to venv script.
fn spawn_backend(app_handle: &tauri::AppHandle) -> BackendProcess {
    // Kill any zombie backend from a previous run
    let _ = Command::new("bash")
        .args(["-c", "fuser -k 5000/tcp 2>/dev/null || true"])
        .output();
    let _ = Command::new("cmd")
        .args(["/C", "netstat -ano | findstr :5000"])
        .output(); // basic windows check (would need taskkill for cleanup)
    std::thread::sleep(std::time::Duration::from_millis(500));

    // 1. Try launching the bundled PyInstaller sidecar binary (production)
    eprintln!("[HealthOS] Launching bundled PyInstaller sidecar backend...");
    match app_handle.shell().sidecar("healthos-backend") {
        Ok(sidecar_cmd) => {
            match sidecar_cmd.spawn() {
                Ok((_rx, child)) => {
                    eprintln!("[HealthOS] Sidecar backend started successfully. PID: {}", child.pid());
                    return BackendProcess {
                        std_child: Mutex::new(None),
                        sidecar_child: Mutex::new(Some(child)),
                    };
                }
                Err(e) => eprintln!("[HealthOS] Failed to spawn sidecar: {}", e),
            }
        }
        Err(e) => eprintln!("[HealthOS] Sidecar 'healthos-backend' not found: {}", e),
    }

    // 2. Fallback: Try the venv Python script (dev mode)
    let exe_dir = app_handle.path().resource_dir().unwrap_or_default();
    let venv_python = exe_dir.join("../../../ai-engine/venv/bin/python");
    let app_py = exe_dir.join("../../../ai-engine/app.py");

    if venv_python.exists() && app_py.exists() {
        eprintln!("[HealthOS] Starting backend (venv): {:?}", venv_python);
        match Command::new(&venv_python).arg(&app_py).spawn() {
            Ok(child) => {
                eprintln!("[HealthOS] Backend started (PID {})", child.id());
                return BackendProcess {
                    std_child: Mutex::new(Some(child)),
                    sidecar_child: Mutex::new(None),
                };
            }
            Err(e) => eprintln!("[HealthOS] Failed to start venv backend: {}", e),
        }
    }

    // 3. Last resort: system python3
    eprintln!("[HealthOS] Trying system python3 fallback...");
    let app_py_abs = exe_dir.join("../../../ai-engine/app.py");
    match Command::new("python3").arg(&app_py_abs).spawn() {
        Ok(child) => {
            eprintln!("[HealthOS] Backend started via system python (PID {})", child.id());
            BackendProcess {
                std_child: Mutex::new(Some(child)),
                sidecar_child: Mutex::new(None),
            }
        }
        Err(e) => {
            eprintln!("[HealthOS] All backend launch methods failed: {}", e);
            BackendProcess {
                std_child: Mutex::new(None),
                sidecar_child: Mutex::new(None),
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .setup(|app| {
            // ── Auto-launch Python backend ────────────────────────────────
            let backend_state = spawn_backend(app.handle());
            app.manage(backend_state);

            // ── Handle Autostart Minimized ────────────────────────────────
            if std::env::args().any(|arg| arg == "--minimized") {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.hide();
                }
            }

            // ── System Tray ───────────────────────────────────────────────
            let show_i = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "Hide Window", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit HealthOS", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &hide_i, &quit_i])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("HealthOS Posture Monitor")
                .menu(&menu)
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show" => {
                            if let Some(win) = app.get_webview_window("main") {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "hide" => {
                            if let Some(win) = app.get_webview_window("main") {
                                let _ = win.hide();
                            }
                        }
                        "quit" => {
                            // Kill backend before quitting
                            if let Some(state) = app.try_state::<BackendProcess>() {
                                if let Ok(mut guard) = state.std_child.lock() {
                                    if let Some(mut child) = guard.take() {
                                        let _ = child.kill();
                                    }
                                }
                                if let Ok(mut guard) = state.sidecar_child.lock() {
                                    if let Some(child) = guard.take() {
                                        let _ = child.kill();
                                    }
                                }
                                eprintln!("[HealthOS] Backend process killed.");
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        // ── Close → Hide to tray (don't actually quit) ────────────────
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running HealthOS");
}
