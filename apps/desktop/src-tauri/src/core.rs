//! UI-10：Python 核心桥（tw-bridge/1）。启动 `tw run --jsonl` 子进程，stdout 逐行转发为
//! `tw://line` 事件，stdin 收审批 / 取消命令；进程退出发 `tw://exit`。
//!
//! 核心命令解析：环境变量 `TW_CORE`（JSON 数组，如 `["uv","run","--project","C:/src/triwitness","tw"]`）
//! → `tw` → `python -m triwitness`（Windows 再试 `py -3 -m triwitness`）。

use serde::{Deserialize, Serialize};
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

/// 本次任务的选择（输入框 + 设置页）：只放行白名单，其余一律丢弃（核心那边还会再拒一次）
#[derive(Default, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Choices {
    pub model: Option<String>,
    pub thinking: Option<String>,
    pub backend: Option<String>,
    pub max_cost: Option<f64>,
    pub permission_mode: Option<String>,
    pub confirm_unrestricted: Option<String>,
    pub allow_peak: Option<bool>,
    /// `attach_save` 返回的路径（只接受 `<tw_home>/attachments/` 之内）
    pub attachments: Option<Vec<String>>,
    /// 个人偏好 + 风格 + 项目说明（纯文本，写成临时文件交给 --guidance-file）
    pub guidance: Option<String>,
}

pub const UNRESTRICTED_PHRASE: &str = "我了解风险";
/// 与 core `Budget.for_run()` 一致：设置页只能调低
pub const MAX_COST_CAP: f64 = 1.0;

pub fn choice_args(c: &Choices) -> Vec<String> {
    let mut a: Vec<String> = Vec::new();
    let mut push = |k: &str, v: &str| {
        a.push(k.to_string());
        a.push(v.to_string());
    };
    if let Some(m) = c.model.as_deref().filter(|m| *m == "deepseek-flash") {
        push("--model", m);
    }
    if let Some(t) = c.thinking.as_deref().filter(|t| matches!(*t, "off" | "low" | "medium" | "high")) {
        push("--thinking", t);
    }
    if let Some(b) = c.backend.as_deref().filter(|b| matches!(*b, "auto" | "docker" | "none")) {
        push("--backend", b);
    }
    if let Some(x) = c.max_cost.filter(|x| x.is_finite() && *x > 0.0 && *x <= MAX_COST_CAP) {
        push("--max-cost", &format!("{x:.2}"));
    }
    match c.permission_mode.as_deref() {
        Some(m @ ("plan" | "ask" | "auto_edit" | "auto" | "full_access")) => push("--permission-mode", m),
        Some("unrestricted") if c.confirm_unrestricted.as_deref() == Some(UNRESTRICTED_PHRASE) => {
            push("--permission-mode", "unrestricted");
            push("--confirm-unrestricted", UNRESTRICTED_PHRASE);
        }
        _ => {}
    }
    if c.allow_peak == Some(true) {
        a.push("--allow-peak".to_string());
    }
    a
}

/// 附件 / 用户说明 → `--attach` / `--guidance-file`；不在附件目录内的路径直接丢弃
pub fn input_args(home: &std::path::Path, c: &Choices, guidance_file: Option<&str>) -> Vec<String> {
    let mut a = Vec::new();
    for p in c.attachments.iter().flatten().take(20) {
        if crate::files::attachment_ok(home, p) {
            a.push("--attach".to_string());
            a.push(p.clone());
        }
    }
    if let Some(g) = guidance_file {
        a.push("--guidance-file".into());
        a.push(g.to_string());
    }
    a
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

fn spawn(prefix: &[String], args: &[String], api_key: Option<&str>) -> std::io::Result<Child> {
    let mut cmd = Command::new(&prefix[0]);
    if let Some(k) = api_key {
        cmd.env("DEEPSEEK_API_KEY", k); // 只进子进程环境，不写盘、不回传前端
    }
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
    choices: Option<Choices>,
) -> Result<String, String> {
    if repo.trim().is_empty() {
        return Err("缺少仓库路径".into());
    }
    if !matches!(mode.as_str(), "demo" | "replay" | "live") {
        return Err(format!("未知运行方式：{mode}"));
    }
    let mut args = run_args(repo.trim(), &issue, &mode);
    let choices = choices.unwrap_or_default();
    args.extend(choice_args(&choices));
    let home = crate::files::tw_home();
    let guidance_file = match choices.guidance.as_deref().map(str::trim).filter(|g| !g.is_empty()) {
        Some(g) => {
            let dir = home.join("attachments").join("guidance");
            std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            let f = dir.join(format!("g{}-{}.md", std::process::id(), state.next.load(Ordering::Relaxed)));
            std::fs::write(&f, g.chars().take(8000).collect::<String>()).map_err(|e| e.to_string())?;
            Some(f.to_string_lossy().to_string())
        }
        None => None,
    };
    args.extend(input_args(&home, &choices, guidance_file.as_deref()));
    // 真实模式：凭据库里有密钥就注入；没有则沿用环境变量 DEEPSEEK_API_KEY
    let api_key = if mode == "live" { crate::secrets::read_key() } else { None };
    let tw_core = std::env::var("TW_CORE").ok();
    let mut last_err = String::from("找不到核心命令");
    let mut child = None;
    for prefix in core_candidates(tw_core.as_deref()) {
        match spawn(&prefix, &args, api_key.as_deref()) {
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
    fn choices_are_whitelisted() {
        let s = |v: &str| Some(v.to_string());
        let ok = Choices { model: s("deepseek-flash"), thinking: s("high"), backend: s("none"), max_cost: Some(0.5),
                           permission_mode: s("ask"), allow_peak: Some(true), ..Default::default() };
        assert_eq!(choice_args(&ok), ["--model", "deepseek-flash", "--thinking", "high", "--backend", "none",
                                      "--max-cost", "0.50", "--permission-mode", "ask", "--allow-peak"]);
        let bad = Choices { model: s("deepseek-v4-pro"), thinking: s("ultra"), backend: s("vm"), max_cost: Some(9.0),
                            permission_mode: s("unrestricted"), confirm_unrestricted: s("ok"), allow_peak: Some(false),
                            ..Default::default() };
        assert!(choice_args(&bad).is_empty());
        assert!(choice_args(&Choices { max_cost: Some(f64::NAN), ..Default::default() }).is_empty());
        let warrior = Choices { permission_mode: s("unrestricted"), confirm_unrestricted: s(UNRESTRICTED_PHRASE), ..Default::default() };
        assert_eq!(choice_args(&warrior), ["--permission-mode", "unrestricted", "--confirm-unrestricted", UNRESTRICTED_PHRASE]);
        let parsed: Choices = serde_json::from_str(r#"{"maxCost":0.3,"permissionMode":"plan"}"#).unwrap();
        assert_eq!(choice_args(&parsed), ["--max-cost", "0.30", "--permission-mode", "plan"]);
    }

    #[test]
    fn inputs_only_from_attachment_folder() {
        let home = std::env::temp_dir().join(format!("tw-inputs-{}", std::process::id()));
        let ok = crate::files::save_attachment(&home, "a.md", b"x").unwrap();
        let c: Choices = serde_json::from_value(serde_json::json!({
            "attachments": [serde_json::to_value(&ok).unwrap()["path"], "/etc/passwd"], "guidance": "g"
        })).unwrap();
        let a = input_args(&home, &c, Some("G.md"));
        assert_eq!(a.len(), 4);
        assert_eq!((a[0].as_str(), a[2].as_str(), a[3].as_str()), ("--attach", "--guidance-file", "G.md"));
        std::fs::remove_dir_all(&home).unwrap();
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
