# valohai__valohai-cli-321（valohai/valohai-cli @ cdc6cfbc3670）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/valohai/valohai-cli/archive/cdc6cfbc3670bb1947ebd6185bd3f670b66afe66.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==26.1.0 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    click==8.1.8 \
    coverage==7.10.7 \
    exceptiongroup==1.3.1 \
    gitignorant==0.4.0 \
    idna==3.20 \
    iniconfig==2.1.0 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.25.1 \
    leval==1.4.0 \
    packaging==26.3 \
    pluggy==1.6.0 \
    pytest-cov==4.1.0 \
    pytest==7.4.4 \
    PyYAML==6.0.3 \
    referencing==0.36.2 \
    requests-mock==1.12.1 \
    requests-toolbelt==1.0.0 \
    requests==2.32.5 \
    rpds-py==0.27.1 \
    tomli==2.5.0 \
    typing_extensions==4.16.0 \
    urllib3==2.6.3 \
    valohai-papi==0.1.3 \
    valohai-utils==0.8.0 \
    valohai-yaml==0.61.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
