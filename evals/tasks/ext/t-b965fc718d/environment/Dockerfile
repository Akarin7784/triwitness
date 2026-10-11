# dask__distributed-8447（dask/distributed @ 5c481ddcbf77）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/dask/distributed/archive/5c481ddcbf77ce814797d663068d6c0651844caf.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    absl-py==2.2.1 \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    coverage==7.8.0 \
    cramjam==2.9.1 \
    Cython==3.0.12 \
    dask==2023.12.1 \
    exceptiongroup==1.2.2 \
    fsspec==2025.3.2 \
    gilknocker==0.4.1 \
    h5py==3.13.0 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    joblib==1.4.2 \
    keras==3.9.1 \
    locket==1.0.0 \
    lz4==4.4.3 \
    markdown-it-py==3.0.0 \
    MarkupSafe==3.0.2 \
    mdurl==0.1.2 \
    ml_dtypes==0.5.1 \
    msgpack==1.1.0 \
    namex==0.0.8 \
    numpy==2.0.2 \
    nvidia-ml-py==12.570.86 \
    optree==0.14.1 \
    packaging==24.2 \
    partd==1.4.2 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    Pygments==2.19.1 \
    pynvml==12.0.0 \
    pytest-cov==6.0.0 \
    pytest-faulthandler==2.0.1 \
    pytest-repeat==0.9.3 \
    pytest-rerunfailures==15.0 \
    pytest-timeout==2.3.1 \
    pytest==8.3.5 \
    python-snappy==0.7.3 \
    PyYAML==6.0.2 \
    rich==14.0.0 \
    scikit-learn==1.6.1 \
    scipy==1.13.1 \
    sortedcollections==2.1.0 \
    sortedcontainers==2.4.0 \
    tblib==3.1.0 \
    threadpoolctl==3.6.0 \
    tomli==2.2.1 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    zict==3.0.0 \
    zipp==3.21.0 \
    zstandard==0.23.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
