#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            #[cfg(windows)]
            harden_webview2(app);
            #[cfg(not(windows))]
            let _ = app;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running TriWitness");
}

/// 让 WebView2 表现得像桌面应用而不是浏览器：
/// - 关闭默认右键菜单（前端另有自绘菜单）
/// - release 下关闭浏览器快捷键（F5/Ctrl+R 刷新、Ctrl+P 打印、Ctrl+F 查找、
///   Ctrl+U、F7 光标浏览、F12/Ctrl+Shift+I 开发者工具等），复制粘贴等编辑键不受影响
/// - 关闭左下角链接状态栏、表单自动填充/密码保存、触摸板左右滑动前进后退
#[cfg(windows)]
fn harden_webview2(app: &tauri::App) {
    use tauri::Manager;
    #[cfg_attr(debug_assertions, allow(unused_imports))]
    use webview2_com::Microsoft::Web::WebView2::Win32::{
        ICoreWebView2Settings3, ICoreWebView2Settings4, ICoreWebView2Settings6,
    };
    use windows_core::Interface;

    let Some(win) = app.get_webview_window("main") else { return };
    let _ = win.with_webview(|pv| unsafe {
        let Ok(core) = pv.controller().CoreWebView2() else { return };
        let Ok(settings) = core.Settings() else { return };

        let _ = settings.SetAreDefaultContextMenusEnabled(false);
        let _ = settings.SetIsStatusBarEnabled(false);

        #[cfg(not(debug_assertions))]
        if let Ok(s3) = settings.cast::<ICoreWebView2Settings3>() {
            let _ = s3.SetAreBrowserAcceleratorKeysEnabled(false);
        }

        if let Ok(s4) = settings.cast::<ICoreWebView2Settings4>() {
            let _ = s4.SetIsGeneralAutofillEnabled(false);
            let _ = s4.SetIsPasswordAutosaveEnabled(false);
        }
        if let Ok(s6) = settings.cast::<ICoreWebView2Settings6>() {
            let _ = s6.SetIsSwipeNavigationEnabled(false);
        }
    });
}
