# delgan__loguru-1451（Delgan/loguru @ 2abeb0fa6d7b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Delgan/loguru/archive/2abeb0fa6d7be4b0455c6e0b580b1e9dab19005e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    cfgv==3.5.0 \
    chardet==7.6.0 \
    charset-normalizer==3.5.2 \
    colorama==0.4.6 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    decorator==5.3.1 \
    distlib==0.4.3 \
    docutils==0.21.2 \
    filelock==4.1.0 \
    freezegun==1.5.0 \
    id==1.6.1 \
    identify==2.6.20 \
    idna==3.20 \
    imagesize==2.0.1 \
    iniconfig==2.3.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.1.2 \
    jaraco.functools==4.6.0 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    keyring==25.7.0 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.4 \
    mdit-py-plugins==0.6.1 \
    mdurl==0.1.2 \
    more-itertools==11.1.0 \
    mypy==1.18.2 \
    mypy_extensions==1.1.0 \
    myst-parser==4.0.0 \
    nh3==0.3.7 \
    nodeenv==1.11.0 \
    packaging==26.3 \
    pathspec==1.1.1 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    pre_commit==4.3.0 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    pyproject-api==1.11.4 \
    pyproject_hooks==1.3.3 \
    pytest-cov==6.2.1 \
    pytest-mypy-plugins==3.2.0 \
    pytest==8.4.1 \
    python-dateutil==2.9.0.post0 \
    python-discovery==1.6.2 \
    PyYAML==6.0.3 \
    readme_renderer==46.0 \
    referencing==0.37.0 \
    regex==2026.9.29 \
    requests-toolbelt==1.0.0 \
    requests==2.34.2 \
    rfc3986==2.0.0 \
    rich==15.0.0 \
    roman-numerals-py==4.1.0 \
    roman-numerals==4.1.0 \
    rpds-py==2026.9.1 \
    SecretStorage==3.5.0 \
    six==1.17.0 \
    snowballstemmer==3.1.1 \
    sphinx-rtd-theme==3.0.2 \
    Sphinx==8.2.1 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tomlkit==0.15.1 \
    tox==4.30.2 \
    twine==6.2.0 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    virtualenv==21.14.6
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
