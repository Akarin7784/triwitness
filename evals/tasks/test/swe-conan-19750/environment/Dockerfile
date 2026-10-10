# conan-io__conan-19750（conan-io/conan @ 6c9356b3e5bd）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/conan-io/conan/archive/6c9356b3e5bd75f7d7061a708785e80aaacb3b43.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    beautifulsoup4==4.15.0 \
    bottle==0.13.4 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    colorama==0.4.6 \
    coverage==7.16.2 \
    distro==1.9.0 \
    docker==7.2.0 \
    execnet==2.1.2 \
    fasteners==0.20 \
    idna==3.20 \
    iniconfig==2.3.1 \
    Jinja2==3.1.6 \
    legacy-cgi==2.6.4 \
    MarkupSafe==3.0.4 \
    packaging==26.3 \
    patch-ng==1.18.1 \
    pluggy==1.6.0 \
    pluginbase==1.0.1 \
    PyJWT==2.15.1 \
    pytest-cov==7.1.0 \
    pytest-xdist==3.8.0 \
    pytest==7.4.4 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.3 \
    requests==2.34.2 \
    setuptools==84.0.0 \
    six==1.17.0 \
    soupsieve==2.10 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0 \
    waitress==3.0.2 \
    WebOb==1.8.11 \
    WebTest==3.0.7
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
