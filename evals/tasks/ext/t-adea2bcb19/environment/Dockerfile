# bvanelli__actualpy-55（bvanelli/actualpy @ f7210990432f）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/bvanelli/actualpy/archive/f7210990432f8748a7707463be7ba477fc717bdd.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.7.0 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    charset-normalizer==3.4.1 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    exceptiongroup==1.2.2 \
    greenlet==3.1.1 \
    idna==3.10 \
    iniconfig==2.1.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    proto-plus==1.26.1 \
    protobuf==6.30.2 \
    pycparser==2.22 \
    pydantic==2.11.1 \
    pydantic_core==2.33.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    requests==2.31.0 \
    six==1.17.0 \
    SQLAlchemy==2.0.40 \
    sqlmodel==0.0.18 \
    tomli==2.2.1 \
    typing-inspection==0.4.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
