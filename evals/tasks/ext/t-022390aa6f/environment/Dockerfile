# dapr__python-sdk-402（dapr/python-sdk @ c57b872bcd26）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/dapr/python-sdk/archive/c57b872bcd263c5a856b8b0caf3e0075cde4fd92.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohappyeyeballs==2.6.1 \
    aiohttp==3.11.14 \
    aiosignal==1.3.2 \
    async-timeout==5.0.1 \
    attrs==25.3.0 \
    blinker==1.9.0 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    cloudevents==1.11.0 \
    codecov==2.1.13 \
    coverage==7.8.0 \
    deprecation==2.1.0 \
    distlib==0.3.9 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flake8==7.2.0 \
    Flask==3.1.0 \
    frozenlist==1.5.0 \
    google-api-core==2.10.1 \
    google-auth==2.38.0 \
    googleapis-common-protos==1.56.4 \
    grpcio-tools==1.48.2 \
    grpcio==1.71.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    itsdangerous==2.2.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    multidict==6.2.0 \
    mypy-extensions==1.0.0 \
    mypy-protobuf==3.3.0 \
    mypy==0.950 \
    opencensus-context==0.1.3 \
    opencensus-ext-grpc==0.7.2 \
    opencensus==0.9.0 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    propcache==0.3.1 \
    protobuf==3.20.1 \
    py==1.11.0 \
    pyasn1==0.6.1 \
    pyasn1_modules==0.4.2 \
    pycodestyle==2.13.0 \
    pyflakes==3.3.2 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    requests==2.32.3 \
    rsa==4.9 \
    six==1.16.0 \
    toml==0.10.2 \
    tomli==2.2.1 \
    tox==3.25.0 \
    types-protobuf==5.29.1.20250315 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    Werkzeug==3.1.3 \
    yarl==1.18.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
