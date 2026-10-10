"""`python -m triwitness …` 等同 `tw …`（桌面端在没有 tw 可执行文件时用解释器直接启动核心）。"""

from triwitness.cli.main import app

if __name__ == "__main__":
    app()
