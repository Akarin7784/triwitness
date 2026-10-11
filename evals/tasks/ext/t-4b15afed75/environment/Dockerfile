# amjith__fuzzyfinder-19（amjith/fuzzyfinder @ 43fe7676cad6）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/amjith/fuzzyfinder/archive/43fe7676cad68e269bbace7bb2fd9b77f2e07da9.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    coverage==7.8.0 \
    coveralls==4.0.1 \
    docopt==0.6.2 \
    exceptiongroup==1.2.2 \
    idna==3.10 \
    iniconfig==2.1.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    requests==2.32.3 \
    tomli==2.2.1 \
    urllib3==2.3.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
