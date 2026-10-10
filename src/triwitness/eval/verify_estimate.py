"""W3-14 预估：verifier 三档对比只重跑验证阶段（复用 W2 已保存的 diff / FinishReport），不重跑 Executor。

- `none`：0 元（直接读 W2 结果）。
- `deterministic`：只用 docker 沙箱复跑复现 / 回归 + 静态检查，不调模型，0 元（只花机器时间）。
- `model`：每个 attempt 一次 Verifier 调用（deepseek-flash 思考档，空闲时段），失败按降级链最多再修 2 次。

输入 token 用真实的 `render_input` 拼出来再按 chars_per_token 折算（与 harness 估算口径一致）；
系统提示 + 工具 schema 是稳定前缀，第 2 次起按缓存命中计。diff 优先用 W2 结果里的 patch.diff，
没有时用参考解（solution/solve.sh，写整文件，偏大 → 估算偏保守）。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from triwitness.core.models import TestRun
from triwitness.llm.pricing import rates
from triwitness.prompts import load_prompt
from triwitness.verify.verifier import SUBMIT_TOOL, VerifierInput, render_input

CHARS_PER_TOKEN = 3.0
TASKS = Path("evals/tasks")
_RUNS = [
    TestRun(scope="repro_base", command="pytest tests/tw_repro", passed=0, failed=1, skipped=0, duration_s=1,
            log_ref="x"),
    TestRun(scope="repro_patched", command="pytest tests/tw_repro", passed=1, failed=0, skipped=0, duration_s=1,
            log_ref="x"),
    TestRun(scope="full", command="pytest", passed=300, failed=2, skipped=5, duration_s=60, log_ref="x",
            new_failures=["tests/test_x.py::test_a"]),
]  # fmt: skip
_STATIC = {"ruff": "pass", "pyright": "skipped", "bandit": "pass", "secrets": "pass"}
_NOTES = ["2 个失败在基线上就存在，不计回归", "复现测试在基线上失败、修复后通过"]


class AttemptSize(BaseModel):
    task_id: str
    source: str  # w2_patch / reference_solution
    body_chars: int


class VerifierEstimate(BaseModel):
    attempts: int
    prefix_tokens: int
    avg_body_tokens: int
    output_tokens: int
    repair_rate: float
    expected_cny: float
    high_cny: float  # 全部未命中、输出 ×1.6、修复率 ×2
    by_source: dict[str, int]
    rates: dict[str, float]


def _issue(task_dir: Path) -> str:
    p = task_dir / "instruction.md"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _body(issue: str, diff: str, summary: str = "修复了 Issue 中描述的问题", risks: list[str] | None = None) -> int:
    inp = VerifierInput(issue=issue, diff=diff, repro_status="reproduced", test_runs=_RUNS, notes=_NOTES,
                        executor_summary=summary, executor_open_risks=risks or ["未覆盖边界情况"],
                        static_checks=_STATIC)  # fmt: skip
    return len(render_input(inp))


def _task_dir(task_id: str, tasks: Path) -> Path | None:
    for split in ("test", "dev"):
        d = tasks / split / task_id
        if d.is_dir():
            return d
    return None


def sizes_from_results(results: Path, tasks: Path = TASKS) -> list[AttemptSize]:
    """W2 结果目录：<config>/<task>/<attempt>/patch.diff（+ finish.json 若有）。空 diff 的 attempt 不需要模型验证。"""
    out: list[AttemptSize] = []
    for patch in sorted(results.glob("*/*/*/patch.diff")):
        diff = patch.read_text(encoding="utf-8", errors="replace")
        if not diff.strip():
            continue
        task_id = patch.parent.parent.name
        d = _task_dir(task_id, tasks)
        fin = patch.parent / "finish.json"
        summary, risks = "修复了 Issue 中描述的问题", None
        if fin.is_file():
            data = json.loads(fin.read_text(encoding="utf-8"))
            summary, risks = data.get("summary", summary), data.get("open_risks")
        out.append(AttemptSize(task_id=task_id, source="w2_patch",
                               body_chars=_body(_issue(d) if d else "", diff, summary, risks)))  # fmt: skip
    return out


def sizes_from_suite(task_ids: list[str], tasks: Path = TASKS) -> list[AttemptSize]:
    out: list[AttemptSize] = []
    for tid in task_ids:
        d = _task_dir(tid, tasks)
        if d is None:
            continue
        sol = d / "solution" / "solve.sh"
        diff = sol.read_text(encoding="utf-8", errors="replace") if sol.is_file() else ""
        out.append(AttemptSize(task_id=tid, source="reference_solution", body_chars=_body(_issue(d), diff)))
    return out


def estimate(
    sizes: list[AttemptSize],
    *,
    model: str = "deepseek-flash",
    peak: bool = False,
    output_tokens: int = 2500,  # 思考档：推理 + submit_verdict 参数
    repair_rate: float = 0.15,  # 需要一次修复重试的比例（W3-10 降级链；修复轮带上一轮输出）
    chars_per_token: float = CHARS_PER_TOKEN,
) -> VerifierEstimate:
    r = rates("deepseek", model, peak=peak)
    prefix_chars = len(load_prompt("verifier").text) + len(json.dumps(SUBMIT_TOOL, ensure_ascii=False))
    prefix = int(prefix_chars / chars_per_token)
    n = len(sizes)
    bodies = [int(s.body_chars / chars_per_token) for s in sizes]

    def cost(miss_prefix_all: bool, out: float, rr: float) -> float:
        total = 0.0
        for i, b in enumerate(bodies):
            hit = 0 if (miss_prefix_all or i == 0) else prefix
            miss = b + (prefix - hit)
            one = (hit * r.cache_hit + miss * r.cache_miss + out * r.output) / 1e6
            # 修复轮：前缀 + 本轮 body 全命中（同一请求前缀），新增上一轮输出 + 错误提示按未命中
            rep = ((prefix + b) * (r.cache_miss if miss_prefix_all else r.cache_hit) + (out + 200) * r.cache_miss
                   + out * r.output) / 1e6  # fmt: skip
            total += one + rr * rep
        return total

    return VerifierEstimate(
        attempts=n, prefix_tokens=prefix, avg_body_tokens=int(sum(bodies) / n) if n else 0,
        output_tokens=output_tokens, repair_rate=repair_rate,
        expected_cny=round(cost(False, output_tokens, repair_rate), 4),
        high_cny=round(cost(True, output_tokens * 1.6, min(1.0, repair_rate * 2)), 4),
        by_source={s: sum(1 for x in sizes if x.source == s) for s in sorted({x.source for x in sizes})},
        rates={"cache_hit": r.cache_hit, "cache_miss": r.cache_miss, "output": r.output},
    )  # fmt: skip


def render(est: VerifierEstimate, *, at: datetime | None = None) -> str:
    when = f"（{at:%Y-%m-%d %H:%M}）" if at else ""
    return "\n".join([
        f"W3-14 verifier 三档预估{when}",
        "| 档位 | 模型调用 | 预估 |",
        "|---|---|---|",
        "| none | 0 | ¥0（读 W2 结果） |",
        "| deterministic | 0 | ¥0（docker 复跑，只花机器时间） |",
        f"| model | {est.attempts} 次 + 修复 ~{est.repair_rate:.0%} "
        f"| ¥{est.expected_cny:.2f}（保守 ¥{est.high_cny:.2f}） |",
        "",
        f"attempt 数 {est.attempts}（{', '.join(f'{k}={v}' for k, v in est.by_source.items())}）；"
        f"稳定前缀 ≈{est.prefix_tokens} token，平均正文 ≈{est.avg_body_tokens} token，"
        f"输出 {est.output_tokens} token/次；单价（元/百万）命中 {est.rates['cache_hit']} / "
        f"未命中 {est.rates['cache_miss']} / 输出 {est.rates['output']}。",
    ])  # fmt: skip


__all__ = ["AttemptSize", "VerifierEstimate", "estimate", "render", "sizes_from_results", "sizes_from_suite"]
