# brightway-lca__brightway2-io-294（brightway-lca/brightway2-io @ 774b44635cbf）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/brightway-lca/brightway2-io/archive/774b44635cbfcc833dd0a40e803ef66e0b204630.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.7.0 \
    asteval==1.0.6 \
    astroid==3.3.9 \
    astunparse==1.6.3 \
    blinker==1.9.0 \
    build==1.2.2.post1 \
    bw-migrations==0.2 \
    bw2calc==2.0.2 \
    bw2data==4.4.3 \
    bw2parameters==1.1.0 \
    bw_processing==1.0 \
    certifi==2025.1.31 \
    cfgv==3.4.0 \
    charset-normalizer==3.4.1 \
    coverage==7.8.0 \
    deepdiff==7.0.1 \
    Deprecated==1.2.18 \
    dill==0.3.9 \
    distlib==0.3.9 \
    et_xmlfile==2.0.0 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flexcache==0.3 \
    flexparser==0.4 \
    fsspec==2025.3.2 \
    identify==2.6.9 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isodate==0.7.2 \
    isort==6.0.1 \
    loguru==0.7.3 \
    lxml==5.3.1 \
    matrix_utils==0.6 \
    mccabe==0.7.0 \
    morefs==0.2.2 \
    mrio-common-metadata==0.2.1 \
    nodeenv==1.9.1 \
    numpy==1.26.4 \
    openpyxl==3.1.5 \
    ordered-set==4.1.0 \
    packaging==24.2 \
    pandas==2.2.3 \
    peewee==3.17.9 \
    Pint==0.24.4 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pre_commit==4.2.0 \
    pydantic-settings==2.8.1 \
    pydantic==2.11.2 \
    pydantic_core==2.33.1 \
    pyecospold==4.0.0 \
    pylint==3.3.6 \
    pyparsing==3.2.3 \
    pyproject_hooks==1.2.0 \
    pytest-cov==6.1.0 \
    pytest-randomly==3.16.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    python-dotenv==1.1.0 \
    pytz==2025.2 \
    pyxlsb==1.0.10 \
    PyYAML==6.0.2 \
    randonneur==0.6.1 \
    randonneur_data==0.6 \
    RapidFuzz==3.13.0 \
    rdflib==7.1.4 \
    requests==2.32.3 \
    scipy==1.13.1 \
    six==1.17.0 \
    snowflake-id==1.0.2 \
    SPARQLWrapper==2.0.0 \
    stats_arrays==0.7 \
    structlog==25.2.0 \
    tomli==2.2.1 \
    tomlkit==0.13.2 \
    tqdm==4.67.1 \
    typing-inspection==0.4.0 \
    typing_extensions==4.13.1 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    virtualenv==20.30.0 \
    voluptuous==0.15.2 \
    wrapt==1.17.2 \
    xlrd==2.0.1 \
    XlsxWriter==3.2.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
