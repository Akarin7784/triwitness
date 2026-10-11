# cwacek__python-jsonschema-objects-261（cwacek/python-jsonschema-objects @ 51c4a5f7226d）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/cwacek/python-jsonschema-objects/archive/51c4a5f7226d7172178869f442da45fb25872b0c.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    anyio==4.9.0 \
    attrs==25.3.0 \
    babel==2.17.0 \
    black==25.1.0 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    colorama==0.4.6 \
    commonmark==0.9.1 \
    coverage==7.8.0 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    h11==0.14.0 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    inflection==0.5.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    jsonschema==4.17.3 \
    Markdown==3.7 \
    MarkupSafe==3.0.2 \
    mypy-extensions==1.0.0 \
    packaging==24.2 \
    pandoc==2.4 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    plumbum==1.9.0 \
    ply==3.11 \
    pyandoc==0.2.0 \
    Pygments==2.19.1 \
    pyrsistent==0.20.0 \
    pytest-mock==3.14.0 \
    pytest==8.3.5 \
    recommonmark==0.7.1 \
    requests==2.32.3 \
    six==1.17.0 \
    sniffio==1.3.1 \
    snowballstemmer==2.2.0 \
    sphinx-autobuild==2024.10.3 \
    Sphinx==7.4.7 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    starlette==0.46.1 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    uvicorn==0.34.0 \
    watchfiles==1.0.4 \
    websockets==15.0.1 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
