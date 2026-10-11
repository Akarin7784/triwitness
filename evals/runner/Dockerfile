# W5 OFAT 消融的运行镜像（只用于跑实验，不是产品安装包）。
# 构建：docker build -f evals/runner/Dockerfile -t tw-eval-runner .
# 运行：见 scripts/windows/run-ofat-ablation.ps1。容器通过挂载的 docker.sock 在宿主 Docker 上构建任务镜像、起沙箱
# （沙箱只用 put_archive 传文件，不用 bind mount，所以容器内路径不需要在宿主上存在）。
# 密钥只经 `docker run -e DEEPSEEK_API_KEY` 透传，不进镜像。
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

ARG GIT_SHA=unknown
RUN echo "$GIT_SHA" > /app/.git-sha

ENV TW_LLM_MODE=live \
    TW_HOME=/work/tw-home
ENTRYPOINT ["bash", "/app/scripts/windows/ofat-entry.sh"]
