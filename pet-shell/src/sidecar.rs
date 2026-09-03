use std::env;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

/// Supervises the Python Brain sidecar process.
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
                                    // Child is still alive, sleep briefly
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
            let p = PathBuf::from(env_bin);
            if p.exists() {
                let parent = p.parent().map(|p| p.to_path_buf());
                return Ok((p.to_string_lossy().to_string(), vec![], parent));
            }
        }

        // 2. Check binary next to current executable (e.g. installed in ~/.local/share/desktop-pet/bin/)
        if let Ok(exe_path) = env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let candidates = [
                    exe_dir.join("pet-brain"),
                    exe_dir.join("pet-brain.sh"),
                    exe_dir.join("../pet-brain/pet-brain"),
                    exe_dir.join("../bin/pet-brain"),
                ];

                for candidate in candidates {
                    if candidate.exists() {
                        let parent = candidate.parent().map(|p| p.to_path_buf());
                        return Ok((candidate.to_string_lossy().to_string(), vec![], parent));
                    }
                }
            }
        }

        // 3. Check ~/.local/share/desktop-pet/
        if let Ok(home) = env::var("HOME") {
            let installed_dir = PathBuf::from(&home).join(".local/share/desktop-pet");
            let candidates = [
                installed_dir.join("bin/pet-brain"),
                installed_dir.join("pet-brain"),
                installed_dir.join("pet-brain/main.py"),
            ];

            for candidate in candidates {
                if candidate.exists() {
                    if candidate.extension().map_or(false, |ext| ext == "py") {
                        // Launch via python
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
        // Check for venv inside or near the directory
        let venv_candidates = [
            base_dir.join(".venv/bin/python"),
            base_dir.join("venv/bin/python"),
            base_dir.join("../.venv/bin/python"),
        ];

        for venv in venv_candidates {
            if venv.exists() {
                return venv.to_string_lossy().to_string();
            }
        }

        // Check conda env if active
        if let Ok(conda_prefix) = env::var("CONDA_PREFIX") {
            let conda_python = PathBuf::from(conda_prefix).join("bin/python");
            if conda_python.exists() {
                return conda_python.to_string_lossy().to_string();
            }
        }

        // Default to system python3
        "python3".to_string()
    }
}

impl Drop for SidecarSupervisor {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
    }
}
