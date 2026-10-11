# casbin__pycasbin-346（casbin/pycasbin @ 846cf2490648）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/casbin/pycasbin/archive/846cf2490648f344817d53280cfb3c4f03a91f26.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    black==23.11.0 \
    click==8.1.8 \
    iniconfig==2.1.0 \
    mypy-extensions==1.0.0 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    py-cpuinfo==9.0.0 \
    py==1.11.0 \
    pytest-benchmark==3.4.1 \
    pytest==7.0.1 \
    setuptools==75.8.0 \
    simpleeval==1.0.3 \
    tomli==2.2.1 \
    wheel==0.45.1
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
