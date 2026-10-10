# Parquery__icontract-297（Parquery/icontract @ 577b5031e054）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Parquery/icontract/archive/577b5031e0542d4960745051b8138b1a861b1bd2.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    astor==0.8.1 \
    astroid==2.15.8 \
    asttokens==2.4.1 \
    asyncstdlib==3.9.1 \
    autodocsumm==0.2.14 \
    babel==2.17.0 \
    black==23.9.1 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    chardet==5.2.0 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    colorama==0.4.6 \
    coverage==6.5.0 \
    deal==4.24.5 \
    dill==0.3.9 \
    distlib==0.3.9 \
    docutils==0.18.1 \
    dpcontracts==0.6.0 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isort==5.13.2 \
    Jinja2==3.1.6 \
    lazy-object-proxy==1.10.0 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    mypy-extensions==1.0.0 \
    mypy==1.5.1 \
    numpy==1.26.4 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    py-cpuinfo==5.0.0 \
    pydocstyle==6.3.0 \
    Pygments==2.19.1 \
    pylint==2.17.5 \
    pyproject-api==1.9.0 \
    pytest==8.3.5 \
    requests==2.32.3 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    sphinx-autodoc-typehints==1.23.0 \
    sphinx-rtd-theme==1.3.0 \
    Sphinx==5.3.0 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tabulate==0.9.0 \
    tomli==2.2.1 \
    tomlkit==0.13.2 \
    tox==4.25.0 \
    typeguard==4.4.2 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    wrapt==1.17.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
