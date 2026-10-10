# marimo-team__marimo-6819（marimo-team/marimo @ e1006ded30c7）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/marimo-team/marimo/archive/e1006ded30c75c04b395b93cb70f5396d60ca25f.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.8.0 \
    anyio==4.15.1 \
    asttokens==3.0.2 \
    black==23.12.1 \
    certifi==2026.7.22 \
    click==8.5.0 \
    Deprecated==3.0.0 \
    dirty-equals==0.11 \
    docutils==0.23 \
    duckdb==1.5.6 \
    executing==2.2.1 \
    h11==0.16.0 \
    httpcore2==2.13.1 \
    httpcore==1.0.9 \
    httpx2==2.13.1 \
    httpx==0.28.1 \
    hypothesis==6.168.5 \
    idna==3.20 \
    importlib_metadata==8.0.0 \
    iniconfig==2.3.1 \
    inline-snapshot==0.36.0 \
    itsdangerous==2.2.0 \
    jedi==0.20.0 \
    jiter==0.17.0 \
    loro==1.16.2 \
    markdown-it-py==4.2.0 \
    Markdown==3.11 \
    mdurl==0.1.2 \
    msgspec_m==0.19.3 \
    mypy_extensions==1.1.0 \
    narwhals==2.27.1 \
    openai==3.28.0 \
    opentelemetry-api==1.26.0 \
    opentelemetry-sdk==1.26.0 \
    opentelemetry-semantic-conventions==0.47b0 \
    packaging==26.3 \
    parso==0.8.7 \
    pathspec==1.1.1 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    psutil==7.2.2 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pymdown-extensions==10.21.3 \
    pytest-asyncio==1.4.0 \
    pytest-rerunfailures==16.7 \
    pytest-timeout==2.4.0 \
    pytest==9.1.1 \
    PyYAML==6.0.3 \
    rich==15.0.0 \
    ruff==0.17.0 \
    sniffio==1.3.1 \
    sortedcontainers==2.4.0 \
    sqlglot==30.22.0 \
    sqlglotc==30.22.0 \
    sqlglotrs==0.13.0 \
    starlette==1.7.0 \
    tomlkit==0.15.1 \
    truststore==0.10.4 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    uvicorn==0.54.0 \
    websockets==17.2 \
    wrapt==2.5.0 \
    zipp==4.1.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
