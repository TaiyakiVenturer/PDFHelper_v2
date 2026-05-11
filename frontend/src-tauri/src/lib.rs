use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use tauri_plugin_dialog::DialogExt;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

fn fatal(app: &tauri::App, msg: &str) -> ! {
    app.dialog().message(msg).title("PDFHelper 錯誤").blocking_show();
    std::process::exit(1);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_child: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let child_for_exit = backend_child.clone();

    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(move |app| {
            #[cfg(not(debug_assertions))]
            {
                let exe_path = match std::env::current_exe() {
                    Ok(p) => p,
                    Err(e) => fatal(app, &format!("無法取得程式路徑：{e}")),
                };
                let exe_dir = match exe_path.parent() {
                    Some(d) => d.to_path_buf(),
                    None => fatal(app, "無法解析程式目錄"),
                };

                let python = exe_dir.join("backend").join(".venv").join("Scripts").join("python.exe");
                let main_py = exe_dir.join("backend").join("main.py");

                if !python.exists() || !main_py.exists() {
                    fatal(
                        app,
                        &format!(
                            "找不到後端程式：\n{}\n\n請重新執行安裝程式。",
                            python.display()
                        ),
                    );
                }

                let mut cmd = Command::new(&python);
                cmd.arg(&main_py).current_dir(exe_dir.join("backend"));

                #[cfg(target_os = "windows")]
                cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

                match cmd.spawn() {
                    Ok(child) => {
                        *backend_child.lock().unwrap() = Some(child);
                    }
                    Err(e) => fatal(app, &format!("後端程序啟動失敗：{e}")),
                }
            }

            Ok(())
        });

    #[cfg(debug_assertions)]
    let builder = builder.plugin(tauri_plugin_mcp_bridge::init());

    builder
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(move |_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut guard) = child_for_exit.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
