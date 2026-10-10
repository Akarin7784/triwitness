//! UI-10：Python 核心桥（tw-bridge/1）。启动 `tw run --jsonl` 子进程，stdout 逐行转发为
//! `tw://line` 事件，stdin 收审批 / 取消命令；进程退出发 `tw://exit`。
//!
//! 核心命令解析：环境变量 `TW_CORE`（JSON 数组，如 `["uv","run","--project","C:/src/triwitness","tw"]`）
//! → `tw` → `python -m triwitness`（Windows 再试 `py -3 -m triwitness`）。

use serde::Serialize;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter, State};

#[derive(Default)]
pub struct CoreState {
    tasks: Mutex<HashMap<String, Task>>,
    next: AtomicU64,
}

struct Task {
    stdin: Option<ChildStdin>,
    child: Arc<Mutex<Child>>,
}

#[derive(Clone, Serialize)]
struct LineEvent {
    key: String,
    line: String,
}

#[derive(Clone, Serialize)]
struct ExitEvent {
    key: String,
    code: Option<i32>,
}

/// 组装 `tw run` 参数（纯函数，便于单测）
pub fn run_args(repo: &str, issue: &str, mode: &str) -> Vec<String> {
    let mut a = vec!["run".to_string(), "--jsonl".into(), "--repo".into(), repo.to_string()];
    if !issue.trim().is_empty() {
        a.push("--issue".into());
        a.push(issue.to_string());
    }
    match mode {
        "demo" => a.push("--demo".into()),
        "live" => a.push("--live".into()),
        _ => {} // replay：默认只回放
    }
    a
}

/// 候选核心命令：TW_CORE（JSON 数组）优先，否则 tw → python -m triwitness
pub fn core_candidates(tw_core: Option<&str>) -> Vec<Vec<String>> {
    if let Some(raw) = tw_core {
        if let Ok(v) = serde_json::from_str::<Vec<String>>(raw) {
            if !v.is_empty() {
                return vec![v];
            }
        }
    }
    let mut c = vec![vec!["tw".to_string()]];
    if cfg!(windows) {
        c.push(vec!["py".into(), "-3".into(), "-m".into(), "triwitness".into()]);
    }
    c.push(vec!["python".into(), "-m".into(), "triwitness".into()]);
    c.push(vec!["python3".into(), "-m".into(), "triwitness".into()]);
    c
}

fn spawn(prefix: &[String], args: &[String]) -> std::io::Result<Child> {
    let mut cmd = Command::new(&prefix[0]);
    cmd.args(&prefix[1..])
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8");
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

#[tauri::command]
pub fn core_start(
    app: AppHandle,
    state: State<'_, CoreState>,
    repo: String,
    issue: String,
    mode: String,
) -> Result<String, String> {
    if repo.trim().is_empty() {
        return Err("缺少仓库路径".into());
    }
    if !matches!(mode.as_str(), "demo" | "replay" | "live") {
        return Err(format!("未知运行方式：{mode}"));
    }
    let args = run_args(repo.trim(), &issue, &mode);
    let tw_core = std::env::var("TW_CORE").ok();
    let mut last_err = String::from("找不到核心命令");
    let mut child = None;
    for prefix in core_candidates(tw_core.as_deref()) {
        match spawn(&prefix, &args) {
            Ok(c) => {
                child = Some(c);
                break;
            }
            Err(e) => last_err = format!("{}：{e}", prefix.join(" ")),
        }
    }
    let mut child = child.ok_or(last_err)?;
    let key = format!("k{}", state.next.fetch_add(1, Ordering::Relaxed));
    let stdout = child.stdout.take().ok_or("无法读取核心输出")?;
    let stderr = child.stderr.take();
    let stdin = child.stdin.take();
    let child = Arc::new(Mutex::new(child));
    state.tasks.lock().map_err(|e| e.to_string())?.insert(
        key.clone(),
        Task { stdin, child: child.clone() },
    );

    if let Some(err) = stderr {
        // 人读日志：读掉，避免管道写满阻塞子进程
        thread::spawn(move || for _ in BufReader::new(err).lines() {});
    }
    let k = key.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    let _ = app.emit("tw://line", LineEvent { key: k.clone(), line });
                }
                Ok(_) => {}
                Err(_) => break,
            }
        }
        let code = child.lock().ok().and_then(|mut c| c.wait().ok()).and_then(|s| s.code());
        let _ = app.emit("tw://exit", ExitEvent { key: k, code });
    });
    Ok(key)
}

fn write_line(state: &State<'_, CoreState>, key: &str, line: &str) -> Result<(), String> {
    let mut tasks = state.tasks.lock().map_err(|e| e.to_string())?;
    let task = tasks.get_mut(key).ok_or("任务已结束")?;
    let stdin = task.stdin.as_mut().ok_or("任务已结束")?;
    stdin
        .write_all(format!("{}\n", line.trim()).as_bytes())
        .and_then(|_| stdin.flush())
        .map_err(|e| e.to_string())
}

/// 审批决定等命令：一行 JSON（前端拼好，这里只校验是 JSON 对象）
#[tauri::command]
pub fn core_send(state: State<'_, CoreState>, key: String, line: String) -> Result<(), String> {
    match serde_json::from_str::<serde_json::Value>(&line) {
        Ok(v) if v.is_object() => write_line(&state, &key, &line),
        _ => Err("命令必须是 JSON 对象".into()),
    }
}

/// 取消：先请核心自己收尾（写 cancelled 事件、保留分支），10 秒后仍在就强制结束
#[tauri::command]
pub fn core_cancel(state: State<'_, CoreState>, key: String) -> Result<(), String> {
    let _ = write_line(&state, &key, r#"{"cmd":"cancel"}"#);
    let child = state
        .tasks
        .lock()
        .map_err(|e| e.to_string())?
        .get(&key)
        .map(|t| t.child.clone())
        .ok_or("任务已结束")?;
    thread::spawn(move || {
        thread::sleep(Duration::from_secs(10));
        if let Ok(mut c) = child.lock() {
            if matches!(c.try_wait(), Ok(None)) {
                let _ = c.kill();
            }
        }
    });
    Ok(())
}

/// 续传：读 `<run_dir>/trajectory.jsonl` 里 seq > after_seq 的行（应用重开 / 重新进入任务时补齐）
#[tauri::command]
pub fn core_read_run(run_dir: String, after_seq: i64) -> Result<Vec<String>, String> {
    read_run(&PathBuf::from(run_dir), after_seq)
}

pub fn read_run(run_dir: &std::path::Path, after_seq: i64) -> Result<Vec<String>, String> {
    let path = run_dir.join("trajectory.jsonl");
    let text = std::fs::read_to_string(&path).map_err(|e| format!("{}：{e}", path.display()))?;
    Ok(text
        .lines()
        .filter(|l| {
            serde_json::from_str::<serde_json::Value>(l)
                .ok()
                .and_then(|v| v.get("seq").and_then(|s| s.as_i64()))
                .is_some_and(|s| s > after_seq)
        })
        .map(str::to_string)
        .collect())
}

/// 任务进程是否还在
#[tauri::command]
pub fn core_alive(state: State<'_, CoreState>, key: String) -> bool {
    let tasks = match state.tasks.lock() {
        Ok(t) => t,
        Err(_) => return false,
    };
    tasks
        .get(&key)
        .and_then(|t| t.child.lock().ok().map(|mut c| matches!(c.try_wait(), Ok(None))))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn args_by_mode() {
        assert_eq!(run_args("C:/r", "修", "demo"), ["run", "--jsonl", "--repo", "C:/r", "--issue", "修", "--demo"]);
        assert_eq!(run_args("/r", "  ", "live"), ["run", "--jsonl", "--repo", "/r", "--live"]);
        assert_eq!(run_args("/r", "x", "replay"), ["run", "--jsonl", "--repo", "/r", "--issue", "x"]);
    }

    #[test]
    fn core_override_and_fallbacks() {
        let c = core_candidates(Some(r#"["uv","run","tw"]"#));
        assert_eq!(c, vec![vec!["uv", "run", "tw"]]);
        let d = core_candidates(Some("not json"));
        assert_eq!(d[0], vec!["tw"]);
        assert!(d.iter().any(|p| p.join(" ") == "python -m triwitness"));
    }

    #[test]
    fn read_run_filters_by_seq() {
        let dir = std::env::temp_dir().join(format!("tw-read-run-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("trajectory.jsonl"), "{\"seq\":0}\n{\"seq\":1}\nbad\n{\"seq\":2}\n").unwrap();
        assert_eq!(read_run(&dir, 0).unwrap(), vec!["{\"seq\":1}", "{\"seq\":2}"]);
        assert_eq!(read_run(&dir, -1).unwrap().len(), 3);
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
