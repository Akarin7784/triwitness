# vndee__llm-sandbox-101（vndee/llm-sandbox @ e797eb390565）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/vndee/llm-sandbox/archive/e797eb3905650a624944183278a144d29ef0d802.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohappyeyeballs==2.7.1 \
    aiohttp-retry==2.9.1 \
    aiohttp==3.14.4 \
    aiosignal==1.4.0 \
    annotated-types==0.8.0 \
    attrs==26.1.0 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    coverage==7.16.2 \
    docker==7.2.0 \
    durationpy==0.11 \
    frozenlist==1.8.0 \
    idna==3.20 \
    iniconfig==2.3.1 \
    kubernetes==37.0.1 \
    multidict==6.9.1 \
    oauthlib==4.0.0 \
    packaging==26.3 \
    pluggy==1.6.0 \
    podman==5.8.0 \
    propcache==0.5.4 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-cov==7.1.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.3 \
    requests-oauthlib==2.0.0 \
    requests==2.34.2 \
    six==1.17.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    websocket-client==1.9.2 \
    yarl==1.25.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
