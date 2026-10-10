# PyCQA__flake8-bugbear-424（PyCQA/flake8-bugbear @ 907e0dd29a99）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/PyCQA/flake8-bugbear/archive/907e0dd29a99818591a604d4557c70ea33204712.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    cachetools==5.5.2 \
    cfgv==3.4.0 \
    chardet==5.2.0 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    distlib==0.3.9 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flake8==7.2.0 \
    hypothesis==6.130.6 \
    hypothesmith==0.3.3 \
    identify==2.6.9 \
    iniconfig==2.1.0 \
    lark==1.2.2 \
    libcst==1.7.0 \
    mccabe==0.7.0 \
    nodeenv==1.9.1 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pre_commit==4.2.0 \
    pycodestyle==2.13.0 \
    pyflakes==3.3.2 \
    pyproject-api==1.9.0 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    sortedcontainers==2.4.0 \
    tomli==2.2.1 \
    tox==4.25.0 \
    typing_extensions==4.13.0 \
    virtualenv==20.29.3
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
