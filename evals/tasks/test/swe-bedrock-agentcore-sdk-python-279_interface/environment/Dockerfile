# aws__bedrock-agentcore-sdk-python-279_interface（aws/bedrock-agentcore-sdk-python @ 1bd22b7e51c1）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/aws/bedrock-agentcore-sdk-python/archive/1bd22b7e51c152aba0f9e322699d06102b707026.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    click==8.5.0 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    dill==0.4.1 \
    docstring_parser==0.18.0 \
    frozenlist==1.8.0 \
    h11==0.16.0 \
    httpcore2==2.13.1 \
    httpcore==1.0.9 \
    httpx2==2.13.1 \
    httpx==0.28.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    jmespath==1.1.0 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    librt==0.16.0 \
    markdown-it-py==4.2.0 \
    markdownify==1.2.3 \
    MarkupSafe==3.0.4 \
    mcp-types==2.1.1 \
    mcp==2.1.1 \
    mdurl==0.1.2 \
    moto==5.2.3 \
    mpmath==1.3.0 \
    multidict==6.9.1 \
    mypy==2.4.0 \
    mypy_extensions==1.1.0 \
    opentelemetry-api==1.45.1 \
    opentelemetry-instrumentation-threading==0.66b1 \
    opentelemetry-instrumentation==0.66b1 \
    opentelemetry-sdk==1.45.1 \
    opentelemetry-semantic-conventions==0.66b1 \
    packaging==26.3 \
    pathspec==1.1.1 \
    pillow==12.3.0 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    propcache==0.5.4 \
    pycparser==3.11 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    PyJWT==2.15.1 \
    pytest-asyncio==1.4.0 \
    pytest-cov==7.1.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    python-multipart==0.0.32 \
    PyYAML==6.0.3 \
    referencing==0.37.0 \
    requests==2.34.2 \
    responses==0.26.3 \
    rich==14.3.4 \
    rpds-py==2026.9.1 \
    ruff==0.17.0 \
    s3transfer==0.19.2 \
    six==1.17.0 \
    slack_bolt==1.30.0 \
    slack_sdk==3.45.0 \
    soupsieve==2.10 \
    sse-starlette==3.5.0 \
    starlette==1.7.0 \
    strands-agents-evals==1.5.0 \
    strands-agents-tools==0.8.9 \
    strands-agents==1.59.0 \
    sympy==1.14.0 \
    tenacity==9.2.1 \
    truststore==0.10.4 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    uvicorn==0.54.0 \
    watchdog==6.0.0 \
    wcwidth==0.9.2 \
    websockets==17.2 \
    Werkzeug==3.1.9 \
    wrapt==2.5.0 \
    xmltodict==1.0.4 \
    yarl==1.25.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
