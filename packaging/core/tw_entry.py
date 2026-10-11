"""PyInstaller 入口：打包后的 tw.exe（桌面端内置核心）。

除了 `tw …` 命令本身，还兼容 `tw.exe -m <模块> …`：演示仓库的测试命令是 `<当前解释器> -m unittest …`，
打包后“当前解释器”就是 tw.exe，所以这里按 `python -m` 的语义用 runpy 跑标准库模块（sys.path[0] = 当前目录）。
"""

from __future__ import annotations

import os
import runpy
import sys


def _hang_dump() -> None:
    """诊断：设置 TW_HANG_DUMP_S=<秒> 时，每隔这么久把所有线程的调用栈写到 stderr（排查卡住，不影响正常运行）。"""
    secs = os.environ.get("TW_HANG_DUMP_S", "").strip()
    if secs.isdigit() and int(secs) > 0 and sys.stderr is not None:
        import faulthandler

        faulthandler.dump_traceback_later(int(secs), repeat=True, file=sys.stderr)


def main() -> None:
    _hang_dump()
    if len(sys.argv) >= 3 and sys.argv[1] == "-m":
        mod = sys.argv[2]
        sys.argv = [mod, *sys.argv[3:]]
        sys.path.insert(0, os.getcwd())
        runpy.run_module(mod, run_name="__main__", alter_sys=True)
        return
    from triwitness.cli.main import app

    app(prog_name="tw")


if __name__ == "__main__":
    main()
