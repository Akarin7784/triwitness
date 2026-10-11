# ipython__ipython-14695（ipython/ipython @ b8220b5b975e）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/ipython/ipython/archive/b8220b5b975e3f4e19d078033aa1e68da28e2c9b.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asttokens==3.0.2 \
    decorator==5.3.1 \
    executing==2.3.0 \
    iniconfig==2.3.1 \
    ipython_pygments_lexers==1.1.1 \
    jedi==0.20.0 \
    matplotlib-inline==0.2.2 \
    packaging==26.3 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    pickleshare==0.7.5 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    Pygments==2.21.0 \
    pytest-asyncio==0.21.2 \
    pytest==9.1.1 \
    stack-data==0.6.3 \
    testpath==0.6.0 \
    traitlets==5.16.1 \
    typing_extensions==4.16.0 \
    wcwidth==0.9.2
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
