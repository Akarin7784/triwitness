# Materials-Consortia__optimade-python-tools-813（Materials-Consortia/optimade-python-tools @ ce8b4ddd1dbd）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Materials-Consortia/optimade-python-tools/archive/ce8b4ddd1dbdf2a11ab2d8f2457eb2cac6624009.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asgiref==3.6.0 \
    astroid==2.15.8 \
    attrs==25.3.0 \
    bracex==2.5.post1 \
    certifi==2025.1.31 \
    cfgv==3.4.0 \
    chardet==4.0.0 \
    click==7.1.2 \
    codecov==2.1.13 \
    coverage==7.8.0 \
    dill==0.3.9 \
    distlib==0.3.9 \
    Django==3.2 \
    dnspython==2.7.0 \
    elasticsearch-dsl==6.4.0 \
    elasticsearch==6.8.2 \
    email-validator==1.1.2 \
    exceptiongroup==1.2.2 \
    fastapi==0.63.0 \
    filelock==3.18.0 \
    ghp-import==2.1.0 \
    h11==0.14.0 \
    htmlmin==0.1.12 \
    identify==2.6.9 \
    idna==2.10 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    invoke==1.7.3 \
    isort==5.13.2 \
    Jinja2==2.11.3 \
    jsmin==3.0.1 \
    jsondiff==1.3.1 \
    lark-parser==0.11.2 \
    lazy-object-proxy==1.10.0 \
    Markdown==3.7 \
    MarkupSafe==2.1.5 \
    mccabe==0.7.0 \
    mergedeep==1.3.4 \
    mkdocs-autorefs==0.2.1 \
    mkdocs-awesome-pages-plugin==2.10.1 \
    mkdocs-get-deps==0.2.0 \
    mkdocs-material-extensions==1.3.1 \
    mkdocs-material==7.3.0 \
    mkdocs-minify-plugin==0.4.1 \
    mkdocs==1.6.1 \
    mkdocstrings==0.15.2 \
    mongomock==3.22.1 \
    natsort==8.4.0 \
    nodeenv==1.9.1 \
    numpy==1.26.4 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pre-commit==2.21.0 \
    py==1.11.0 \
    pydantic==1.8.2 \
    Pygments==2.19.1 \
    pylint==2.17.7 \
    pymdown-extensions==8.2 \
    pymongo==3.11.3 \
    pytest-cov==2.12.1 \
    pytest==6.2.5 \
    python-dateutil==2.9.0.post0 \
    pytkdocs==0.11.1 \
    pytz==2025.2 \
    PyYAML==5.4.1 \
    pyyaml_env_tag==0.1 \
    requests==2.25.1 \
    sentinels==1.0.0 \
    six==1.17.0 \
    sqlparse==0.5.3 \
    starlette==0.13.6 \
    toml==0.10.2 \
    tomli==2.2.1 \
    tomlkit==0.13.2 \
    typing_extensions==4.13.0 \
    urllib3==1.26.20 \
    uvicorn==0.13.4 \
    virtualenv==20.29.3 \
    watchdog==6.0.0 \
    wcmatch==10.0 \
    wrapt==1.17.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
