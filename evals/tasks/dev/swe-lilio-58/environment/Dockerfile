# AI4S2S__lilio-58（AI4S2S/lilio @ 416ea560d41b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/AI4S2S/lilio/archive/416ea560d41b57502cf204fbf4e65e79c21373bf.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    anyio==4.9.0 \
    backports.tarfile==1.2.0 \
    black==25.1.0 \
    bump2version==1.0.1 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    cftime==1.6.4.post1 \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    contourpy==1.3.0 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    cycler==0.12.1 \
    dask==2024.8.0 \
    distlib==0.3.9 \
    distributed==2024.8.0 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    fonttools==4.56.0 \
    fsspec==2025.3.1 \
    h11==0.14.0 \
    hatch==1.14.0 \
    hatchling==1.27.0 \
    httpcore==1.0.7 \
    httpx==0.28.1 \
    hyperlink==21.0.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    isort==6.0.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.0.1 \
    jaraco.functools==4.1.0 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    joblib==1.4.2 \
    keyring==25.6.0 \
    kiwisolver==1.4.7 \
    locket==1.0.0 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    matplotlib==3.9.4 \
    mdurl==0.1.2 \
    more-itertools==10.6.0 \
    msgpack==1.1.0 \
    mypy-extensions==1.0.0 \
    mypy==1.15.0 \
    netCDF4==1.7.2 \
    numpy==2.0.2 \
    packaging==24.2 \
    pandas==2.2.3 \
    partd==1.4.2 \
    pathspec==0.12.1 \
    pexpect==4.9.0 \
    pillow==11.1.0 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    ptyprocess==0.7.0 \
    pycparser==2.22 \
    Pygments==2.19.1 \
    pyparsing==3.2.3 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    rich==14.0.0 \
    ruff==0.11.2 \
    scikit-learn==1.6.1 \
    scipy==1.13.1 \
    SecretStorage==3.3.3 \
    shellingham==1.5.4 \
    six==1.17.0 \
    sniffio==1.3.1 \
    sortedcontainers==2.4.0 \
    tblib==3.1.0 \
    threadpoolctl==3.6.0 \
    tomli==2.2.1 \
    tomli_w==1.2.0 \
    tomlkit==0.13.2 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    trove-classifiers==2025.3.19.19 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    userpath==1.9.2 \
    uv==0.6.11 \
    virtualenv==20.29.3 \
    xarray==2024.7.0 \
    zict==3.0.0 \
    zipp==3.21.0 \
    zstandard==0.23.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
