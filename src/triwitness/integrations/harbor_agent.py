"""Harbor 自定义 Agent：`harbor run -a triwitness.integrations.harbor_agent:TriWitnessAgent`（W5-13）。

需要 Harbor（不是 TriWitness 的依赖）：`uv run --with harbor==0.24.0 harbor run ...`，见
scripts/harbor_external.py 与 scripts/windows/run-harbor-tb2.ps1。只用 deepseek-flash（非思考），所有调用记账本
（类别 `harbor-external`）；DeepSeek 密钥从环境变量读取。评测模式：不问人、不开 PR。
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from harbor.agents.base import BaseAgent  # pyright: ignore[reportMissingImports]

from triwitness.core.models import Budget
from triwitness.harness.config import HarnessConfig
from triwitness.harness.run import run_task
from triwitness.integrations.harbor_sandbox import REPRO_DIR_DEFAULT, HarborSandbox, external_task_prompt
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools
from triwitness.tools.repro import cleanup_repro_artifacts, snapshot_repro_dirs

CATEGORY = "harbor-external"
TOOLS = ["bash", "edit_file", "finish", "grep", "list_files", "notes", "read_file", "write_file"]


class TriWitnessAgent(BaseAgent):  # pyright: ignore[reportUntypedBaseClass]
    """`--ak harness=<名>`（configs/harness/<名>.yaml，默认 baseline）、`--ak thinking=true`。

    复现产物（W5-13 第二轮，默认安全）：`--ak repro_dir=/tmp/tw_repro`（默认；空串 = 不加提示）让 Agent 把复现测试
    写到任务目录之外；`--ak repro_cleanup=true`（默认）在 Agent 结束、verifier 开始前删掉工作目录下新出现的
    tw_repro / .pytest_cache / __pycache__ 和因此变空的新 tests 目录。"""

    @staticmethod
    def name() -> str:
        return "triwitness"

    def version(self) -> str:
        from triwitness import __version__

        return str(__version__)

    def __init__(self, *args: Any, harness: str = "baseline", thinking: str | bool = False,
                 repro_dir: str = REPRO_DIR_DEFAULT, repro_cleanup: str | bool = True,
                 **kwargs: Any) -> None:  # fmt: skip
        super().__init__(*args, **kwargs)
        self.harness_name = harness
        self.thinking = str(thinking).lower() in ("1", "true", "yes")
        self.repro_dir = repro_dir.strip().rstrip("/") if repro_dir and repro_dir.strip() not in ("none", "") else ""
        self.repro_cleanup = str(repro_cleanup).lower() not in ("0", "false", "no")

    async def setup(self, environment: Any) -> None:
        return None

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        from triwitness.llm.router import Router

        os.environ.setdefault("TW_LLM_MODE", "live")
        cfg = HarnessConfig.load(f"harness/{self.harness_name}.yaml")
        tools = [t for t in cfg.tools if t in TOOLS]
        sb = await HarborSandbox.attach(environment)
        run_id = f"harbor-{uuid.uuid4().hex[:8]}"
        rec = TrajectoryRecorder(getattr(self, "session_id", None) or run_id, run_id, run_dir=self.logs_dir / "tw")
        router = Router.deepseek_default(executor={"model": "deepseek-flash", "thinking": self.thinking})
        title = next((ln.strip("# ").strip() for ln in instruction.splitlines() if ln.strip()), "task")[:120]
        before = await snapshot_repro_dirs(sb, sb.spec.workdir) if self.repro_cleanup else set()
        prompt = external_task_prompt(instruction, self.repro_dir)
        try:
            res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools(names=tools)),
                                 sandbox=sb, issue_title=title, task_prompt=prompt,
                                 repo="harbor", budget=Budget.for_eval(), config_hash=f"harbor-{self.harness_name}",
                                 mode="eval", config=cfg, category=CATEGORY)  # type: ignore[arg-type]  # fmt: skip
        finally:
            removed = await cleanup_repro_artifacts(sb, sb.spec.workdir, before) if self.repro_cleanup else []
        c = res.cost
        flat = c.to_flat()
        context.n_input_tokens = flat.get("input_tokens")
        context.n_cache_tokens = flat.get("cache_hit_tokens")
        context.n_output_tokens = flat.get("output_tokens")
        context.metadata = {"triwitness_status": res.status, "cost_cny": round(c.total_cny, 6),
                            "steps": res.outcome.steps, "cache_hit_rate": c.cache_hit_rate,
                            "finish": res.finish.summary if res.finish else None,
                            "repro_dir": self.repro_dir or None, "repro_cleanup": removed}  # fmt: skip


__all__ = ["CATEGORY", "TriWitnessAgent"]
