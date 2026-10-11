//! UI-21：DeepSeek API 密钥存系统凭据库（Windows 凭据管理器 / macOS 钥匙串 / Linux 密钥环）。
//! v1.0：GitHub 令牌（开 PR 用）同样存这里（kind = "github"）。
//! 前端只能写入、清除、查询“是否已设置”；明文永不回传前端。只在启动核心子进程时注入它的环境变量。

const SERVICE: &str = "triwitness";
const ACCOUNT: &str = "deepseek-api-key";
const GITHUB_ACCOUNT: &str = "github-token";

/// 前端传来的 kind → 凭据库账户名；未知值一律拒绝（缺省 = DeepSeek，兼容 0.3.1 前端）
fn account(kind: Option<&str>) -> Result<&'static str, String> {
    match kind {
        None | Some("deepseek") => Ok(ACCOUNT),
        Some("github") => Ok(GITHUB_ACCOUNT),
        Some(_) => Err("未知的密钥类型".into()),
    }
}

fn entry_for(acct: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, acct).map_err(|e| e.to_string())
}

fn entry() -> Result<keyring::Entry, String> {
    entry_for(ACCOUNT)
}

/// GitHub 令牌（只在 Rust 侧使用：`tw pr …` 子进程的 GITHUB_TOKEN）
pub fn read_github_token() -> Option<String> {
    entry_for(GITHUB_ACCOUNT).ok()?.get_password().ok().filter(|k| !k.is_empty())
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
pub fn secret_status(kind: Option<String>) -> bool {
    account(kind.as_deref()).ok().and_then(|a| entry_for(a).ok()?.get_password().ok()).is_some_and(|k| !k.is_empty())
}

#[tauri::command]
pub fn secret_set(value: String, kind: Option<String>) -> Result<(), String> {
    let acct = account(kind.as_deref())?;
    let k = normalize_key(&value).ok_or("密钥格式不对")?;
    entry_for(acct)?.set_password(&k).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn secret_clear(kind: Option<String>) -> Result<(), String> {
    match entry_for(account(kind.as_deref())?)?.delete_credential() {
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
        assert!(normalize_key("github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz").is_some());
    }

    #[test]
    fn kinds_are_whitelisted() {
        assert_eq!(account(None).unwrap(), ACCOUNT);
        assert_eq!(account(Some("deepseek")).unwrap(), ACCOUNT);
        assert_eq!(account(Some("github")).unwrap(), GITHUB_ACCOUNT);
        assert!(account(Some("../x")).is_err());
    }
}
