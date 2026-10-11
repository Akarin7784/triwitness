#!/usr/bin/env bash
# 容器入口（W5-09/10/11）：OFAT 消融 → 报告 → 打包。第一个参数是消融规格（evals/ablations/*.yaml），其余原样传给
# `ofat_ablation.py run`。/out 是宿主机挂载目录（结果与 zip）；/work 是 docker 卷（TW_HOME 账本、回放缓存，续跑时保留）。
set -uo pipefail
cd /app
spec="${1:-evals/ablations/w5-round1.yaml}"
shift || true
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "容器里没有 DEEPSEEK_API_KEY（请在宿主机设置环境变量后用 -e DEEPSEEK_API_KEY 透传）" >&2
  exit 2
fi
if [ ! -S /var/run/docker.sock ]; then
  echo "容器里没有 /var/run/docker.sock（docker run 需要 -v //var/run/docker.sock:/var/run/docker.sock）" >&2
  exit 2
fi
mkdir -p /out/ofat /work/tw-home
uv run --no-sync python - <<'PY' > /out/ofat/env.json
import json, os, platform
import docker
sha = open("/app/.git-sha").read().strip() if os.path.exists("/app/.git-sha") else "?"
v = docker.from_env().version()
print(json.dumps({"python": platform.python_version(), "git_sha": sha, "docker": v.get("Version"),
                  "os": v.get("Os"), "kernel": v.get("KernelVersion"), "llm_mode": os.environ.get("TW_LLM_MODE")}))
PY
uv run --no-sync python scripts/ofat_ablation.py run "$spec" --out /out/ofat "$@" 2>&1 | tee -a /out/ofat/run.log
rc=${PIPESTATUS[0]}
uv run --no-sync python scripts/ofat_ablation.py report "$spec" --out /out/ofat 2>&1 | tee -a /out/ofat/run.log
uv run --no-sync python - <<'PY' 2>&1 | tee -a /out/ofat/run.log
from triwitness.cost.ledger import GlobalLedger
led = GlobalLedger()
print(f"本机账本（容器卷）：ofat-ablation 累计 ¥{led.spent('ofat-ablation'):.4f}，全部 ¥{led.spent():.4f}")
PY
uv run --no-sync python scripts/ofat_ablation.py bundle --out /out/ofat 2>&1 | tee -a /out/ofat/run.log
exit "$rc"
