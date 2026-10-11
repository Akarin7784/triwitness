# auth0__auth0-python-499（auth0/auth0-python @ 53c326a8e482）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/auth0/auth0-python/archive/53c326a8e4828c4f552169e6167c7f2f8aa46205.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohappyeyeballs==2.6.1 \
    aiohttp==3.11.14 \
    aioresponses==0.7.8 \
    aiosignal==1.3.2 \
    alabaster==0.7.16 \
    async-timeout==5.0.1 \
    attrs==25.3.0 \
    babel==2.17.0 \
    black==25.1.0 \
    callee==0.3.1 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    cfgv==3.4.0 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flake8==7.2.0 \
    frozenlist==1.5.0 \
    identify==2.6.9 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isort==6.0.1 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    mistune==3.1.3 \
    mock==5.2.0 \
    multidict==6.2.0 \
    mypy-extensions==1.0.0 \
    nodeenv==1.9.1 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pre_commit==4.2.0 \
    propcache==0.3.1 \
    pycodestyle==2.13.0 \
    pycparser==2.22 \
    pyflakes==3.3.1 \
    Pygments==2.19.1 \
    PyJWT==2.10.1 \
    pytest-mock==3.14.0 \
    pytest==8.3.5 \
    pyupgrade==3.19.1 \
    PyYAML==6.0.2 \
    requests==2.32.3 \
    snowballstemmer==2.2.0 \
    sphinx-rtd-theme==3.0.2 \
    Sphinx==7.4.7 \
    sphinx_mdinclude==0.6.2 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tokenize_rt==6.1.0 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    yarl==1.18.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
