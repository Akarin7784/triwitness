# lincc-frameworks__nested-pandas-302（lincc-frameworks/nested-pandas @ 1eeda4bafab0）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/lincc-frameworks/nested-pandas/archive/1eeda4bafab06582e90b1266a36f6923ccf31fdc.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    jupyter_server==2.21.1 \
    jupyter_server_terminals==0.5.4 \
    jupyterlab==4.6.4 \
    jupyterlab_pygments==0.3.0 \
    jupyterlab_server==2.28.1 \
    jupyterlab_widgets==3.0.17 \
    lark==1.3.1 \
    librt==0.16.0 \
    MarkupSafe==3.0.4 \
    matplotlib-inline==0.2.2 \
    mistune==3.3.4 \
    multidict==7.1.0 \
    mypy==2.4.0 \
    mypy_extensions==1.1.0 \
    nbclient==0.11.0 \
    nbconvert==7.17.1 \
    nbformat==5.11.1 \
    nest-asyncio2==1.7.4 \
    nodeenv==1.11.0 \
    notebook==7.6.3 \
    notebook_shim==0.2.4 \
    numpy==2.4.6 \
    overrides==7.7.0 \
    packaging==26.3 \
    pandas==2.3.3 \
    pandocfilters==1.5.1 \
    parso==0.8.7 \
    pathlib_abc==0.5.2 \
    pathspec==1.1.1 \
    pexpect==4.9.0 \
    platformdirs==4.13.0 \
    pluggy==1.6.0 \
    pre_commit==4.6.2 \
    prometheus_client==0.26.0 \
    prompt_toolkit==3.0.53 \
    propcache==0.5.4 \
    psutil==7.2.2 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    pyarrow==26.0.0 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    Pympler==1.1 \
    pyproject_hooks==1.3.3 \
    pytest-cov==7.1.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    python-discovery==1.6.2 \
    python-json-logger==4.2.0 \
    pytz==2026.5 \
    PyYAML==6.0.3 \
    pyzmq==27.2.0 \
    referencing==0.37.0 \
    requests==2.34.2 \
    rfc3339-validator==0.1.4 \
    rfc3986-validator==0.1.1 \
    rfc3987-syntax==1.1.0 \
    rpds-py==2026.9.1 \
    ruff==0.17.0 \
    Send2Trash==2.1.0 \
    six==1.17.0 \
    soupsieve==3.0.1 \
    stack-data==0.6.3 \
    tabulate==0.10.0 \
    terminado==0.18.1 \
    tinycss2==1.5.1 \
    tornado==6.5.10 \
    traitlets==5.16.1 \
    typing_extensions==4.16.0 \
    tzdata==2026.5 \
    universal_pathlib==0.3.10 \
    uri-template==1.3.0 \
    urllib3==2.8.0 \
    virtualenv==21.14.6 \
    wcwidth==0.9.2 \
    webcolors==25.10.0 \
    webencodings==0.6.1 \
    websocket-client==1.9.2 \
    widgetsnbextension==4.0.16 \
    yarl==1.25.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
