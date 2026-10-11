#!/usr/bin/env bash
# W5-13：在 WSL2（Docker Desktop 的 WSL 集成）里用 Harbor 跑 Terminal-Bench 2.0 子集 × TriWitness，打包结果。
# 由 scripts/windows/run-harbor-tb2.ps1 调用；也可在任何 Linux（docker + compose 可用、容器能联网）上直接跑：
#   DEEPSEEK_API_KEY=... bash scripts/wsl/run-harbor-tb2.sh [--smoke] [--allow-peak] [--out-win /mnt/c/...]
# 密钥只从环境变量读取，不写入任何文件。
set -uo pipefail
REPO_URL="${TW_REPO_URL:-https://github.com/Akarin7784/triwitness.git}"
BRANCH="${TW_BRANCH:-main}"
WORK="${TW_HARBOR_HOME:-$HOME/tw-harbor}"
SMOKE=0; ALLOW_PEAK=""; OUT_WIN=""; CONC=2
while [ $# -gt 0 ]; do
  case "$1" in
    --smoke) SMOKE=1 ;;
    --allow-peak) ALLOW_PEAK="--allow-peak" ;;
    --out-win) OUT_WIN="$2"; shift ;;
    --concurrency) CONC="$2"; shift ;;
  esac
  shift
done
die() { echo "错误：$*" >&2; exit 1; }
[ -n "${DEEPSEEK_API_KEY:-}" ] || die "没有 DEEPSEEK_API_KEY（Windows 端用 WSLENV 透传）"
docker info >/dev/null 2>&1 || die "WSL 里 docker 不可用：Docker Desktop → Settings → Resources → WSL integration 打开当前发行版"
docker compose version >/dev/null 2>&1 || die "WSL 里没有 docker compose（Docker Desktop 自带；请开启 WSL 集成）"
command -v git >/dev/null || die "WSL 里没有 git（sudo apt install git）"
if ! command -v uv >/dev/null; then
  echo "==> 安装 uv（用户目录）"
  curl -LsSf https://astral.sh/uv/install.sh | sh || die "uv 安装失败"
  export PATH="$HOME/.local/bin:$PATH"
fi
mkdir -p "$WORK"
SRC="$WORK/triwitness"
if [ ! -d "$SRC/.git" ]; then
  git clone -q --branch "$BRANCH" "$REPO_URL" "$SRC" || die "git clone 失败"
else
  git -C "$SRC" fetch -q origin "$BRANCH" && git -C "$SRC" checkout -q "$BRANCH" && git -C "$SRC" merge -q --ff-only "origin/$BRANCH" \
    || die "更新仓库失败（本地有改动？）"
fi
cd "$SRC" || exit 1
echo "==> commit $(git rev-parse --short HEAD)"
uv sync -q --frozen --no-dev || die "uv sync 失败"
export TW_HOME="$WORK/tw-home"
uv run --no-sync python scripts/harbor_external.py fetch --dir "$WORK/terminal-bench-2" || exit 1
args=(--dir "$WORK/terminal-bench-2" --out "$WORK/jobs" --concurrency "$CONC")
[ "$SMOKE" = 1 ] && args+=(--task fix-git)
[ -n "$ALLOW_PEAK" ] && args+=("$ALLOW_PEAK")
uv run --no-sync python scripts/harbor_external.py run "${args[@]}" 2>&1 | tee -a "$WORK/run.log"
rc=${PIPESTATUS[0]}
uv run --no-sync python scripts/harbor_external.py report --out "$WORK/jobs" 2>&1 | tee -a "$WORK/run.log"
uv run --no-sync python - <<'PY' 2>&1 | tee -a "$WORK/run.log"
from triwitness.cost.ledger import GlobalLedger
led = GlobalLedger()
print(f"账本（{led.path}）：harbor-external 累计 ¥{led.spent('harbor-external'):.4f}，全部 ¥{led.spent():.4f}")
PY
cp "$WORK/run.log" "$WORK/jobs/run.log" 2>/dev/null
zip=$(uv run --no-sync python scripts/harbor_external.py bundle --out "$WORK/jobs" | sed -n 's/^已打包：\(.*\.zip\).*/\1/p')
if [ -n "$OUT_WIN" ] && [ -n "$zip" ]; then
  mkdir -p "$OUT_WIN" && cp "$zip" "$OUT_WIN/" && echo "结果包已复制到 $OUT_WIN/$(basename "$zip")"
fi
exit "$rc"
