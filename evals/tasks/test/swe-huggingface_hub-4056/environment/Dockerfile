# huggingface__huggingface_hub-4056（huggingface/huggingface_hub @ 6983a4d3d2bd）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/huggingface/huggingface_hub/archive/6983a4d3d2bdcbd09c6ea08acae64cdf83ccb2e4.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-doc==0.0.5 \
    annotated-types==0.8.0 \
    anyio==4.15.1 \
    Authlib==1.8.0 \
    certifi==2026.7.22 \
    cffi==2.1.1 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    duckdb==1.5.6 \
    execnet==2.1.2 \
    fastapi==0.143.0 \
    filelock==4.1.0 \
    fsspec==2026.9.0 \
    h11==0.16.0 \
    hf-xet==1.7.0 \
    httpcore==1.0.9 \
    httpx==0.28.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    itsdangerous==2.2.0 \
    jedi==0.20.0 \
    Jinja2==3.1.6 \
    joserfc==1.7.5 \
    markdown-it-py==4.2.0 \
    MarkupSafe==3.0.4 \
    mdurl==0.1.2 \
    numpy==2.5.3 \
    opentelemetry-api==1.45.1 \
    packaging==26.3 \
    parso==0.8.7 \
    pillow==12.3.0 \
    pluggy==1.6.0 \
    pycparser==3.11 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-asyncio==1.4.0 \
    pytest-cov==7.1.0 \
    pytest-env==1.7.1 \
    pytest-mock==3.16.0 \
    pytest-rerunfailures==15.1 \
    pytest-vcr==1.0.2 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    python-dotenv==1.2.4 \
    PyYAML==6.0.3 \
    rich==15.0.0 \
    shellingham==1.5.4 \
    soundfile==0.14.0 \
    starlette==1.7.0 \
    tqdm==4.70.1 \
    typer==0.27.3 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    urllib3==1.26.20 \
    vcrpy==8.3.0 \
    wrapt==2.5.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
