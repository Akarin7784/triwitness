# Delgan__loguru-1306（Delgan/loguru @ 3cfd03fb6fd2）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Delgan/loguru/archive/3cfd03fb6fd2176b90ad14223408f3c4ec803cb6.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    cachetools==5.5.2 \
    cfgv==3.4.0 \
    chardet==5.2.0 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    decorator==5.2.1 \
    distlib==0.3.9 \
    exceptiongroup==1.1.3 \
    filelock==3.18.0 \
    freezegun==1.5.0 \
    identify==2.6.9 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    MarkupSafe==3.0.2 \
    mypy-extensions==1.0.0 \
    mypy==1.14.1 \
    nodeenv==1.9.1 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pre_commit==4.1.0 \
    pyproject-api==1.9.0 \
    pytest-cov==6.0.0 \
    pytest-mypy-plugins==3.2.0 \
    pytest==8.3.2 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.2 \
    referencing==0.36.2 \
    regex==2024.11.6 \
    rpds-py==0.24.0 \
    six==1.17.0 \
    tomli==2.2.1 \
    tomlkit==0.13.2 \
    tox==4.24.1 \
    typing_extensions==4.13.1 \
    virtualenv==20.30.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
