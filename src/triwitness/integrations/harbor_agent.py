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
from triwitness.integrations.harbor_sandbox import HarborSandbox
from triwitness.telemetry.trajectory import TrajectoryRecorder
from triwitness.tools import ToolRegistry, default_tools

CATEGORY = "harbor-external"
TOOLS = ["bash", "edit_file", "finish", "grep", "list_files", "notes", "read_file", "write_file"]


class TriWitnessAgent(BaseAgent):  # pyright: ignore[reportUntypedBaseClass]
    """`--ak harness=<名>`（configs/harness/<名>.yaml，默认 baseline）、`--ak thinking=true`。"""

    @staticmethod
    def name() -> str:
        return "triwitness"

    def version(self) -> str:
        from triwitness import __version__

        return str(__version__)

    def __init__(self, *args: Any, harness: str = "baseline", thinking: str | bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.harness_name = harness
        self.thinking = str(thinking).lower() in ("1", "true", "yes")

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
        res = await run_task(recorder=rec, router=router, registry=ToolRegistry(default_tools(names=tools)),
                             sandbox=sb, issue_title=title, task_prompt=instruction, repo="harbor",
                             budget=Budget.for_eval(), config_hash=f"harbor-{self.harness_name}", mode="eval",
                             config=cfg, category=CATEGORY)  # type: ignore[arg-type]  # fmt: skip
        c = res.cost
        flat = c.to_flat()
        context.n_input_tokens = flat.get("input_tokens")
        context.n_cache_tokens = flat.get("cache_hit_tokens")
        context.n_output_tokens = flat.get("output_tokens")
        context.metadata = {"triwitness_status": res.status, "cost_cny": round(c.total_cny, 6),
                            "steps": res.outcome.steps, "cache_hit_rate": c.cache_hit_rate,
                            "finish": res.finish.summary if res.finish else None}  # fmt: skip


__all__ = ["CATEGORY", "TriWitnessAgent"]
