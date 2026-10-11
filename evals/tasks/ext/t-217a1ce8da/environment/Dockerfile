# PMEAL__porespy-465（PMEAL/porespy @ 51276c464cca）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/PMEAL/porespy/archive/51276c464ccaf8feea1cb246c6178a81af3b51dc.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    bokeh==3.4.3 \
    chemicals==1.3.3 \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    contourpy==1.3.0 \
    coverage==7.8.0 \
    cycler==0.12.1 \
    dask-expr==1.1.10 \
    dask==2024.8.0 \
    distributed==2024.8.0 \
    docrep==0.3.2 \
    edt==3.0.0 \
    exceptiongroup==1.2.2 \
    execnet==2.1.1 \
    fluids==1.1.0 \
    fonttools==4.56.0 \
    fsspec==2025.3.1 \
    h5py==3.13.0 \
    imageio==2.37.0 \
    imglyb==2.1.0 \
    importlib_metadata==8.6.1 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    jgo==1.0.6 \
    Jinja2==3.1.6 \
    jpype1==1.5.2 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    jupyterlab_widgets==3.0.13 \
    kiwisolver==1.4.7 \
    labeling==0.1.14 \
    lazy_loader==0.4 \
    llvmlite==0.43.0 \
    locket==1.0.0 \
    loguru==0.7.3 \
    lz4==4.4.3 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    matplotlib==3.9.4 \
    mdurl==0.1.2 \
    mpmath==1.3.0 \
    msgpack==1.1.0 \
    networkx==3.2.1 \
    numba==0.60.0 \
    numpy-stl==3.2.0 \
    numpy==2.0.2 \
    openpnm==3.5.0 \
    packaging==24.2 \
    pandas==2.2.3 \
    partd==1.4.2 \
    pillow==11.1.0 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    pyamg==5.2.1 \
    pyarrow-hotfix==0.6 \
    pyarrow==19.0.1 \
    pyevtk==1.6.0 \
    Pygments==2.19.1 \
    pyimagej==1.6.0 \
    pyparsing==3.2.3 \
    pytest-asyncio==0.26.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest-xdist==3.6.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    python-utils==3.9.1 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    referencing==0.36.2 \
    rich==14.0.0 \
    rpds-py==0.24.0 \
    scikit-image==0.24.0 \
    scipy==1.13.1 \
    scyjava==1.10.2 \
    six==1.17.0 \
    sortedcontainers==2.4.0 \
    sympy==1.13.3 \
    tblib==3.1.0 \
    thermo==0.4.2 \
    tifffile==2024.8.30 \
    tomli==2.2.1 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    tqdm==4.67.1 \
    transforms3d==0.4.2 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    xarray==2024.7.0 \
    xyzservices==2025.1.0 \
    zict==3.0.0 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
