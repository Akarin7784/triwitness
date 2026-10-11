# capitalone__datacompy-335（capitalone/datacompy @ 60c52d2d5d8b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/capitalone/datacompy/archive/60c52d2d5d8b1f93954cb979228978c895d2774a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    adagio==0.2.6 \
    alabaster==0.7.16 \
    antlr4-python3-runtime==4.11.1 \
    appdirs==1.4.4 \
    babel==2.17.0 \
    backports.tarfile==1.2.0 \
    beautifulsoup4==4.13.3 \
    build==1.2.2.post1 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    cfgv==3.4.0 \
    charset-normalizer==3.4.1 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    duckdb==1.2.1 \
    filelock==3.18.0 \
    findspark==2.0.1 \
    fs==2.4.16 \
    fsspec==2025.3.1 \
    fugue-sql-antlr==0.2.2 \
    fugue==0.9.1 \
    furo==2024.8.6 \
    googleapis-common-protos==1.69.2 \
    grpcio-status==1.71.0 \
    grpcio==1.71.0 \
    id==1.5.0 \
    identify==2.6.9 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.0.1 \
    jaraco.functools==4.1.0 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    keyring==25.6.0 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    mdit-py-plugins==0.4.2 \
    mdurl==0.1.2 \
    more-itertools==10.6.0 \
    mypy-extensions==1.0.0 \
    mypy==1.15.0 \
    myst-parser==3.0.1 \
    nh3==0.2.21 \
    nodeenv==1.9.1 \
    numpy==1.26.4 \
    ordered-set==4.1.0 \
    pandas-stubs==2.2.2.240807 \
    pandas==2.2.2 \
    platformdirs==4.3.7 \
    polars==1.6.0 \
    pre_commit==4.2.0 \
    protobuf==5.29.4 \
    py4j==0.10.9.7 \
    pyarrow==19.0.1 \
    pycparser==2.22 \
    Pygments==2.19.1 \
    pyproject_hooks==1.2.0 \
    pyspark==3.5.5 \
    pytest-cov==6.0.0 \
    pytest-spark==0.7.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    qpd==0.4.4 \
    readme_renderer==44.0 \
    requests-toolbelt==1.0.0 \
    requests==2.32.3 \
    rfc3986==2.0.0 \
    rich==14.0.0 \
    ruff==0.5.7 \
    SecretStorage==3.3.3 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    soupsieve==2.6 \
    sphinx-basic-ng==1.0.0b2 \
    Sphinx==7.4.7 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    sqlglot==26.12.0 \
    triad==0.9.8 \
    twine==6.1.0 \
    types-pytz==2025.2.0.20250326 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
