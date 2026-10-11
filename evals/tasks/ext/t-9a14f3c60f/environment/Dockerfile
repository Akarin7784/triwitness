# burnash__gspread-1415（burnash/gspread @ 4a48fbdc4bc5）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/burnash/gspread/archive/4a48fbdc4bc56724d3a1d8fcdb7f5793fb58f160.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    apeye-core==1.1.5 \
    apeye==1.4.1 \
    autodocsumm==0.2.14 \
    babel==2.17.0 \
    bandit==1.7.5 \
    beautifulsoup4==4.13.3 \
    black==23.3.0 \
    CacheControl==0.14.2 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    codespell==2.2.5 \
    cssutils==2.11.1 \
    dict2css==0.3.0.post1 \
    docutils==0.19 \
    domdf_python_tools==3.10.0 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flake8==6.0.0 \
    gitdb==4.0.12 \
    GitPython==3.1.44 \
    google-auth-oauthlib==1.2.1 \
    google-auth==2.15.0 \
    html5lib==1.1 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isort==5.12.0 \
    Jinja2==3.1.6 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    mdurl==0.1.2 \
    more-itertools==10.6.0 \
    msgpack==1.1.0 \
    multidict==6.2.0 \
    mypy-extensions==1.0.0 \
    mypy==1.6.1 \
    natsort==8.4.0 \
    oauthlib==3.2.2 \
    packaging==24.2 \
    pathspec==0.12.1 \
    pbr==6.1.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    propcache==0.3.1 \
    pyasn1==0.6.1 \
    pyasn1_modules==0.4.2 \
    pycodestyle==2.10.0 \
    pyflakes==3.0.1 \
    Pygments==2.19.1 \
    pytest-vcr==1.0.2 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    requests-oauthlib==2.0.0 \
    requests==2.32.3 \
    rich==14.0.0 \
    rsa==4.9 \
    ruamel.yaml.clib==0.2.12 \
    ruamel.yaml==0.18.10 \
    six==1.17.0 \
    smmap==5.0.2 \
    snowballstemmer==2.2.0 \
    soupsieve==2.6 \
    sphinx-autodoc-typehints==1.23.0 \
    sphinx-jinja2-compat==0.3.0 \
    sphinx-prompt==1.6.0 \
    sphinx-rtd-theme==3.0.2 \
    sphinx-tabs==3.4.5 \
    sphinx-toolbox==3.9.0 \
    Sphinx==6.2.1 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    stevedore==5.4.1 \
    StrEnum==0.4.15 \
    tabulate==0.9.0 \
    tomli==2.2.1 \
    typing_extensions==4.8.0 \
    urllib3==1.26.15 \
    vcrpy==7.0.0 \
    webencodings==0.5.1 \
    wrapt==1.17.2 \
    yarl==1.18.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
