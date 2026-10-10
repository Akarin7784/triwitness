# TDAmeritrade__stumpy-1015（TDAmeritrade/stumpy @ 3077d0ddfb31）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/TDAmeritrade/stumpy/archive/3077d0ddfb315464321dc86f8ec3bf2cab9ce3b1.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    black==25.1.0 \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    coverage==7.8.0 \
    dask==2024.8.0 \
    distributed==2024.8.0 \
    exceptiongroup==1.2.2 \
    flake8-docstrings==1.7.0 \
    flake8==7.2.0 \
    fsspec==2025.3.2 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isort==6.0.1 \
    Jinja2==3.1.6 \
    llvmlite==0.43.0 \
    locket==1.0.0 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    msgpack==1.1.0 \
    mypy-extensions==1.0.0 \
    numba==0.60.0 \
    numpy==2.0.2 \
    packaging==24.2 \
    pandas==2.2.3 \
    partd==1.4.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    pycodestyle==2.13.0 \
    pydocstyle==6.3.0 \
    pyflakes==3.3.2 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    scipy==1.13.1 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    sortedcontainers==2.4.0 \
    tbb==2022.1.0 \
    tblib==3.1.0 \
    tcmlib==1.3.0 \
    tomli==2.2.1 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    zict==3.0.0 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
