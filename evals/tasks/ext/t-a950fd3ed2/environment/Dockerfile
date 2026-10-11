# conan-io__conan-15924（conan-io/conan @ 82765f2ba80a）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/conan-io/conan/archive/82765f2ba80a3f07d21de4c27d73203081017694.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    attrs==25.3.0 \
    beautifulsoup4==4.13.3 \
    bottle==0.12.25 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    colorama==0.4.6 \
    distro==1.8.0 \
    execnet==2.1.1 \
    fasteners==0.19 \
    idna==3.10 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    mock==1.3.0 \
    packaging==24.2 \
    parameterized==0.9.0 \
    patch-ng==1.17.4 \
    pbr==6.1.1 \
    pluggy==1.5.0 \
    pluginbase==1.0.1 \
    py==1.11.0 \
    PyJWT==2.10.1 \
    pytest-xdist==3.5.0 \
    pytest==6.2.5 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.2 \
    requests==2.32.3 \
    six==1.17.0 \
    soupsieve==2.6 \
    toml==0.10.2 \
    typing_extensions==4.13.0 \
    urllib3==1.26.20 \
    waitress==3.0.2 \
    WebOb==1.8.9 \
    WebTest==2.0.35
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
