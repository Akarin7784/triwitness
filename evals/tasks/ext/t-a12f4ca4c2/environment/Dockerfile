# pgmpy__pgmpy-2098（pgmpy/pgmpy @ 8975b8991913）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/pgmpy/pgmpy/archive/8975b899191330c4a856981c8dc38508e42ed576.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    black==26.10.1 \
    cfgv==3.5.0 \
    click==8.5.0 \
    cloudpickle==3.1.2 \
    coverage==7.16.2 \
    cuda-bindings==13.4.3 \
    cuda-pathfinder==1.8.3 \
    cuda-toolkit==13.0.3.0 \
    distlib==0.4.3 \
    execnet==2.1.2 \
    filelock==4.1.0 \
    formulaic==1.2.2 \
    fsspec==2026.9.0 \
    identify==2.6.20 \
    iniconfig==2.3.1 \
    interface_meta==2.0.1 \
    Jinja2==3.1.6 \
    joblib==1.6.0 \
    MarkupSafe==3.0.4 \
    mock==5.2.0 \
    mpmath==1.3.0 \
    mypy_extensions==1.1.0 \
    narwhals==2.27.1 \
    networkx==3.6.1 \
    nodeenv==1.11.0 \
    numpy==2.4.6 \
    nvidia-cublas==13.1.1.3 \
    nvidia-cuda-cupti==13.0.85 \
    nvidia-cuda-nvrtc==13.0.88 \
    nvidia-cuda-runtime==13.0.96 \
    nvidia-cudnn-cu13==9.24.0.43 \
    nvidia-cufft==12.0.0.61 \
    nvidia-cufile==1.15.1.6 \
    nvidia-curand==10.4.0.35 \
    nvidia-cusolver==12.0.4.66 \
    nvidia-cusparse==12.6.3.3 \
    nvidia-cusparselt-cu13==0.8.1 \
    nvidia-nccl-cu13==2.30.7 \
    nvidia-nvjitlink==13.4.92 \
    nvidia-nvshmem-cu13==3.4.5 \
    nvidia-nvtx==13.0.85 \
    opt_einsum==3.4.0 \
    packaging==26.3 \
    pandas==3.0.6 \
    pathspec==1.1.1 \
    patsy==1.0.3 \
    platformdirs==4.13.0 \
    pluggy==1.6.0 \
    pre_commit==4.6.2 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pyro-api==0.1.2 \
    pyro-ppl==1.9.2 \
    pytest-cov==7.1.0 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    python-discovery==1.6.2 \
    pytokens==0.4.1 \
    PyYAML==6.0.3 \
    scikit-learn==1.9.1 \
    scipy==1.17.1 \
    six==1.17.0 \
    statsmodels==0.15.0 \
    sympy==1.14.0 \
    threadpoolctl==3.7.0 \
    torch==2.14.1 \
    tqdm==4.70.1 \
    triton==3.8.0 \
    typing_extensions==4.16.0 \
    virtualenv==21.14.6 \
    wrapt==2.5.0 \
    xdoctest==1.3.2
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
