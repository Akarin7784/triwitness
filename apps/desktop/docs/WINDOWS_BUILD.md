# Windows 构建步骤

## 方式 A：在 Windows 本机构建（推荐，最稳）

1. 安装 [Node.js 20+](https://nodejs.org/)
2. 安装 [Rust](https://rustup.rs/)（默认的 MSVC 工具链）
3. 安装 **Visual Studio 2022 Build Tools**，勾选“使用 C++ 的桌面开发”
4. WebView2：Windows 10/11 一般已经自带。没有的话，到 [微软官网](https://developer.microsoft.com/microsoft-edge/webview2/) 下载 Evergreen 运行时
5. 在仓库里执行：
   ```powershell
   cd apps\desktop
   npm ci
   npm run tauri:dev      # 开发窗口，支持热更新
   npm run tauri:build    # 产出安装包
   ```
6. 安装包位置：
   - `src-tauri\target\release\bundle\nsis\TriWitness_0.1.0_x64-setup.exe`
   - `src-tauri\target\release\bundle\msi\TriWitness_0.1.0_x64_en-US.msi`

## 方式 B：在 Linux 交叉编译（实验性，只能出 NSIS 包）

```bash
sudo apt-get install -y clang lld llvm nsis
curl -sSf https://sh.rustup.rs | sh -s -- -y
rustup target add x86_64-pc-windows-msvc
cargo install cargo-xwin --locked
cd apps/desktop && npm ci
npx tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --bundles nsis
# → src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/TriWitness_0.1.0_x64-setup.exe
```

注意：
- 第一次运行时，cargo-xwin 会下载微软 CRT 和 Windows SDK 的头文件与库，约几百 MB，下载即视为接受微软的许可条款
- 交叉编译出的安装包**没有代码签名**，第一次运行时 SmartScreen 会弹出提示，选“仍要运行”即可
- 字体已经打包进前端产物，离线也能正常显示
