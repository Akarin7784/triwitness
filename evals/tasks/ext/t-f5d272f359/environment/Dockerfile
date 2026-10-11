# aio-libs__aiocache-795（aio-libs/aiocache @ a6a131ecd338）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/aio-libs/aiocache/archive/a6a131ecd33862a3406d03514e9e1031612301ef.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohttp==3.8.3 \
    aiomcache==0.8.0 \
    aiosignal==1.3.2 \
    async-timeout==4.0.3 \
    attrs==25.3.0 \
    charset-normalizer==2.1.1 \
    coverage==7.8.0 \
    exceptiongroup==1.2.2 \
    frozenlist==1.5.0 \
    idna==3.10 \
    iniconfig==2.1.0 \
    marshmallow==3.19.0 \
    msgpack==1.0.4 \
    multidict==6.2.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    propcache==0.3.1 \
    pytest-asyncio==0.20.3 \
    pytest-cov==4.0.0 \
    pytest-mock==3.10.0 \
    pytest==7.2.0 \
    redis==4.4.2 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    yarl==1.18.3
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
