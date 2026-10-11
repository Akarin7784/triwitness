# Aunsiels__pyformlang-35（Aunsiels/pyformlang @ 04d769ab7da4）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Aunsiels/pyformlang/archive/04d769ab7da44a7ae80eec49661c0b03fdcd0bac.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    exceptiongroup==1.3.1 \
    iniconfig==2.1.0 \
    networkx==3.2.1 \
    numpy==2.0.2 \
    packaging==26.3 \
    pluggy==1.6.0 \
    pydot==4.0.1 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest==8.4.2 \
    tomli==2.5.0 \
    typing_extensions==4.16.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
