"""把 Python 核心打成 PyInstaller **onedir** 目录（tw / tw.exe + _internal/），供桌面安装包内置。

用法（在仓库根）：
    uv sync --locked --no-dev --group package
    uv run --no-dev --group package python packaging/core/build_core.py [--out apps/desktop/src-tauri/resources/core]

为什么 onedir 而不是 onefile：
- onefile 每次启动都要把 ~40 MB 解压到临时目录再运行，桌面端每起一个任务、每查一次规则 / 账本都会启动一次核心，
  冷启动多 1–3 秒，而且杀毒软件会反复扫描临时目录里的新文件；
- onedir 由安装器一次性装好，启动只是加载已在磁盘上的文件（实测 Linux 上 `tw --version` 约 0.1–0.5 s），
  也便于以后逐个文件签名。
PyInstaller 不能交叉编译：Windows 的 tw.exe 只能在 Windows 上构建（CI：.github/workflows/package-windows.yml）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEP = ";" if sys.platform == "win32" else ":"

# 开发 / 测试依赖和用不到的大模块：不进安装包
# 0.3.1 起正式版不含演示 / 假模型 / 测试辅助：只在源码（开发 / 测试）里有
DEV_ONLY = [
    "triwitness.bridge.demo",
    "triwitness.harness.testing",
    "triwitness.verify.testing",
    "triwitness.llm.fake",
]
EXCLUDES = [
    *DEV_ONLY,
    "tkinter",
    "_tkinter",
    "pytest",
    "_pytest",
    "pyright",
    "ruff",
    "jsonschema",
    "IPython",
    "matplotlib",
    "numpy",
    "setuptools",
    "pip",
    "PyInstaller",
    "lib2to3",
    "pydoc_data",
    "test",
    "idlelib",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "apps" / "desktop" / "src-tauri" / "resources" / "core"))
    ns = ap.parse_args()
    out = Path(ns.out)
    work = ROOT / "build" / "pyinstaller"
    import PyInstaller.__main__ as pyi

    args = [
        str(Path(__file__).with_name("tw_entry.py")),
        "--name", "tw",
        "--onedir",
        "--console",  # 桌面端经管道读写 stdio，并以 CREATE_NO_WINDOW 启动，不会弹窗
        "--noconfirm",
        "--clean",
        "--noupx",
        # Windows 控制台默认 cp936/cp1252：冻结后的解释器不一定读 PYTHONUTF8，直接打开 UTF-8 模式
        "--python-option",
        "X utf8",
        "--distpath", str(work / "dist"),
        "--workpath", str(work / "build"),
        "--specpath", str(work),
        "--add-data", f"{ROOT / 'configs'}{SEP}configs",
        "--collect-data", "triwitness",  # prompts/*.md、tools/descriptions/*.md
        # 出网网关源码要原样拷进网关容器（sandbox/egress.py），冻结包里没有 .py，单独带一份
        "--add-data", f"{ROOT / 'src' / 'triwitness' / 'gateway' / 'egress_proxy.py'}{SEP}triwitness/gateway",
        "--collect-submodules", "triwitness",
        "--collect-submodules", "unittest",  # 演示仓库：tw.exe -m unittest（含 unittest.__main__）
        "--hidden-import", "tzdata",
        "--collect-data", "tzdata",  # Windows 没有系统时区库，Asia/Shanghai 靠 tzdata
    ]  # fmt: skip
    for m in EXCLUDES:
        args += ["--exclude-module", m]
    pyi.run(args)
    built = work / "dist" / "tw"
    if out.exists():
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built, out)
    check_no_dev_modules(out)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"core → {out}  ({size / 1024 / 1024:.1f} MiB, {sum(1 for _ in out.rglob('*'))} files)")


def check_no_dev_modules(out: Path) -> None:
    """列出冻结包里的全部模块（pyi-archive_viewer -r -b），确认演示 / 假模型 / 测试辅助都没打进去。"""
    import subprocess

    exe = out / ("tw.exe" if sys.platform == "win32" else "tw")
    listing = subprocess.run(
        [sys.executable, "-m", "PyInstaller.utils.cliutils.archive_viewer", "-r", "-b", str(exe)],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=300,
    ).stdout  # fmt: skip
    names = set(listing.split())
    assert "triwitness.cli.main" in names, "模块清单里没有 triwitness.cli.main：列举方式失效"
    leaked = [m for m in DEV_ONLY if m in names]
    stems = [m.replace(".", "/") for m in DEV_ONLY]
    files = [p for p in out.rglob("*.py*") if "triwitness" in p.parts
             and any(p.relative_to(out).as_posix().endswith(s + p.suffix) for s in stems)]  # fmt: skip
    if leaked or files:
        raise SystemExit(f"正式版混入了开发 / 测试模块：{leaked} {files}")
    print(f"dev-only 模块检查通过（{len(names)} 项，未含 {', '.join(DEV_ONLY)}）")


if __name__ == "__main__":
    main()
