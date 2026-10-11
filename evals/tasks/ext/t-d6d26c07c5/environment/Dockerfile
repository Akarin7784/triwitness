# owkin__PyDESeq2-356（owkin/PyDESeq2 @ 5a44961789b9）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.10-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/owkin/PyDESeq2/archive/5a44961789b96edb8012c3b62ba650d9e14ed05a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==1.0.0 \
    anndata==0.11.4 \
    array-api-compat==1.15.0 \
    ast_serialize==0.12.1 \
    babel==2.18.0 \
    certifi==2026.7.22 \
    cfgv==3.5.0 \
    charset-normalizer==3.5.2 \
    cloudpickle==3.1.2 \
    contourpy==1.3.2 \
    coverage==7.16.2 \
    cycler==0.12.1 \
    distlib==0.4.3 \
    docutils==0.21.2 \
    exceptiongroup==1.3.1 \
    filelock==4.1.0 \
    fonttools==4.65.0 \
    formulaic-contrasts==1.0.0 \
    formulaic==1.2.2 \
    h5py==3.16.0 \
    identify==2.6.20 \
    idna==3.20 \
    imagesize==2.0.1 \
    iniconfig==2.3.1 \
    interface_meta==2.0.1 \
    Jinja2==3.1.6 \
    joblib==1.6.0 \
    kiwisolver==1.5.1 \
    librt==0.16.0 \
    MarkupSafe==3.0.4 \
    matplotlib==3.10.9 \
    mypy==2.4.0 \
    mypy_extensions==1.1.0 \
    narwhals==2.27.1 \
    natsort==8.4.0 \
    nodeenv==1.11.0 \
    numpy==2.2.6 \
    numpydoc==1.11.0 \
    packaging==26.3 \
    pandas-stubs==2.3.3.260113 \
    pandas==2.3.3 \
    pathspec==1.1.1 \
    pillow==12.3.0 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    pre_commit==4.6.2 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    python-discovery==1.6.2 \
    pytz==2026.5 \
    PyYAML==6.0.3 \
    requests==2.34.2 \
    scikit-learn==1.7.2 \
    scipy==1.15.3 \
    session_info==1.0.1 \
    six==1.17.0 \
    snowballstemmer==3.1.1 \
    Sphinx==8.1.3 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    stdlib-list==0.12.0 \
    threadpoolctl==3.7.0 \
    tomli==2.5.0 \
    types-pytz==2026.5.0.20261006 \
    typing_extensions==4.16.0 \
    tzdata==2026.5 \
    urllib3==2.8.0 \
    virtualenv==21.14.6 \
    wrapt==2.5.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
