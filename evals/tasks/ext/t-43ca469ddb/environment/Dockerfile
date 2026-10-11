# vprusso__toqito-1298（vprusso/toqito @ 6983af91a51e）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/vprusso/toqito/archive/6983af91a51ec3a6267a41aeb6bf5a8531e56937.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    cvxpy==1.7.1 \
    debugpy==1.8.22 \
    defusedxml==0.7.1 \
    docutils==0.22.4 \
    executing==2.3.0 \
    fastjsonschema==2.22.2 \
    idna==3.20 \
    imagesize==2.0.1 \
    iniconfig==2.3.1 \
    ipykernel==7.4.0 \
    ipython==9.17.1 \
    ipython_pygments_lexers==1.1.1 \
    ipywidgets==8.1.9 \
    jedi==0.20.0 \
    Jinja2==3.1.6 \
    joblib==1.6.0 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    jupyter-sphinx==0.5.3 \
    jupyter_client==8.10.0 \
    jupyter_core==5.9.1 \
    jupyterlab_pygments==0.3.0 \
    jupyterlab_widgets==3.0.17 \
    llvmlite==0.44.0 \
    MarkupSafe==3.0.4 \
    matplotlib-inline==0.2.2 \
    mistune==3.3.4 \
    more-itertools==10.7.0 \
    nbclient==0.11.0 \
    nbconvert==7.17.1 \
    nbformat==5.11.1 \
    nest-asyncio2==1.7.4 \
    networkx==3.7 \
    numba==0.61.2 \
    numpy==2.2.6 \
    osqp==1.1.3 \
    packaging==26.3 \
    pandocfilters==1.5.1 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    PICOS==2.6.0 \
    platformdirs==4.13.0 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    psutil==7.2.2 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    pyzmq==27.2.0 \
    referencing==0.37.0 \
    requests==2.34.2 \
    roman-numerals==4.1.0 \
    rpds-py==2026.9.1 \
    scipy==1.15.3 \
    scs==3.2.7.post2 \
    setuptools==84.0.0 \
    six==1.17.0 \
    snowballstemmer==3.1.1 \
    soupsieve==3.0.1 \
    Sphinx==9.1.0 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    stack-data==0.6.3 \
    tinycss2==1.5.1 \
    tornado==6.5.10 \
    traitlets==5.16.1 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    wcwidth==0.9.2 \
    webencodings==0.6.1 \
    widgetsnbextension==4.0.16
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
