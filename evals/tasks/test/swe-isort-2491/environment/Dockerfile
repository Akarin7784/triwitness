# pycqa__isort-2491（PyCQA/isort @ ae91dadf3495）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/PyCQA/isort/archive/ae91dadf34951e316d5a81ffe7ac086952f1da65.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    hypothesis==6.168.5 \
    iniconfig==2.3.1 \
    packaging==26.3 \
    pluggy==1.6.0 \
    py-cpuinfo2==10.1.1 \
    Pygments==2.21.0 \
    pytest-benchmark==5.3.0 \
    pytest==9.1.1 \
    sortedcontainers==2.4.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
