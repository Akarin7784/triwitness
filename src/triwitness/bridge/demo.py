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
from triwitness.llm.stream import current_sink, split_text
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
        subprocess.run([*git, *args], cwd=path, check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    return path


def script() -> list[Any]:
    repro_cmd = f"{python_cmd()} -m unittest {REPRO}"
    finish = {"summary": "line_count 改为只数非空行；复现测试在原代码上失败、修复后通过，原有测试仍通过。",
              "changes": [{"path": "verses.py", "kind": "modified"}], "tests_run": ["unittest discover"],
              "tests_passed": True, "confidence": 0.86,
              "open_risks": ["只按 str.strip() 判空，全角空格行也会被当成空行"]}  # fmt: skip
    return [
        say(call("read_file", path="verses.py"), text="先读 `verses.py`，看 `line_count` 怎么数行。"),
        say(
            call("read_file", path="tests/test_verses.py"),
            text="`split('\\n')` 会把**空行**和**末尾换行**都算进去：\n\n"
            "- 「床前明月光」和「疑是地上霜」之间的空行算 1 行\n"
            "- 末尾的 `\\n` 又多切出一个空串\n\n看看已有测试。",
        ),
        say(call("write_file", path=REPRO, content=REPRO_TEST), text="先写一个复现：两句诗夹一个空行，应为 2。"),
        say(call("submit_repro", path=REPRO, cmd=repro_cmd), text="提交复现，确认它在原代码上失败。"),
        say(
            call("edit_file", path="verses.py", old_str=OLD, new_str=NEW),
            text="复现成立。改成只数非空行：\n\n```python\n" + NEW.strip() + "\n```",
        ),
        say(call("run_tests"), text="跑一遍全部测试。"),
        say(call("finish", **finish), text="都通过了，收尾。"),
    ]


# 每步的“推理”（演示流式思考用；按思考强度取前几句）
REASONING: list[str] = [
    "Issue 说空行被算进行数。先看实现，确认是哪种切分方式。如果用的是 split，空行和末尾换行都会多算。",
    "实现是 len(text.split('\\n'))。对「床前明月光\\n\\n疑是地上霜\\n」会切出 4 段：两句诗、一个空串（空行）、"
    "一个空串（末尾）。所以返回 4。修法应该是只数非空行。改之前先看已有测试的风格。",
    "测试用 unittest。复现就写同样风格：输入两句诗夹空行，期望 2。放在 tests/tw_repro/ 下，不碰原有测试。",
    "复现写好了，提交给评审前先确认它在原代码上确实失败，否则说明没抓到问题。",
    "复现在原代码上失败，符合预期。用 splitlines() 再过滤 strip() 为空的行：既去掉空行，也不会多出末尾空串。"
    "全角空格行也会被当空行，这一点记为风险。",
    "改完了。跑全部测试，确认复现通过、原有测试不回归。",
    "全部通过。整理结论：改动一处，复现在原代码失败、修复后通过；风险是全角空格。置信度给 0.86。",
]


EFFORT_SENTENCES = {"low": 1, "high": 2, "max": 99, None: 2}


def reasoning_for(step: int, effort: str | None) -> str:
    text = REASONING[step] if step < len(REASONING) else ""
    parts = [p + "。" for p in text.split("。") if p]
    return "".join(parts[: EFFORT_SENTENCES.get(effort, 2)])


class DemoRouter(FakeRouter):
    """脚本化 Router：模拟流式输出（先推理、后正文，按片段停顿），让界面像真的在写；成本记 0（不进账本）。"""

    def __init__(self, *, delay_s: float = 0.9, thinking: bool = True, effort: str | None = None) -> None:
        super().__init__(script(), cost_cny=0.0, served_model="demo",
                         usage=Usage(input_tokens=6200, cache_hit_tokens=5900, cache_miss_tokens=300,
                                     output_tokens=180))  # fmt: skip
        self.delay_s = delay_s
        self.thinking = thinking
        self.effort = effort
        self.step = 0

    async def complete(self, req: LLMRequest, *, guard: TaskBudgetGuard | None = None, **kw: Any) -> LLMResponse:
        step = self.step
        self.step += 1
        msg = self.script[0] if self.script else None
        reasoning = reasoning_for(step, self.effort) if self.thinking else ""
        sink = current_sink()
        if sink is None or msg is None:
            await asyncio.sleep(self.delay_s)
        else:
            pieces = [("reasoning", p) for p in split_text(reasoning, 6)]
            pieces += [("content", p) for p in split_text(msg.content or "", 4)]
            gap = self.delay_s * 2.4 / max(1, len(pieces))
            await asyncio.sleep(self.delay_s * 0.3)
            for kind, text in pieces:
                sink(kind, text)  # type: ignore[arg-type]
                await asyncio.sleep(gap)
        resp = await super().complete(req, guard=guard, **kw)
        if reasoning:
            resp.message = resp.message.model_copy(update={"reasoning_content": reasoning})
        resp.latency_ms = int(self.delay_s * 2700)
        return resp


__all__ = ["ISSUE", "DemoRouter", "ensure_repo", "test_command"]
