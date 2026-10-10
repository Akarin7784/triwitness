# BrianPugh__cyclopts-633（BrianPugh/cyclopts @ 23fed053c63c）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/BrianPugh/cyclopts/archive/23fed053c63ca13e7ab28ca54e94804012d23946.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.8.0 \
    attrs==26.1.0 \
    cfgv==3.5.0 \
    coverage==7.16.2 \
    distlib==0.4.3 \
    docstring_parser==0.18.0 \
    docutils==0.23 \
    filelock==4.1.0 \
    identify==2.6.20 \
    idna==3.20 \
    iniconfig==2.3.1 \
    markdown-it-py==4.2.0 \
    mdurl==0.1.2 \
    nodeenv==1.11.0 \
    outcome==1.3.0.post0 \
    packaging==26.3 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    pre_commit==4.6.2 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-cov==7.1.0 \
    pytest-mock==3.16.0 \
    pytest==9.1.1 \
    python-discovery==1.6.2 \
    PyYAML==6.0.3 \
    rich-rst==1.3.2 \
    rich==15.0.0 \
    sniffio==1.3.1 \
    sortedcontainers==2.4.0 \
    toml==0.10.2 \
    trio==0.34.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    virtualenv==21.14.6
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
