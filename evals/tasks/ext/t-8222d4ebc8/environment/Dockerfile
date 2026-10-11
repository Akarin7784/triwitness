# EvoluxBR__greenswitch-83（EvoluxBR/greenswitch @ eb210f31ff72）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/EvoluxBR/greenswitch/archive/eb210f31ff723bba75d83b09d898f7e1273eb63b.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    coverage==7.8.0 \
    exceptiongroup==1.2.2 \
    gevent==24.11.1 \
    gprof2dot==2024.6.6 \
    greenlet==3.1.1 \
    iniconfig==2.1.0 \
    mock==5.2.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pytest-cov==6.0.0 \
    pytest-profiling==1.8.1 \
    pytest-spec==4.0.0 \
    pytest==8.3.5 \
    six==1.17.0 \
    tomli==2.2.1 \
    zope.event==5.0 \
    zope.interface==7.2
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
