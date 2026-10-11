# dask__distributed-5699（dask/distributed @ 30ffa9c67c78）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/dask/distributed/archive/30ffa9c67c786f043566b6e03c090e36775e904d.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    click==8.1.8 \
    cloudpickle==3.1.1 \
    dask==2022.1.1 \
    exceptiongroup==1.2.2 \
    fsspec==2025.3.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    locket==1.0.0 \
    MarkupSafe==3.0.2 \
    msgpack==1.1.0 \
    packaging==24.2 \
    partd==1.4.2 \
    pluggy==1.5.0 \
    psutil==7.0.0 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    sortedcontainers==2.4.0 \
    tblib==3.1.0 \
    tomli==2.2.1 \
    toolz==1.0.0 \
    tornado==6.4.2 \
    zict==3.0.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
