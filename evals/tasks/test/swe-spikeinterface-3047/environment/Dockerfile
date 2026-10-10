# SpikeInterface__spikeinterface-3047（SpikeInterface/spikeinterface @ e139e75d6d9a）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/SpikeInterface/spikeinterface/archive/e139e75d6d9a5bcbde9ce133db84a83ab7724a9e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    altair==5.5.0 \
    asciitree==0.3.3 \
    asttokens==3.0.0 \
    attrs==25.3.0 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    comm==0.2.2 \
    contourpy==1.3.0 \
    coverage==7.8.0 \
    cuda-bindings==12.8.0 \
    cuda-python==12.8.0 \
    cycler==0.12.1 \
    decorator==5.2.1 \
    distinctipy==1.3.4 \
    executing==2.2.0 \
    fasteners==0.19 \
    figurl==0.3.0a1 \
    fonttools==4.56.0 \
    h5py==3.13.0 \
    hdmf==4.0.0 \
    idna==3.10 \
    importlib_resources==6.5.2 \
    ipympl==0.9.7 \
    ipython==8.18.1 \
    ipywidgets==8.1.5 \
    jedi==0.19.2 \
    Jinja2==3.1.6 \
    joblib==1.4.2 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    jupyterlab_widgets==3.0.13 \
    kachery==2.0.2 \
    kiwisolver==1.4.7 \
    llvmlite==0.43.0 \
    MarkupSafe==3.0.2 \
    matplotlib-inline==0.1.7 \
    matplotlib==3.9.4 \
    narwhals==1.32.0 \
    neo==0.14.0 \
    networkx==3.2.1 \
    numba==0.60.0 \
    numcodecs==0.12.1 \
    numpy==1.26.4 \
    pandas==2.2.3 \
    parso==0.8.4 \
    pexpect==4.9.0 \
    pillow==11.1.0 \
    probeinterface==0.2.26 \
    prompt_toolkit==3.0.50 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.3 \
    Pygments==2.19.1 \
    pynwb==3.0.0 \
    pyparsing==3.2.3 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pytz==2025.2 \
    PyYAML==6.0.2 \
    quantities==0.16.1 \
    referencing==0.36.2 \
    requests==2.32.3 \
    rpds-py==0.24.0 \
    ruamel.yaml.clib==0.2.12 \
    ruamel.yaml==0.18.10 \
    scikit-learn==1.6.1 \
    scipy==1.13.1 \
    simplejson==3.20.1 \
    six==1.17.0 \
    sortingview==0.14.1 \
    stack-data==0.6.3 \
    threadpoolctl==3.6.0 \
    tqdm==4.67.1 \
    traitlets==5.14.3 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    urllib3==2.3.0 \
    wcwidth==0.2.13 \
    widgetsnbextension==4.0.13 \
    xarray==2024.7.0 \
    zarr==2.17.2 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
