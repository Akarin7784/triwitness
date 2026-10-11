# fjosw__pyerrors-253（fjosw/pyerrors @ 997d360db371）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/fjosw/pyerrors/archive/997d360db37133b7dcbef8b9dbf1e3aff4d7c4bf.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asttokens==3.0.2 \
    attrs==26.1.0 \
    autograd==1.8.0 \
    comm==0.2.3 \
    contourpy==1.3.0 \
    coverage==7.10.7 \
    cycler==0.12.1 \
    debugpy==1.8.21 \
    decorator==5.3.1 \
    exceptiongroup==1.3.1 \
    executing==2.3.0 \
    fastjsonschema==2.21.2 \
    flake8==7.3.0 \
    fonttools==4.60.2 \
    h5py==3.14.0 \
    hypothesis==6.141.1 \
    iminuit==2.33.0 \
    importlib_metadata==8.7.1 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    ipykernel==6.31.0 \
    ipython==8.18.1 \
    jedi==0.19.2 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.25.1 \
    jupyter_client==8.6.3 \
    jupyter_core==5.8.1 \
    kiwisolver==1.4.7 \
    lxml==6.1.3 \
    matplotlib-inline==0.2.2 \
    matplotlib==3.9.4 \
    mccabe==0.7.0 \
    nbclient==0.10.2 \
    nbformat==5.10.4 \
    nbmake==1.5.5 \
    nest-asyncio==1.6.0 \
    numdifftools==0.9.41 \
    numpy==2.0.2 \
    packaging==26.3 \
    pandas==2.3.3 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    pillow==11.3.0 \
    platformdirs==4.4.0 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.52 \
    psutil==7.2.2 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    py-cpuinfo==9.0.0 \
    pycodestyle==2.14.0 \
    pyflakes==3.4.0 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest-benchmark==5.2.3 \
    pytest-cov==7.1.0 \
    pytest==8.4.2 \
    python-dateutil==2.9.0.post0 \
    python-rapidjson==1.23 \
    pytz==2026.5 \
    pyzmq==27.2.0 \
    referencing==0.36.2 \
    rpds-py==0.27.1 \
    scipy==1.13.1 \
    six==1.17.0 \
    sortedcontainers==2.4.0 \
    stack-data==0.6.3 \
    tomli==2.5.0 \
    tornado==6.5.10 \
    traitlets==5.15.1 \
    typing_extensions==4.16.0 \
    tzdata==2026.5 \
    wcwidth==0.9.2 \
    zipp==3.23.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
