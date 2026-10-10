# sqlfluff__sqlfluff-7615（sqlfluff/sqlfluff @ 14d78ec8b330）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/sqlfluff/sqlfluff/archive/14d78ec8b330821ba3bc06c70f0847a95ba9ceeb.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    anyio==4.15.1 \
    ast_serialize==0.12.1 \
    cachetools==7.2.1 \
    certifi==2026.7.22 \
    chardet==7.6.0 \
    charset-normalizer==3.5.2 \
    click==8.3.3 \
    colorama==0.4.6 \
    coverage==7.16.2 \
    diff_cover==10.6.0 \
    distlib==0.4.3 \
    doc8==2.0.0 \
    docutils==0.21.2 \
    execnet==2.1.2 \
    fastcore==2.2.33 \
    fastspec==0.2.5 \
    fasttransport==0.0.4 \
    filelock==4.1.0 \
    ghapi==2.1.4 \
    grimp==3.17 \
    h11==0.16.0 \
    httpcore2==2.13.1 \
    httpx2==2.13.1 \
    hypothesis==6.168.5 \
    idna==3.20 \
    import-linter==2.15 \
    iniconfig==2.3.1 \
    Jinja2==3.1.6 \
    librt==0.16.0 \
    markdown-it-py==4.2.0 \
    MarkupSafe==3.0.4 \
    mdurl==0.1.2 \
    mypy==2.4.0 \
    mypy_extensions==1.1.0 \
    packaging==26.3 \
    pathspec==1.1.1 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    Pygments==2.21.0 \
    pyproject-api==1.11.4 \
    pytest-cov==7.1.0 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    python-discovery==1.6.2 \
    PyYAML==6.0.3 \
    regex==2026.9.29 \
    requests==2.34.2 \
    restructuredtext_lint==2.0.2 \
    rich==15.0.0 \
    ruff==0.17.0 \
    setuptools==84.0.0 \
    sortedcontainers==2.4.0 \
    stevedore==5.9.1 \
    tblib==3.2.2 \
    tomli_w==1.2.0 \
    tox==4.65.1 \
    tqdm==4.70.1 \
    truststore==0.10.4 \
    types-appdirs==1.4.3.5 \
    types-chardet==5.0.4.6 \
    types-colorama==0.4.15.20260508 \
    types-PyYAML==6.0.12.20260906 \
    types-regex==2026.9.29.20261005 \
    types-tqdm==4.70.0.20260906 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    virtualenv==21.14.6 \
    yamllint==1.38.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
