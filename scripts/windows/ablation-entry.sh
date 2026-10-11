#!/usr/bin/env bash
# 容器入口（W4-14）：跑消融 → 评分 → 打包。参数原样传给 `reviewer_ablation.py run`。
# /out 是宿主机挂载目录（结果与 zip）；/work 是 docker 卷（worktree、TW_HOME 账本，续跑时保留）。
set -uo pipefail
cd /app
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "容器里没有 DEEPSEEK_API_KEY（请在宿主机设置环境变量后用 -e DEEPSEEK_API_KEY 透传）" >&2
  exit 2
fi
mkdir -p /out/ablation /work/sandbox /work/tw-home
python - <<'PY' > /out/ablation/env.json
import json, platform, subprocess, os
sha = open("/app/.git-sha").read().strip() if os.path.exists("/app/.git-sha") else "?"
print(json.dumps({"python": platform.python_version(), "git_sha": sha, "llm_mode": os.environ.get("TW_LLM_MODE")}))
PY
uv run --no-sync python scripts/reviewer_ablation.py run --out /out/ablation --repos /data/repos --work /work/sandbox "$@" \
  2>&1 | tee -a /out/ablation/run.log
rc=${PIPESTATUS[0]}
uv run --no-sync python scripts/reviewer_ablation.py score --out /out/ablation 2>&1 | tee -a /out/ablation/run.log
uv run --no-sync python - <<'PY' 2>&1 | tee -a /out/ablation/run.log
from triwitness.cost.ledger import GlobalLedger
led = GlobalLedger()
print(f"本机账本（容器卷）：reviewer-ablation 累计 ¥{led.spent('reviewer-ablation'):.4f}，全部 ¥{led.spent():.4f}")
PY
uv run --no-sync python scripts/reviewer_ablation.py bundle --out /out/ablation 2>&1 | tee -a /out/ablation/run.log
exit "$rc"
