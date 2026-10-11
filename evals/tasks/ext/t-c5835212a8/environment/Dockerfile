# burnash__gspread-1336（burnash/gspread @ 25499bfd9e5b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/burnash/gspread/archive/25499bfd9e5b5745bb8f47bd24e9da4301f8cf1a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    apeye-core==1.1.5 \
    apeye==1.4.1 \
    autodocsumm==0.2.14 \
    babel==2.17.0 \
    beautifulsoup4==4.13.3 \
    CacheControl==0.14.2 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    coverage==7.8.0 \
    cssutils==2.11.1 \
    dict2css==0.3.0.post1 \
    docutils==0.19 \
    domdf_python_tools==3.10.0 \
    exceptiongroup==1.2.2 \
    execnet==2.1.1 \
    filelock==3.18.0 \
    google-auth-oauthlib==1.2.1 \
    google-auth==2.15.0 \
    html5lib==1.1 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    more-itertools==10.6.0 \
    msgpack==1.1.0 \
    multidict==6.2.0 \
    natsort==8.4.0 \
    oauthlib==3.2.2 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    propcache==0.3.1 \
    pyasn1==0.6.1 \
    pyasn1_modules==0.4.2 \
    Pygments==2.19.1 \
    pytest-asyncio==0.26.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest-vcr==1.0.2 \
    pytest-xdist==3.6.1 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    requests-oauthlib==2.0.0 \
    requests==2.32.3 \
    rsa==4.9 \
    ruamel.yaml.clib==0.2.12 \
    ruamel.yaml==0.18.10 \
    six==1.17.0 \
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
    StrEnum==0.4.15 \
    tabulate==0.9.0 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
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
