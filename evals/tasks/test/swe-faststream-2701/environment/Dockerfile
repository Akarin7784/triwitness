# ag2ai__faststream-2701（ag2ai/faststream @ 6ac6f967e847）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/ag2ai/faststream/archive/6ac6f967e847212803c119f3092a121ac7d9afef.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aio-pika==9.6.2 \
    aiokafka==0.12.0 \
    aiormq==6.9.4 \
    annotated-doc==0.0.5 \
    annotated-types==0.8.0 \
    anyio==4.15.1 \
    async-timeout==5.0.1 \
    certifi==2026.7.22 \
    click==8.5.0 \
    confluent-kafka==2.16.0 \
    covdefaults==2.3.0 \
    coverage==7.16.2 \
    dirty-equals==0.11 \
    dnspython==2.9.0 \
    email-validator==2.3.0 \
    execnet==2.1.2 \
    fast-depends==3.0.9 \
    fastapi==0.121.3 \
    h11==0.16.0 \
    httpcore==1.0.9 \
    httpx==0.28.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    markdown-it-py==4.2.0 \
    mdurl==0.1.2 \
    msgspec==0.22.0 \
    multidict==7.1.0 \
    nats-py==2.16.0 \
    opentelemetry-api==1.45.1 \
    opentelemetry-sdk==1.45.1 \
    opentelemetry-semantic-conventions==0.66b1 \
    packaging==26.3 \
    pamqp==3.3.0 \
    pluggy==1.6.0 \
    prometheus_client==0.26.0 \
    propcache==0.5.4 \
    psutil==7.1.3 \
    pydantic-settings==2.15.0 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-asyncio==1.3.0 \
    pytest-cov==7.1.0 \
    pytest-rerunfailures==16.7 \
    pytest-timeout==2.4.0 \
    pytest-xdist==3.8.0 \
    pytest==9.0.1 \
    python-dotenv==1.2.4 \
    PyYAML==6.0.3 \
    redis==7.4.1 \
    rich==15.0.0 \
    shellingham==1.5.4 \
    starlette==0.50.0 \
    typer==0.20.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    uv==0.13.0 \
    uvicorn==0.54.0 \
    uvloop==0.23.0 \
    watchfiles==1.1.1 \
    yarl==1.25.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
