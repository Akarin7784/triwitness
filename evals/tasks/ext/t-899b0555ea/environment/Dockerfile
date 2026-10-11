# adamtheturtle__doccmd-78（adamtheturtle/doccmd @ caf2f7628eb0）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.10-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/adamtheturtle/doccmd/archive/caf2f7628eb0bc39fdd90edf1e4e0aef8666ac69.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    actionlint_py==1.7.1.15 \
    alabaster==1.0.0 \
    astroid==3.3.9 \
    attrs==25.3.0 \
    babel==2.17.0 \
    beartype==0.20.2 \
    beautifulsoup4==4.13.3 \
    build==1.2.2.post1 \
    certifi==2025.1.31 \
    cfgv==3.4.0 \
    charset-normalizer==3.4.1 \
    check-manifest==0.49 \
    click==8.1.8 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    deptry==0.20.0 \
    dill==0.3.9 \
    distlib==0.3.9 \
    doc8==1.1.2 \
    docker==7.1.0 \
    docutils==0.21.2 \
    filelock==3.18.0 \
    furo==2024.8.6 \
    homebrew-pypi-poet==0.10.0 \
    identify==2.6.9 \
    idna==3.10 \
    imagesize==1.4.1 \
    interrogate==1.7.0 \
    isort==5.13.2 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    mypy-extensions==1.0.0 \
    mypy==1.11.2 \
    nodeenv==1.9.1 \
    pbr==6.1.1 \
    platformdirs==4.3.7 \
    pre-commit==3.8.0 \
    py==1.11.0 \
    pydocstyle==6.3.0 \
    pyenchant==3.2.2 \
    Pygments==2.18.0 \
    pylint==3.3.0 \
    pyproject-fmt-rust==1.1.6 \
    pyproject-fmt==2.2.4 \
    pyproject_hooks==1.2.0 \
    pyright==1.1.381 \
    pyroma==4.2 \
    pytest-cov==5.0.0 \
    pytest-datadir==1.6.1 \
    pytest-regressions==2.5.0 \
    pytest==8.3.3 \
    PyYAML==6.0.2 \
    requests==2.32.3 \
    restructuredtext_lint==1.4.0 \
    ruff==0.6.6 \
    shellcheck-py==0.10.0.1 \
    snowballstemmer==2.2.0 \
    soupsieve==2.6 \
    sphinx-basic-ng==1.0.0b2 \
    sphinx-click==6.0.0 \
    sphinx-copybutton==0.5.2 \
    sphinx-substitution-extensions==2024.8.6 \
    Sphinx==8.0.2 \
    sphinx_inline_tabs==2023.4.21 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    sphinxcontrib-spelling==8.0.0 \
    stevedore==5.4.1 \
    sybil-extras==2024.9.20 \
    sybil==9.1.0 \
    tabulate==0.9.0 \
    tee-subprocess==1.2.0 \
    tomlkit==0.13.2 \
    trove-classifiers==2025.3.19.19 \
    types-docker==7.1.0.20240827 \
    types-docutils==0.21.0.20241128 \
    types-Pygments==2.18.0.20240506 \
    types-requests==2.32.0.20250328 \
    types-setuptools==78.1.0.20250329 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    vulture==2.12
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
