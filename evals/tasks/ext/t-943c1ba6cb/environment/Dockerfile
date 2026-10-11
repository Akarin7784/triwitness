# ARMmbed__greentea-263（ARMmbed/greentea @ 68508c5f4d7c）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/ARMmbed/greentea/archive/68508c5f4d7cf0635c75399d0ff7cfa896fdf2cc.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    appdirs==1.4.4 \
    beautifulsoup4==4.13.3 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    colorama==0.3.9 \
    fasteners==0.19 \
    future==1.0.0 \
    idna==3.10 \
    intelhex==2.3.0 \
    junit-xml==1.9 \
    lockfile==0.12.2 \
    mbed-host-tests==1.8.15 \
    mbed-ls==1.8.15 \
    mbed-os-tools==1.8.15 \
    mock==5.2.0 \
    prettytable==2.5.0 \
    pyserial==3.5 \
    pytest==8.3.5 \
    requests==2.32.3 \
    six==1.17.0 \
    soupsieve==2.6 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    wcwidth==0.2.13
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
