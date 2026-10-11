# bodo-ai__PyDough-368（bodo-ai/PyDough @ bce6fc846fe7）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/bodo-ai/PyDough/archive/bce6fc846fe739fd8a9d913574aa4998b6cb5b73.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    h11==0.16.0 \
    httpcore==1.0.9 \
    httpx==0.28.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    ipykernel==7.4.0 \
    ipython==9.17.1 \
    ipython_pygments_lexers==1.1.1 \
    isoduration==20.11.0 \
    jedi==0.20.0 \
    Jinja2==3.1.6 \
    json5==0.17.3 \
    jsonpointer==3.2.1 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    jupyter-events==0.12.1 \
    jupyter-lsp==2.3.1 \
    jupyter_builder==1.2.3 \
    jupyter_client==8.10.0 \
    jupyter_core==5.9.1 \
    jupyter_server==2.21.1 \
    jupyter_server_terminals==0.5.4 \
    jupyterlab==4.6.4 \
    jupyterlab_pygments==0.3.0 \
    jupyterlab_server==2.28.1 \
    lark==1.3.1 \
    MarkupSafe==3.0.4 \
    matplotlib-inline==0.2.2 \
    mistune==3.3.4 \
    nbclient==0.11.0 \
    nbconvert==7.17.1 \
    nbformat==5.11.1 \
    nest-asyncio2==1.7.4 \
    notebook_shim==0.2.4 \
    numpy==2.4.6 \
    overrides==7.7.0 \
    packaging==26.3 \
    pandas==3.0.6 \
    pandocfilters==1.5.1 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    platformdirs==4.13.0 \
    pluggy==1.6.0 \
    prometheus_client==0.26.0 \
    prompt_toolkit==3.0.53 \
    psutil==7.2.2 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    pyarrow==26.0.0 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
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
    Send2Trash==2.1.0 \
    six==1.17.0 \
    soupsieve==3.0.1 \
    sqlglot==26.7.0 \
    stack-data==0.6.3 \
    terminado==0.18.1 \
    tinycss2==1.5.1 \
    tornado==6.5.10 \
    traitlets==5.16.1 \
    typing_extensions==4.16.0 \
    tzdata==2026.5 \
    uri-template==1.3.0 \
    urllib3==2.8.0 \
    wcwidth==0.9.2 \
    webcolors==25.10.0 \
    webencodings==0.6.1 \
    websocket-client==1.9.2
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
