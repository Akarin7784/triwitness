# caronc__apprise-119（caronc/apprise @ cbd35c3b7e4b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/caronc/apprise/archive/cbd35c3b7e4b0559fbdb16b481d7c2cabbb602a1.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    chardet==5.2.0 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    decorator==5.2.1 \
    distlib==0.3.9 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    flake8==7.2.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    Markdown==3.7 \
    mccabe==0.7.0 \
    mock==5.2.0 \
    oauthlib==3.2.2 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pycodestyle==2.13.0 \
    pyflakes==3.3.2 \
    pyproject-api==1.9.0 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    requests-oauthlib==2.0.0 \
    requests==2.32.3 \
    six==1.17.0 \
    tomli==2.2.1 \
    tox==4.25.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
