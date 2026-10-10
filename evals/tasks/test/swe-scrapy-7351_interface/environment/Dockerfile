# scrapy__scrapy-7351_interface（scrapy/scrapy @ 2b174e348d88）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/scrapy/scrapy/archive/2b174e348d88d19dd32135e8e483c4eb784aeca8.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    anyio==4.15.1 \
    attrs==26.1.0 \
    Automat==25.4.16 \
    certifi==2026.7.22 \
    cffi==2.1.1 \
    charset-normalizer==3.5.2 \
    constantly==23.10.4 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    cssselect==1.6.0 \
    decorator==5.3.1 \
    defusedxml==0.7.1 \
    execnet==2.1.2 \
    filelock==4.1.0 \
    greenlet==3.5.6 \
    h11==0.16.0 \
    httpcore==1.0.9 \
    httpx==0.28.1 \
    hyperlink==21.0.0 \
    idna==3.20 \
    Incremental==24.11.0 \
    iniconfig==2.3.1 \
    itemadapter==0.13.1 \
    itemloaders==1.5.0 \
    jmespath==1.1.0 \
    lxml==6.1.3 \
    packaging==26.3 \
    parsel==1.12.1 \
    pexpect==4.9.0 \
    pluggy==1.6.0 \
    Protego==0.7.0 \
    ptyprocess==0.7.0 \
    pyasynchat==1.0.5 \
    pyasyncore==1.0.5 \
    pycparser==3.11 \
    PyDispatcher==2.0.7 \
    pyftpdlib==2.2.0 \
    Pygments==2.21.0 \
    pyOpenSSL==26.4.0 \
    pytest-cov==7.1.0 \
    pytest-twisted==1.14.3 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    queuelib==1.10.0 \
    requests-file==3.0.1 \
    requests==2.34.2 \
    service-identity==26.1.0 \
    sybil==10.1.0 \
    testfixtures==12.4.0 \
    tldextract==5.4.0 \
    Twisted==25.5.0 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    w3lib==2.5.0 \
    zope.interface==8.6
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
