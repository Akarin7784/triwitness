# PMEAL__porespy-809（PMEAL/porespy @ 63ce07d4a1c0）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/PMEAL/porespy/archive/63ce07d4a1c0337bc5942a33777fae81adc6aba9.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    chemicals==1.3.3 \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    contourpy==1.3.0 \
    coverage==7.8.0 \
    cycler==0.12.1 \
    dask==2024.8.0 \
    Deprecated==1.2.18 \
    docrep==0.3.2 \
    edt==3.0.0 \
    exceptiongroup==1.2.2 \
    execnet==2.1.1 \
    fluids==1.1.0 \
    fonttools==4.56.0 \
    fsspec==2025.3.1 \
    h5py==3.13.0 \
    imageio==2.37.0 \
    importlib_metadata==8.6.1 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    kiwisolver==1.4.7 \
    lazy_loader==0.4 \
    llvmlite==0.43.0 \
    locket==1.0.0 \
    markdown-it-py==3.0.0 \
    matplotlib==3.9.4 \
    mdurl==0.1.2 \
    mpmath==1.3.0 \
    networkx==3.2.1 \
    numba==0.60.0 \
    numpy==2.0.2 \
    openpnm==3.5.0 \
    packaging==24.2 \
    pandas==2.2.3 \
    partd==1.4.2 \
    pillow==11.1.0 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    pyamg==5.2.1 \
    Pygments==2.19.1 \
    pyparsing==3.2.3 \
    pytest-asyncio==0.26.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest-xdist==3.6.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    referencing==0.36.2 \
    rich==14.0.0 \
    rpds-py==0.24.0 \
    scikit-image==0.24.0 \
    scipy==1.13.1 \
    six==1.17.0 \
    sympy==1.13.3 \
    thermo==0.4.2 \
    tifffile==2024.8.30 \
    tomli==2.2.1 \
    toolz==1.0.0 \
    tqdm==4.67.1 \
    transforms3d==0.4.2 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    wrapt==1.17.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
