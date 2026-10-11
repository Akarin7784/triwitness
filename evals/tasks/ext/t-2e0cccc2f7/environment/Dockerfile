# altair-viz__altair-3128（altair-viz/altair @ 72a361c68731）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/altair-viz/altair/archive/72a361c68731212d8aa042f4c73d5070aa110a9a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    altair-data-server==0.4.1 \
    anyio==4.9.0 \
    arro3-core==0.4.6 \
    asttokens==3.0.0 \
    attrs==25.3.0 \
    backports.tarfile==1.2.0 \
    black==23.12.1 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    click==8.1.8 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    decorator==5.2.1 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    execnet==2.1.1 \
    executing==2.2.0 \
    filelock==3.18.0 \
    h11==0.14.0 \
    hatch==1.14.0 \
    hatchling==1.27.0 \
    httpcore==1.0.7 \
    httpx==0.28.1 \
    hyperlink==21.0.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    ipython==8.18.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.0.1 \
    jaraco.functools==4.1.0 \
    jedi==0.19.2 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    keyring==25.6.0 \
    m2r==0.3.1 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    matplotlib-inline==0.1.7 \
    mdurl==0.1.2 \
    mistune==0.8.4 \
    more-itertools==10.6.0 \
    mypy-extensions==1.0.0 \
    mypy==1.15.0 \
    narwhals==1.32.0 \
    numpy==2.0.2 \
    pandas-stubs==2.2.2.240807 \
    pandas==2.2.3 \
    parso==0.8.4 \
    pathspec==0.12.1 \
    pexpect==4.9.0 \
    platformdirs==4.3.7 \
    portpicker==1.6.0 \
    prompt_toolkit==3.0.50 \
    psutil==7.0.0 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.3 \
    pyarrow==19.0.1 \
    pycparser==2.22 \
    Pygments==2.19.1 \
    pytest-asyncio==0.26.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest-xdist==3.6.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    referencing==0.36.2 \
    rich==14.0.0 \
    rpds-py==0.24.0 \
    ruff==0.11.2 \
    SecretStorage==3.3.3 \
    shellingham==1.5.4 \
    six==1.17.0 \
    sniffio==1.3.1 \
    stack-data==0.6.3 \
    tomli_w==1.2.0 \
    tomlkit==0.13.2 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    traitlets==5.14.3 \
    trove-classifiers==2025.3.19.19 \
    types-jsonschema==4.23.0.20241208 \
    types-pytz==2025.2.0.20250326 \
    types-setuptools==78.1.0.20250329 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    userpath==1.9.2 \
    uv==0.6.11 \
    vega-datasets==0.9.0 \
    vegafusion==2.0.2 \
    virtualenv==20.29.3 \
    vl-convert-python==1.7.0 \
    wcwidth==0.2.13 \
    zipp==3.21.0 \
    zstandard==0.23.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
