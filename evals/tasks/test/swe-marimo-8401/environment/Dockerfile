# marimo-team__marimo-8401（marimo-team/marimo @ ba84c0f36252）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/marimo-team/marimo/archive/ba84c0f362524945984df58ce94715737e967794.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    anyio==4.15.1 \
    anywidget==0.11.0 \
    asttokens==3.0.2 \
    attrs==26.1.0 \
    click==8.5.0 \
    comm==0.2.3 \
    dirty-equals==0.11 \
    docutils==0.23 \
    executing==2.2.1 \
    fastjsonschema==2.22.2 \
    h11==0.16.0 \
    hypothesis==6.168.5 \
    idna==3.20 \
    iniconfig==2.3.1 \
    inline-snapshot==0.36.0 \
    ipython==9.17.1 \
    ipython_pygments_lexers==1.1.1 \
    ipywidgets==8.1.9 \
    itsdangerous==2.2.0 \
    jedi==0.20.0 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    jupyter_core==5.9.1 \
    jupyterlab_widgets==3.0.17 \
    loro==1.16.2 \
    markdown-it-py==4.2.0 \
    Markdown==3.11 \
    matplotlib-inline==0.2.2 \
    mdurl==0.1.2 \
    msgspec==0.22.0 \
    narwhals==2.27.1 \
    nbformat==5.11.1 \
    packaging==26.3 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    psutil==7.2.2 \
    psygnal==0.16.1 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    Pygments==2.21.0 \
    pymdown-extensions==10.21.3 \
    pytest-asyncio==1.4.0 \
    pytest-timeout==2.4.0 \
    pytest==9.1.1 \
    PyYAML==6.0.3 \
    referencing==0.37.0 \
    rich==15.0.0 \
    rpds-py==2026.9.1 \
    sortedcontainers==2.4.0 \
    stack-data==0.6.3 \
    starlette==1.7.0 \
    tomlkit==0.15.1 \
    traitlets==5.16.1 \
    typing_extensions==4.16.0 \
    uvicorn==0.54.0 \
    wcwidth==0.9.2 \
    websockets==17.2 \
    widgetsnbextension==4.0.16
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
