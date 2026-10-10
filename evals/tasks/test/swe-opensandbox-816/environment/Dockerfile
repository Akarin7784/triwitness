# alibaba__opensandbox-816（alibaba/OpenSandbox @ fb78091f947f）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git >/dev/null && rm -rf /var/lib/apt/lists/*
ADD https://github.com/alibaba/OpenSandbox/archive/fb78091f947f62ae2c71a372af42425a764aacee.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohappyeyeballs==2.7.1 \
    aiohttp-retry==2.9.1 \
    aiohttp==3.14.4 \
    aiosignal==1.4.0 \
    annotated-doc==0.0.5 \
    annotated-types==0.8.0 \
    anyio==4.15.1 \
    attrs==26.1.0 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    click==8.5.0 \
    coverage==7.16.2 \
    docker==7.2.0 \
    durationpy==0.11 \
    fastapi==0.143.0 \
    frozenlist==1.8.0 \
    h11==0.16.0 \
    httpcore==1.0.9 \
    httpx-sse==0.4.3 \
    httpx==0.28.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    kubernetes==37.0.1 \
    markdown-it-py==4.2.0 \
    mdurl==0.1.2 \
    multidict==6.9.1 \
    oauthlib==4.0.0 \
    opensandbox==0.1.16 \
    opentelemetry-api==1.45.1 \
    packaging==26.3 \
    pluggy==1.6.0 \
    propcache==0.5.4 \
    pydantic-settings==2.15.0 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-asyncio==1.4.0 \
    pytest-cov==7.1.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    python-dotenv==1.2.4 \
    PyYAML==6.0.3 \
    redis==8.1.0 \
    requests-oauthlib==2.0.0 \
    requests==2.34.2 \
    rich==13.9.4 \
    six==1.17.0 \
    socksio==1.0.0 \
    starlette==1.7.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    uvicorn==0.54.0 \
    websocket-client==1.9.2 \
    websockets==17.2 \
    yarl==1.25.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
