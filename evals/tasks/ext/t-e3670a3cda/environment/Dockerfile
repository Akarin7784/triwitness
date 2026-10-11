# stfc__PSyclone-2999（stfc/PSyclone @ 9a5a1420dd52）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/stfc/PSyclone/archive/9a5a1420dd52b464d9ae09e8d38ce9841405159a.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    configparser==7.2.0 \
    exceptiongroup==1.3.1 \
    fparser==0.2.5 \
    graphviz==0.21 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.4 \
    mpmath==1.3.0 \
    packaging==26.3 \
    pluggy==1.6.0 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest==8.4.2 \
    sympy==1.14.0 \
    termcolor==3.1.0 \
    tomli==2.5.0 \
    typing_extensions==4.16.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
