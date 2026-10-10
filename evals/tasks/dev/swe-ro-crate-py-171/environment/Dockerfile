# ResearchObject__ro-crate-py-171（ResearchObject/ro-crate-py @ 42aeed481d1c）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/ResearchObject/ro-crate-py/archive/42aeed481d1c14dab3eaef00c90db7a9a30caf9e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    aiohappyeyeballs==2.6.1 \
    aiohttp==3.11.14 \
    aiosignal==1.3.2 \
    arcp==0.2.1 \
    async-timeout==5.0.1 \
    attrs==25.3.0 \
    bioblend==1.5.0 \
    CacheControl==0.14.2 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    frozenlist==1.5.0 \
    galaxy2cwl==0.1.4 \
    gxformat2==0.20.0 \
    idna==3.10 \
    iniconfig==2.1.0 \
    isodate==0.7.2 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mistune==3.0.2 \
    msgpack==1.1.0 \
    multidict==6.2.0 \
    mypy-extensions==1.0.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    propcache==0.3.1 \
    pyparsing==3.2.3 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.2 \
    rdflib==7.1.4 \
    requests-toolbelt==1.0.0 \
    requests==2.32.3 \
    ruamel.yaml.clib==0.2.12 \
    ruamel.yaml==0.18.10 \
    schema-salad==8.8.20250205075315 \
    six==1.17.0 \
    tinydb==4.8.2 \
    tomli==2.2.1 \
    tuspy==1.1.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    yarl==1.18.3
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
