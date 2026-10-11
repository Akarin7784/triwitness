# brightway-lca__brightway2-data-235（brightway-lca/brightway2-data @ f9f36639f263）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/brightway-lca/brightway2-data/archive/f9f36639f2637e4cb9f033d44e2acd7cf59fe026.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.7.0 \
    asteval==1.0.6 \
    astroid==3.3.9 \
    astunparse==1.6.3 \
    blinker==1.9.0 \
    build==1.2.2.post1 \
    bw2parameters==1.1.0 \
    bw_processing==1.0 \
    cfgv==3.4.0 \
    coverage==7.8.0 \
    deepdiff==7.0.1 \
    Deprecated==1.2.18 \
    dill==0.3.9 \
    distlib==0.3.9 \
    filelock==3.18.0 \
    flexcache==0.3 \
    flexparser==0.4 \
    fsspec==2025.3.2 \
    identify==2.6.9 \
    importlib_metadata==8.6.1 \
    isort==6.0.1 \
    lxml==5.3.1 \
    mccabe==0.7.0 \
    morefs==0.2.2 \
    nodeenv==1.9.1 \
    numpy==1.26.4 \
    ordered-set==4.1.0 \
    pandas==2.2.3 \
    peewee==3.17.9 \
    Pint==0.24.4 \
    platformdirs==4.3.7 \
    pre_commit==4.2.0 \
    pydantic-settings==2.8.1 \
    pydantic==2.11.2 \
    pydantic_core==2.33.1 \
    pylint==3.3.6 \
    pyproject_hooks==1.2.0 \
    pytest-cov==6.1.0 \
    pytest-randomly==3.16.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    python-dotenv==1.1.0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    RapidFuzz==3.13.0 \
    scipy==1.13.1 \
    six==1.17.0 \
    snowflake-id==1.0.2 \
    stats_arrays==0.7 \
    structlog==25.2.0 \
    tomlkit==0.13.2 \
    tqdm==4.67.1 \
    typing-inspection==0.4.0 \
    typing_extensions==4.13.1 \
    tzdata==2025.2 \
    virtualenv==20.30.0 \
    voluptuous==0.15.2 \
    wrapt==1.17.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
