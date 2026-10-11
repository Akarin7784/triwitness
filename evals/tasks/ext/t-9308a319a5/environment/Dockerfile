# beartype__beartype-88（beartype/beartype @ 4190bc3112d0）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/beartype/beartype/archive/4190bc3112d0f56d81af586a5f01a10c3e19feae.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    babel==2.17.0 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    chardet==5.2.0 \
    charset-normalizer==3.4.1 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mypy-extensions==1.0.0 \
    mypy==1.15.0 \
    numpy==2.0.2 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    Pygments==2.19.1 \
    pyproject-api==1.9.0 \
    pytest==8.3.5 \
    requests==2.32.3 \
    snowballstemmer==2.2.0 \
    Sphinx==7.4.7 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
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
