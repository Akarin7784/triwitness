# W4-14 评审者消融的运行镜像（只用于跑实验，不是产品安装包）。
# 构建：docker build -f evals/reviewer/Dockerfile -t tw-reviewer-ablation .
# 运行：见 scripts/windows/run-reviewer-ablation.ps1（密钥只经 `docker run -e DEEPSEEK_API_KEY` 透传，不进镜像）。
FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    UV_INDEX_URL=${PIP_INDEX_URL} \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY configs ./configs
COPY scripts ./scripts
COPY evals ./evals

# 基线源码在构建时下载好（GitHub 源码包），运行时不需要再联网拉仓库
RUN uv run --no-sync python scripts/reviewer_ablation.py prepare --out /data --repos /data/repos

ARG GIT_SHA=unknown
RUN echo "$GIT_SHA" > /app/.git-sha

ENV TW_LLM_MODE=live \
    TW_HOME=/work/tw-home
ENTRYPOINT ["bash", "/app/scripts/windows/ablation-entry.sh"]
