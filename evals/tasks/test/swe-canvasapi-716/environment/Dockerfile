# ucfopen__canvasapi-716（ucfopen/canvasapi @ 77ff5b248603）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/ucfopen/canvasapi/archive/77ff5b248603db987e57f11a104767d4b790265a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    arrow==1.4.0 \
    black==25.1.0 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    click==8.5.0 \
    coverage==7.16.2 \
    flake8==7.4.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    isort==9.0.2 \
    mccabe==0.7.0 \
    mypy_extensions==1.1.0 \
    packaging==26.3 \
    pathspec==1.1.1 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    pycodestyle==2.15.0 \
    pyflakes==4.0.3 \
    Pygments==2.21.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    pytz==2026.5 \
    requests-mock==1.12.1 \
    requests==2.34.2 \
    six==1.17.0 \
    tzdata==2026.5 \
    urllib3==2.8.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
