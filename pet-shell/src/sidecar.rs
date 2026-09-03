use std::env;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

/// Supervises the Python Brain sidecar process (cross-platform for Linux & Windows).
/// Automatically starts it, monitors its health, and restarts it if it crashes.
pub struct SidecarSupervisor {
    running: Arc<AtomicBool>,
}

impl SidecarSupervisor {
    pub fn start() -> Self {
        let running = Arc::new(AtomicBool::new(true));
        let r = running.clone();

        thread::spawn(move || {
            println!("[Supervisor] Starting pet-brain sidecar supervisor...");
            let mut restart_count = 0;

            while r.load(Ordering::SeqCst) {
                match Self::spawn_brain_process() {
                    Ok(mut child) => {
                        println!("[Supervisor] Spawned pet-brain (PID: {})", child.id());

                        // Monitor child process
                        loop {
                            if !r.load(Ordering::SeqCst) {
                                println!("[Supervisor] Shell shutting down. Terminating brain PID: {}", child.id());
                                let _ = child.kill();
                                let _ = child.wait();
                                return;
                            }

                            match child.try_wait() {
                                Ok(Some(status)) => {
                                    println!("[Supervisor] pet-brain exited with status: {}", status);
                                    break; // Break to restart loop
                                }
                                Ok(None) => {
                                    thread::sleep(Duration::from_millis(500));
                                }
                                Err(e) => {
                                    println!("[Supervisor] Error waiting on pet-brain: {}", e);
                                    break;
                                }
                            }
                        }
                    }
                    Err(e) => {
                        println!("[Supervisor] Failed to spawn pet-brain: {}", e);
                    }
                }

                if !r.load(Ordering::SeqCst) {
                    break;
                }

                restart_count += 1;
                let backoff = (restart_count as u64).min(5);
                println!("[Supervisor] Restarting pet-brain in {}s (restart #{})", backoff, restart_count);
                thread::sleep(Duration::from_secs(backoff));
            }
        });

        Self { running }
    }

    fn spawn_brain_process() -> std::io::Result<Child> {
        let (cmd, args, working_dir) = Self::locate_brain_target()?;
        println!("[Supervisor] Executing: {} {:?} in {:?}", cmd, args, working_dir);

        let mut command = Command::new(&cmd);
        command.args(&args);
        if let Some(dir) = working_dir {
            command.current_dir(dir);
        }

        command.spawn()
    }

    fn locate_brain_target() -> std::io::Result<(String, Vec<String>, Option<PathBuf>)> {
        // 1. Check explicit environment override
        if let Ok(env_bin) = env::var("DESKTOP_PET_BRAIN_BIN") {
            let p = PathBuf::from(&env_bin);
            if p.exists() {
                let parent = p.parent().map(|p| p.to_path_buf());
                return Ok((p.to_string_lossy().to_string(), vec![], parent));
            }
        }

        // 2. Check executable directory (Linux & Windows)
        if let Ok(exe_path) = env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let candidates = [
                    exe_dir.join("pet-brain"),
                    exe_dir.join("pet-brain.exe"),
                    exe_dir.join("pet-brain.sh"),
                    exe_dir.join("pet-brain.bat"),
                    exe_dir.join("../pet-brain/pet-brain"),
                    exe_dir.join("../pet-brain/pet-brain.exe"),
                    exe_dir.join("../bin/pet-brain"),
                    exe_dir.join("../bin/pet-brain.exe"),
                    exe_dir.join("pet-brain/main.py"),
                    exe_dir.join("../pet-brain/main.py"),
                ];

                for candidate in candidates {
                    if candidate.exists() {
                        if candidate.extension().map_or(false, |ext| ext == "py") {
                            let python_bin = Self::find_python_interpreter(candidate.parent().unwrap());
                            let parent = candidate.parent().map(|p| p.to_path_buf());
                            return Ok((python_bin, vec![candidate.to_string_lossy().to_string()], parent));
                        } else {
                            let parent = candidate.parent().map(|p| p.to_path_buf());
                            return Ok((candidate.to_string_lossy().to_string(), vec![], parent));
                        }
                    }
                }
            }
        }

        // 3. Check Windows LocalAppData & Linux Home directories
        let mut base_dirs = Vec::new();
        if let Ok(local_app_data) = env::var("LOCALAPPDATA") {
            base_dirs.push(PathBuf::from(local_app_data).join("desktop-pet"));
        }
        if let Ok(app_data) = env::var("APPDATA") {
            base_dirs.push(PathBuf::from(app_data).join("desktop-pet"));
        }
        if let Ok(home) = env::var("HOME") {
            base_dirs.push(PathBuf::from(home).join(".local/share/desktop-pet"));
        }

        for installed_dir in base_dirs {
            let candidates = [
                installed_dir.join("bin/pet-brain"),
                installed_dir.join("bin/pet-brain.exe"),
                installed_dir.join("pet-brain"),
                installed_dir.join("pet-brain.exe"),
                installed_dir.join("pet-brain/main.py"),
            ];

            for candidate in candidates {
                if candidate.exists() {
                    if candidate.extension().map_or(false, |ext| ext == "py") {
                        let python_bin = Self::find_python_interpreter(&installed_dir);
                        return Ok((python_bin, vec![candidate.to_string_lossy().to_string()], Some(installed_dir)));
                    } else {
                        return Ok((candidate.to_string_lossy().to_string(), vec![], Some(installed_dir)));
                    }
                }
            }
        }

        // 4. Fallback for Development (relative workspace directory)
        let dev_candidates = [
            PathBuf::from("pet-brain/main.py"),
            PathBuf::from("../pet-brain/main.py"),
        ];

        for candidate in dev_candidates {
            if candidate.exists() {
                let work_dir = candidate.parent().unwrap().parent().map(|p| p.to_path_buf());
                let python_bin = Self::find_python_interpreter(candidate.parent().unwrap());
                return Ok((
                    python_bin,
                    vec![candidate.to_string_lossy().to_string()],
                    work_dir,
                ));
            }
        }

        Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "Could not locate pet-brain executable or script in standard paths",
        ))
    }

    fn find_python_interpreter(base_dir: &Path) -> String {
        // Check for venv (Linux & Windows)
        let venv_candidates = [
            base_dir.join(".venv/bin/python"),
            base_dir.join(".venv/Scripts/python.exe"),
            base_dir.join("venv/bin/python"),
            base_dir.join("venv/Scripts/python.exe"),
            base_dir.join("../.venv/bin/python"),
            base_dir.join("../.venv/Scripts/python.exe"),
        ];

        for venv in venv_candidates {
            if venv.exists() {
                return venv.to_string_lossy().to_string();
            }
        }

        // Check conda env if active
        if let Ok(conda_prefix) = env::var("CONDA_PREFIX") {
            let conda_py_unix = PathBuf::from(&conda_prefix).join("bin/python");
            let conda_py_win = PathBuf::from(&conda_prefix).join("python.exe");
            if conda_py_unix.exists() {
                return conda_py_unix.to_string_lossy().to_string();
            }
            if conda_py_win.exists() {
                return conda_py_win.to_string_lossy().to_string();
            }
        }

        if cfg!(target_os = "windows") {
            "python.exe".to_string()
        } else {
            "python3".to_string()
        }
    }
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
    }
}
