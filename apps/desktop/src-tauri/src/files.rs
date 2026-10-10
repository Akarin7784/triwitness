//! UI-21 第 3 轮：附件落盘、导出 / 下载、读取任务产物、调用核心的只读 / 受控子命令。
//!
//! 安全边界：
//! - 附件只能写进 `<tw_home>/attachments/<随机目录>/`，文件名清洗，单个 ≤ 10 MiB
//! - `core_start` 只接受这个目录下的附件路径
//! - 产物只读 `<tw_home>/runs/<run_id>/` 下的白名单文件
//! - `core_tool` 只放行固定的几个子命令及其选项（`tool_args_ok`）

use base64::Engine;
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

pub const MAX_ATTACH_BYTES: usize = 10 * 1024 * 1024;
pub const ARTIFACTS: [&str; 5] = ["patch.diff", "pr.md", "cost.md", "finish.json", "summary.json"];

pub fn tw_home() -> PathBuf {
    if let Ok(h) = std::env::var("TW_HOME") {
        if !h.trim().is_empty() {
            return PathBuf::from(h);
        }
    }
    dirs::home_dir().unwrap_or_else(std::env::temp_dir).join(".triwitness")
}

/// 文件名清洗：去掉路径分隔、控制字符和 Windows 保留字符，限长；空了就用 file
pub fn clean_name(name: &str) -> String {
    let base = name.rsplit(['/', '\\']).next().unwrap_or("");
    let mut s: String = base
        .chars()
        .map(|c| if c.is_control() || "<>:\"|?*".contains(c) { '_' } else { c })
        .collect();
    s = s.trim().trim_matches('.').to_string();
    if s.chars().count() > 120 {
        let ext = Path::new(&s).extension().map(|e| e.to_string_lossy().to_string());
        let stem: String = s.chars().take(100).collect();
        s = match ext {
            Some(e) if e.len() <= 10 => format!("{stem}.{e}"),
            _ => stem,
        };
    }
    let upper = s.split('.').next().unwrap_or("").to_ascii_uppercase();
    let reserved = ["CON", "PRN", "AUX", "NUL"].contains(&upper.as_str())
        || ((upper.starts_with("COM") || upper.starts_with("LPT")) && upper.len() == 4);
    if s.is_empty() || reserved {
        format!("file{}", if s.is_empty() { String::new() } else { format!("_{s}") })
    } else {
        s
    }
}

fn stamp() -> String {
    let d = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    format!("{}-{:06}", d.as_secs(), d.subsec_micros())
}

/// 附件路径必须在 `<home>/attachments/` 之内（规范化后比较，防 `..` 逃逸）
pub fn attachment_ok(home: &Path, p: &str) -> bool {
    let root = match home.join("attachments").canonicalize() {
        Ok(r) => r,
        Err(_) => return false,
    };
    match Path::new(p).canonicalize() {
        Ok(f) => f.starts_with(&root) && f.is_file(),
        Err(_) => false,
    }
}

#[derive(Serialize)]
pub struct Saved {
    path: String,
    name: String,
    size: usize,
}

fn decode(data_b64: &str) -> Result<Vec<u8>, String> {
    base64::engine::general_purpose::STANDARD.decode(data_b64.trim()).map_err(|e| format!("数据损坏：{e}"))
}

pub fn save_attachment(home: &Path, name: &str, bytes: &[u8]) -> Result<Saved, String> {
    if bytes.len() > MAX_ATTACH_BYTES {
        return Err("附件超过 10 MB".into());
    }
    let n = clean_name(name);
    let dir = home.join("attachments").join(stamp());
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join(&n);
    std::fs::write(&path, bytes).map_err(|e| e.to_string())?;
    Ok(Saved { path: path.to_string_lossy().to_string(), name: n, size: bytes.len() })
}

#[tauri::command]
pub fn attach_save(name: String, data_b64: String) -> Result<Saved, String> {
    save_attachment(&tw_home(), &name, &decode(&data_b64)?)
}

/// 不覆盖：同名时加 (1)、(2)…
pub fn unique_path(dir: &Path, name: &str) -> PathBuf {
    let p = dir.join(name);
    if !p.exists() {
        return p;
    }
    let path = Path::new(name);
    let stem = path.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
    let ext = path.extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
    (1..1000).map(|i| dir.join(format!("{stem} ({i}){ext}"))).find(|p| !p.exists()).unwrap_or(p)
}

/// 导出 / 下载：写到“下载”文件夹，返回完整路径
#[tauri::command]
pub fn save_download(name: String, data_b64: String) -> Result<String, String> {
    let bytes = decode(&data_b64)?;
    let dir = dirs::download_dir().or_else(dirs::home_dir).ok_or("找不到下载文件夹")?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let p = unique_path(&dir, &clean_name(&name));
    std::fs::write(&p, bytes).map_err(|e| e.to_string())?;
    Ok(p.to_string_lossy().to_string())
}

pub fn read_artifact(home: &Path, run_dir: &str, name: &str) -> Result<Option<String>, String> {
    if !ARTIFACTS.contains(&name) {
        return Err("不允许读取该文件".into());
    }
    let runs = home.join("runs").canonicalize().map_err(|e| e.to_string())?;
    let dir = Path::new(run_dir).canonicalize().map_err(|e| e.to_string())?;
    if !dir.starts_with(&runs) {
        return Err("不在任务目录内".into());
    }
    let p = dir.join(name);
    if !p.is_file() {
        return Ok(None);
    }
    std::fs::read_to_string(&p).map(Some).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn core_read_artifact(run_dir: String, name: String) -> Result<Option<String>, String> {
    read_artifact(&tw_home(), &run_dir, &name)
}

fn opt_pairs<'a>(rest: &'a [String], allowed: &[&str]) -> Option<Vec<(&'a str, &'a str)>> {
    if rest.len() % 2 != 0 {
        return None;
    }
    let mut seen = Vec::new();
    for pair in rest.chunks(2) {
        let (k, v) = (pair[0].as_str(), pair[1].as_str());
        if !allowed.contains(&k) || seen.iter().any(|(s, _)| *s == k) || v.starts_with("--") {
            return None;
        }
        seen.push((k, v));
    }
    Some(seen)
}

/// `core_tool` 白名单：只读自检、受控安装（--plan / --yes 由前端在用户确认后才传）、规则编辑
pub fn tool_args_ok(a: &[String]) -> bool {
    let s: Vec<&str> = a.iter().map(String::as_str).collect();
    match s.as_slice() {
        ["doctor", "--json"] => true,
        ["sandbox", "install", "docker" | "wsl", "--plan" | "--yes"] => true,
        ["permissions", "list", ..] => opt_pairs(&a[2..], &["--repo"]).is_some(),
        ["permissions", "validate", ..] => opt_pairs(&a[2..], &["--kind", "--rule"]).is_some_and(|p| p.len() == 2),
        ["permissions", sub @ ("add" | "remove"), ..] => {
            let allowed: &[&str] = if *sub == "add" {
                &["--kind", "--rule", "--layer", "--repo", "--replace"]
            } else {
                &["--kind", "--rule", "--layer", "--repo"]
            };
            opt_pairs(&a[2..], allowed).is_some_and(|p| {
                p.iter().any(|(k, _)| *k == "--kind")
                    && p.iter().any(|(k, _)| *k == "--rule")
                    && p.iter().all(|(k, v)| match *k {
                        "--kind" => matches!(*v, "allow" | "ask" | "deny"),
                        "--layer" => matches!(*v, "user" | "local"),
                        _ => true,
                    })
            })
        }
        _ => false,
    }
}

#[derive(Serialize)]
pub struct ToolOut {
    code: Option<i32>,
    stdout: String,
    stderr: String,
}

#[tauri::command(async)]
pub fn core_tool(args: Vec<String>) -> Result<ToolOut, String> {
    if !tool_args_ok(&args) {
        return Err("不允许的核心命令".into());
    }
    let tw_core = std::env::var("TW_CORE").ok();
    let mut last = String::from("找不到核心命令");
    for prefix in crate::core::core_candidates(tw_core.as_deref()) {
        let mut cmd = Command::new(&prefix[0]);
        cmd.args(&prefix[1..])
            .args(&args)
            .stdin(Stdio::null())
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8");
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000);
        }
        match cmd.output() {
            Ok(o) => {
                return Ok(ToolOut {
                    code: o.status.code(),
                    stdout: String::from_utf8_lossy(&o.stdout).to_string(),
                    stderr: String::from_utf8_lossy(&o.stderr).chars().rev().take(2000).collect::<String>().chars().rev().collect(),
                })
            }
            Err(e) => last = format!("{}：{e}", prefix.join(" ")),
        }
    }
    Err(last)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn names_are_cleaned() {
        assert_eq!(clean_name("../../etc/passwd"), "passwd");
        assert_eq!(clean_name("C:\\Users\\a\\报告?.md"), "报告_.md");
        assert_eq!(clean_name("CON.txt"), "file_CON.txt");
        assert_eq!(clean_name("..."), "file");
        assert!(clean_name(&format!("{}.png", "长".repeat(300))).ends_with(".png"));
    }

    #[test]
    fn attachments_stay_in_their_folder() {
        let home = std::env::temp_dir().join(format!("tw-files-{}", std::process::id()));
        let s = save_attachment(&home, "a/b.txt", b"hi").unwrap();
        assert!(attachment_ok(&home, &s.path));
        let outside = home.join("x.txt");
        std::fs::write(&outside, "x").unwrap();
        assert!(!attachment_ok(&home, outside.to_str().unwrap()));
        let sneaky = format!("{}/../../x.txt", s.path);
        assert!(!attachment_ok(&home, &sneaky));
        assert!(save_attachment(&home, "big", &vec![0u8; MAX_ATTACH_BYTES + 1]).is_err());
        std::fs::create_dir_all(home.join("runs/r1")).unwrap();
        std::fs::write(home.join("runs/r1/pr.md"), "# PR").unwrap();
        let rd = home.join("runs/r1");
        assert_eq!(read_artifact(&home, rd.to_str().unwrap(), "pr.md").unwrap().as_deref(), Some("# PR"));
        assert!(read_artifact(&home, rd.to_str().unwrap(), "trajectory.jsonl").is_err());
        assert!(read_artifact(&home, home.to_str().unwrap(), "pr.md").is_err());
        assert_eq!(read_artifact(&home, rd.to_str().unwrap(), "patch.diff").unwrap(), None);
        let p = unique_path(&home, "x.txt");
        assert!(p.ends_with("x (1).txt"));
        std::fs::remove_dir_all(&home).unwrap();
    }

    #[test]
    fn tool_whitelist() {
        assert!(tool_args_ok(&v(&["doctor", "--json"])));
        assert!(tool_args_ok(&v(&["sandbox", "install", "wsl", "--yes"])));
        assert!(!tool_args_ok(&v(&["sandbox", "install", "kernel", "--yes"])));
        assert!(!tool_args_ok(&v(&["run", "--repo", "x"])));
        assert!(tool_args_ok(&v(&["permissions", "list"])));
        assert!(tool_args_ok(&v(&["permissions", "list", "--repo", "C:/r"])));
        assert!(tool_args_ok(&v(&["permissions", "validate", "--kind", "allow", "--rule", "Bash(ls)"])));
        assert!(tool_args_ok(&v(&["permissions", "add", "--kind", "deny", "--rule", "Read(.env)", "--replace", "x"])));
        assert!(!tool_args_ok(&v(&["permissions", "remove", "--kind", "deny", "--rule", "x", "--replace", "y"])));
        assert!(!tool_args_ok(&v(&["permissions", "add", "--kind", "god", "--rule", "x"])));
        assert!(!tool_args_ok(&v(&["permissions", "add", "--rule", "x"])));
        assert!(!tool_args_ok(&v(&["permissions", "add", "--kind", "allow", "--rule", "--live"])));
        assert!(!tool_args_ok(&v(&["permissions", "add", "--kind", "allow", "--kind", "deny", "--rule", "x"])));
    }
}
