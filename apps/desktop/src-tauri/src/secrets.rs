//! UI-21：DeepSeek API 密钥存系统凭据库（Windows 凭据管理器 / macOS 钥匙串 / Linux 密钥环）。
//! 前端只能写入、清除、查询“是否已设置”；明文永不回传前端。真实模式启动核心时注入子进程环境变量。

const SERVICE: &str = "triwitness";
const ACCOUNT: &str = "deepseek-api-key";

fn entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|e| e.to_string())
}

/// 形状检查：去空白、长度 16–200、只含可见 ASCII（不校验真伪，不联网）
pub fn normalize_key(raw: &str) -> Option<String> {
    let k = raw.trim();
    if k.len() < 16 || k.len() > 200 || !k.chars().all(|c| c.is_ascii_graphic()) {
        return None;
    }
    Some(k.to_string())
}

/// 读出密钥（只在 Rust 侧使用，给子进程注入环境变量）
pub fn read_key() -> Option<String> {
    entry().ok()?.get_password().ok().filter(|k| !k.is_empty())
}

#[tauri::command]
pub fn secret_status() -> bool {
    read_key().is_some()
}

#[tauri::command]
pub fn secret_set(value: String) -> Result<(), String> {
    let k = normalize_key(&value).ok_or("密钥格式不对")?;
    entry()?.set_password(&k).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn secret_clear() -> Result<(), String> {
    match entry()?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn key_shape() {
        assert_eq!(normalize_key("  sk-abcdefghijklmnop  ").as_deref(), Some("sk-abcdefghijklmnop"));
        assert!(normalize_key("short").is_none());
        assert!(normalize_key("sk-abc defghijklmnopq").is_none());
        assert!(normalize_key("sk-中文中文中文中文中文").is_none());
    }
}
