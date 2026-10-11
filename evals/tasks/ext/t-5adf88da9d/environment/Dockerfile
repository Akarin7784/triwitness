# gidgethub__gidgethub-225（gidgethub/gidgethub @ abdf45e24b0a）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/gidgethub/gidgethub/archive/abdf45e24b0ac2dbbcb3b423594326d9627c3db8.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    cffi==2.1.1 \
    cryptography==50.0.2 \
    iniconfig==2.3.1 \
    packaging==26.3 \
    pluggy==1.6.0 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    PyJWT==2.15.1 \
    pytest==9.1.1 \
    uritemplate==4.2.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
