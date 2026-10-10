"""录制 DeepSeek fixture（W1-09/W1-08）。会真调 API、花钱：只在空闲时段运行。

用法：TW_LLM_MODE=record uv run python scripts/record_llm_fixture.py
- 只允许 deepseek-flash；高峰时段直接拒绝（不提供 --allow-peak）。
- 录制文件写入 tests/fixtures/llm/deepseek/<case>.json，自动去掉认证信息；已存在的用例走缓存、不重复花钱。
- 每次真实调用记入全局账本（~/.triwitness/ledger.sqlite，类别 dev）。
- 输出只含用量与费用，绝不打印密钥。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from triwitness.cost.ledger import GlobalLedger
from triwitness.llm import cases
from triwitness.llm.client import LLMClient
from triwitness.llm.deepseek import BASE_URL, DeepSeekAdapter
from triwitness.llm.http import HttpTransport
from triwitness.llm.replay import RecordReplayTransport, ReplayStore
from triwitness.llm.types import LLMRequest, LLMResponse

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "llm" / "deepseek"


async def main() -> int:
    if os.environ.get("TW_LLM_MODE") != "record":
        sys.stderr.write("需要 TW_LLM_MODE=record\n")
        return 2
    store = ReplayStore("deepseek", [FIXTURES], write_dir=FIXTURES)
    rr = RecordReplayTransport(store, HttpTransport(BASE_URL, "DEEPSEEK_API_KEY"), mode="record")
    ledger = GlobalLedger()
    client = LLMClient(DeepSeekAdapter(), rr, ledger=ledger, allow_peak=False)
    before = ledger.spent()

    async def run(name: str, req: LLMRequest) -> LLMResponse:
        rr.next_name = name
        r = await client.complete(req, cases.MODEL, category="dev")
        u = r.usage
        sys.stdout.write(
            f"{name:28s} {r.source:6s} served={r.served_model} in={u.input_tokens} hit={u.cache_hit_tokens} "
            f"miss={u.cache_miss_tokens} out={u.output_tokens} reason={u.reasoning_tokens} "
            f"¥{r.cost_cny:.6f} peak={r.peak} {r.latency_ms}ms\n"
        )
        return r

    await run("text_nonthinking", cases.text_nonthinking())
    await run("tool_single_nonthinking", cases.tool_single_nonthinking())
    first = await run("tool_multiturn_thinking_1", cases.tool_multiturn_thinking_1())
    await run("tool_multiturn_thinking_2", cases.tool_multiturn_thinking_2(first))
    await run("cache_prefix_1", cases.cache_prefix(cases.CACHE_Q1))
    await run("cache_prefix_2", cases.cache_prefix(cases.CACHE_Q2))
    sys.stdout.write(f"本次真实花费 ¥{ledger.spent() - before:.6f}；账本累计 ¥{ledger.spent():.6f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
