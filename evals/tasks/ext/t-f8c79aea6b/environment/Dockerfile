# microsoft__fabric-cicd-465（microsoft/fabric-cicd @ 74f59b95e020）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/microsoft/fabric-cicd/archive/74f59b95e0203e0c7dda5418d461a1f2723a8b4b.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    azure-core==1.41.0 \
    azure-identity==1.26.0 \
    certifi==2026.7.22 \
    cffi==2.1.1 \
    charset-normalizer==3.5.2 \
    cryptography==50.0.2 \
    dpath==2.2.0 \
    filetype==1.2.0 \
    idna==3.20 \
    iniconfig==2.3.1 \
    jsonpath-ng==1.10.0 \
    msal-extensions==1.3.1 \
    msal==1.39.0 \
    packaging==26.3 \
    pluggy==1.6.0 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    PyJWT==2.15.1 \
    pytest==9.1.1 \
    PyYAML==6.0.3 \
    requests==2.34.2 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
