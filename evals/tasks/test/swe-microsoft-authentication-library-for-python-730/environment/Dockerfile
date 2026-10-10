# AzureAD__microsoft-authentication-library-for-python-730（AzureAD/microsoft-authentication-library-for-python @ fe8f7583a539）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/AzureAD/microsoft-authentication-library-for-python/archive/fe8f7583a539f9a5c232df31c916368bc12057f7.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    babel==2.17.0 \
    beautifulsoup4==4.13.3 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    charset-normalizer==3.4.1 \
    cryptography==44.0.2 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    furo==2024.8.6 \
    idna==3.10 \
    imagesize==1.4.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    packaging==24.2 \
    perf-baseline==0.1.0 \
    pluggy==1.5.0 \
    py-cpuinfo==9.0.0 \
    pycparser==2.22 \
    Pygments==2.19.1 \
    PyJWT==2.10.1 \
    pytest-benchmark==4.0.0 \
    pytest==8.3.5 \
    python-dotenv==1.1.0 \
    requests==2.32.3 \
    snowballstemmer==2.2.0 \
    soupsieve==2.6 \
    sphinx-basic-ng==1.0.0b2 \
    sphinx-paramlinks==0.6.0 \
    Sphinx==7.4.7 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
