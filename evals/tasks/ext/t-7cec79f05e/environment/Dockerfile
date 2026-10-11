# canopen-python__canopen-613（canopen-python/canopen @ 593f0621f41c）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/canopen-python/canopen/archive/593f0621f41ce3f94c09322ca8414c7e649b128e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==26.1.0 \
    canmatrix==1.2 \
    click==8.5.0 \
    coverage==7.16.2 \
    iniconfig==2.3.1 \
    librt==0.16.0 \
    mypy==1.20.2 \
    mypy_extensions==1.1.0 \
    packaging==26.3 \
    pathspec==1.1.1 \
    pluggy==1.6.0 \
    Pygments==2.21.0 \
    pytest-cov==5.0.0 \
    pytest==8.4.2 \
    python-can==4.6.1 \
    typing_extensions==4.16.0 \
    wrapt==1.17.3
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
