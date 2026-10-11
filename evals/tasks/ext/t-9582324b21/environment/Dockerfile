# alexgolec__tda-api-105（alexgolec/tda-api @ 8e4897d378b2）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/alexgolec/tda-api/archive/8e4897d378b20dfd9fd14abf354902a8414f48e7.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    attrs==25.3.0 \
    babel==2.17.0 \
    backports.tarfile==1.2.0 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    charset-normalizer==3.4.1 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    h11==0.14.0 \
    id==1.5.0 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.0.1 \
    jaraco.functools==4.1.0 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    keyring==25.6.0 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    mdurl==0.1.2 \
    more-itertools==10.6.0 \
    nh3==0.2.21 \
    nose==1.3.7 \
    oauthlib==3.2.2 \
    outcome==1.3.0.post0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pycparser==2.22 \
    Pygments==2.19.1 \
    PySocks==1.7.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    readme_renderer==44.0 \
    requests-oauthlib==2.0.0 \
    requests-toolbelt==1.0.0 \
    requests==2.32.3 \
    rfc3986==2.0.0 \
    rich==14.0.0 \
    SecretStorage==3.3.3 \
    selenium==4.30.0 \
    six==1.17.0 \
    sniffio==1.3.1 \
    snowballstemmer==2.2.0 \
    sortedcontainers==2.4.0 \
    sphinx-rtd-theme==3.0.2 \
    Sphinx==7.4.7 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tomli==2.2.1 \
    trio-websocket==0.12.2 \
    trio==0.29.0 \
    twine==6.1.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    websocket-client==1.8.0 \
    websockets==15.0.1 \
    wsproto==1.2.0 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
