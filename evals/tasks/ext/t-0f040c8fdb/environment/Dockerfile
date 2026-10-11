# Textualize__textual-441（Textualize/textual @ efafbdfcc16f）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Textualize/textual/archive/efafbdfcc16fdd3c7e9b5906fc7d8cc6e354f70e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohttp==3.8.1 \
    aiosignal==1.2.0 \
    async-timeout==4.0.2 \
    attrs==21.4.0 \
    black==22.3.0 \
    cfgv==3.3.1 \
    charset-normalizer==2.0.12 \
    click==8.1.2 \
    commonmark==0.9.1 \
    coverage==6.3.2 \
    distlib==0.3.4 \
    exceptiongroup==1.2.2 \
    filelock==3.6.0 \
    frozenlist==1.3.0 \
    ghp-import==2.0.2 \
    identify==2.4.12 \
    idna==3.3 \
    importlib-metadata==4.11.3 \
    iniconfig==1.1.1 \
    Jinja2==3.1.1 \
    lockfile==0.12.2 \
    Markdown==3.3.6 \
    MarkupSafe==2.1.1 \
    mergedeep==1.3.4 \
    mkdocs-autorefs==0.4.1 \
    mkdocs-material-extensions==1.0.3 \
    mkdocs-material==7.3.6 \
    mkdocs==1.3.0 \
    mkdocstrings==0.17.0 \
    multidict==6.0.2 \
    mypy-extensions==0.4.3 \
    mypy==0.931 \
    nodeenv==1.6.0 \
    packaging==21.3 \
    pathspec==0.9.0 \
    platformdirs==2.5.2 \
    pluggy==1.0.0 \
    pre-commit==2.18.1 \
    py==1.11.0 \
    Pygments==2.11.2 \
    pymdown-extensions==9.3 \
    pyparsing==3.0.8 \
    pytest-aiohttp==1.0.4 \
    pytest-asyncio==0.18.3 \
    pytest-cov==2.12.1 \
    pytest==6.2.5 \
    python-dateutil==2.8.2 \
    pytkdocs==0.16.1 \
    PyYAML==6.0 \
    pyyaml_env_tag==0.1 \
    rich==12.1.0 \
    six==1.16.0 \
    time-machine==2.6.0 \
    toml==0.10.2 \
    tomli==2.0.1 \
    typing-extensions==3.10.0.2 \
    virtualenv==20.14.1 \
    watchdog==2.1.7 \
    webencodings==0.5.1 \
    yarl==1.7.2 \
    zipp==3.8.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
