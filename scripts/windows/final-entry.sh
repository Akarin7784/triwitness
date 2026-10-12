#!/usr/bin/env bash
# 容器入口（W8-01 终测）：两臂（TW_SKIP_RUN=1 跳过） tw eval run --live → 报告 → 打包（超 24MB 自动拆分）。
# /out 是宿主机挂载目录；/work 是 docker 卷（TW_HOME 账本、回放缓存，续跑时保留）。其余参数原样传给 final_eval.py run。
set -uo pipefail
cd /app
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "容器里没有 DEEPSEEK_API_KEY（宿主机设置后用 -e DEEPSEEK_API_KEY 透传）" >&2
  exit 2
fi
if [ ! -S /var/run/docker.sock ]; then
  echo "容器里没有 /var/run/docker.sock（docker run 需要 -v //var/run/docker.sock:/var/run/docker.sock）" >&2
  exit 2
fi
mkdir -p /out/final /work/tw-home
uv run --no-sync python - <<'PY' > /out/final/env.json
import json, os, platform
import docker
sha = open("/app/.git-sha").read().strip() if os.path.exists("/app/.git-sha") else "?"
v = docker.from_env().version()
print(json.dumps({"python": platform.python_version(), "git_sha": sha, "docker": v.get("Version"),
                  "os": v.get("Os"), "kernel": v.get("KernelVersion"), "llm_mode": os.environ.get("TW_LLM_MODE")}))
PY
rc=0
if [ "${TW_SKIP_RUN:-0}" != "1" ]; then
  uv run --no-sync python scripts/final_eval.py run --out /out/final "$@" 2>&1 | tee -a /out/final/run.log
  rc=${PIPESTATUS[0]}
fi
if [ "${TW_REPRODUCE:-0}" = "1" ]; then   # W8-05：终测后复现 baseline 臂 1 道最便宜的题（约 ¥0.05-0.2）
  uv run --no-sync python scripts/final_eval.py reproduce --out /out/final 2>&1 | tee -a /out/final/run.log
fi
uv run --no-sync python scripts/final_eval.py report --out /out/final 2>&1 | tee -a /out/final/run.log
uv run --no-sync python - <<'PY' 2>&1 | tee -a /out/final/run.log
from triwitness.cost.ledger import GlobalLedger
led = GlobalLedger()
print(f"本机账本（容器卷）：final-eval 累计 ¥{led.spent('final-eval'):.4f}，全部 ¥{led.spent():.4f}")
PY
uv run --no-sync python scripts/final_eval.py bundle --out /out/final --dest /out 2>&1 | tee -a /out/final/run.log
exit "$rc"
