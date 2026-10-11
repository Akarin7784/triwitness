# Bachmann1234__diff_cover-210（Bachmann1234/diff_cover @ 5f7aeea8b954）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Bachmann1234/diff_cover/archive/5f7aeea8b95441f8286a38524ce0234e1716e304.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    black==25.1.0 \
    chardet==5.2.0 \
    click==8.1.8 \
    coverage==7.8.0 \
    exceptiongroup==1.2.2 \
    importlib_metadata==8.6.1 \
    inflect==7.5.0 \
    iniconfig==2.1.0 \
    isort==6.0.1 \
    jinja2-pluralize==0.3.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    more-itertools==10.6.0 \
    mypy-extensions==1.0.0 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    Pygments==2.19.1 \
    pytest-cov==6.0.0 \
    pytest==8.3.5 \
    tomli==2.2.1 \
    typeguard==4.4.2 \
    typing_extensions==4.13.0 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
