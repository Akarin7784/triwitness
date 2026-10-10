"""演示适配器（`tw run --demo`）：脚本化 Router + 自带的小仓库，¥0、不联网，走真实的沙箱 / 权限 / 验证流程。

用于桌面端开发、截图与端到端回放测试；真实路径（DeepSeek）不变，只是不在这里调用。
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

from triwitness.core.models import Usage
from triwitness.cost.guard import TaskBudgetGuard
from triwitness.harness.testing import FakeRouter, call, say
from triwitness.llm.types import LLMRequest, LLMResponse

ISSUE = "line_count 把空行也算进去了：「床前明月光\\n\\n疑是地上霜\\n」应为 2 行，实际返回 4。"
REPRO = "tests/tw_repro/test_issue_demo.py"

FILES: dict[str, str] = {
    "verses.py": (
        '"""小诗集工具。"""\n\n\n'
        "def line_count(text: str) -> int:\n"
        '    """数一首诗有几行（空行不算）。"""\n'
        '    return len(text.split("\\n"))\n'
    ),
    "tests/__init__.py": "",
    "tests/test_verses.py": (
        "import unittest\n\nfrom verses import line_count\n\n\n"
        "class LineCountTest(unittest.TestCase):\n"
        "    def test_single_line(self):\n"
        '        self.assertEqual(line_count("举头望明月"), 1)\n'
    ),
    "README.md": "# verses\n\n一个小诗集工具，用来演示三证。\n",
}

OLD = '    return len(text.split("\\n"))\n'
NEW = "    return sum(1 for line in text.splitlines() if line.strip())\n"
REPRO_TEST = (
    "import unittest\n\nfrom verses import line_count\n\n\n"
    "class IssueDemoTest(unittest.TestCase):\n"
    "    def test_blank_lines_not_counted(self):\n"
    '        self.assertEqual(line_count("床前明月光\\n\\n疑是地上霜\\n"), 2)\n'
)


def python_cmd() -> str:
    """当前解释器，正斜杠 + 引号：Git Bash / cmd / POSIX 都能直接执行。"""
    return f'"{Path(sys.executable).as_posix()}"'


def test_command() -> str:
    return f"{python_cmd()} -m unittest discover -s tests -t ."


def ensure_repo(path: Path) -> Path:
    """目标目录不存在或为空：写入演示仓库并提交一次；已是 git 仓库则原样使用。"""
    path = path.expanduser()
    if (path / ".git").exists():
        return path
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"演示仓库目录非空且不是 git 仓库：{path}")
    for rel, text in FILES.items():
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    git = ["git", "-c", "user.email=demo@triwitness.local", "-c", "user.name=TriWitness Demo",
           "-c", "core.autocrlf=false"]  # fmt: skip
    for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "演示仓库"]):
        subprocess.run([*git, *args], cwd=path, check=True, capture_output=True)
    return path


def script() -> list[Any]:
    repro_cmd = f"{python_cmd()} -m unittest {REPRO}"
    finish = {"summary": "line_count 改为只数非空行；复现测试在原代码上失败、修复后通过，原有测试仍通过。",
              "changes": [{"path": "verses.py", "kind": "modified"}], "tests_run": ["unittest discover"],
              "tests_passed": True, "confidence": 0.86,
              "open_risks": ["只按 str.strip() 判空，全角空格行也会被当成空行"]}  # fmt: skip
    return [
        say(call("read_file", path="verses.py"), text="先读 verses.py，看 line_count 怎么数行。"),
        say(
            call("read_file", path="tests/test_verses.py"),
            text="split('\\n') 会把空行和末尾换行都算进去。看看已有测试。",
        ),
        say(call("write_file", path=REPRO, content=REPRO_TEST), text="先写一个复现：两句诗夹一个空行，应为 2。"),
        say(call("submit_repro", path=REPRO, cmd=repro_cmd), text="提交复现，确认它在原代码上失败。"),
        say(call("edit_file", path="verses.py", old_str=OLD, new_str=NEW), text="复现成立。改成只数非空行。"),
        say(call("run_tests"), text="跑一遍全部测试。"),
        say(call("finish", **finish), text="都通过了，收尾。"),
    ]


class DemoRouter(FakeRouter):
    """脚本化 Router：每步停顿一下，让推流像真的在写；成本记 0（不进账本）。"""

    def __init__(self, *, delay_s: float = 0.9) -> None:
        super().__init__(script(), cost_cny=0.0, served_model="demo",
                         usage=Usage(input_tokens=6200, cache_hit_tokens=5900, cache_miss_tokens=300,
                                     output_tokens=180))  # fmt: skip
        self.delay_s = delay_s

    async def complete(self, req: LLMRequest, *, guard: TaskBudgetGuard | None = None, **kw: Any) -> LLMResponse:
        await asyncio.sleep(self.delay_s)
        return await super().complete(req, guard=guard, **kw)


__all__ = ["ISSUE", "DemoRouter", "ensure_repo", "test_command"]
