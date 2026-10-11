# mpmath__mpmath-992（mpmath/mpmath @ 97c45f21e37d）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/mpmath/mpmath/archive/97c45f21e37d53070c813138bab83d6120f47df7.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asttokens==3.0.2 \
    build==1.6.1 \
    contourpy==1.4.0 \
    coverage==7.16.2 \
    cycler==0.12.1 \
    executing==2.3.0 \
    flake518==1.6.0 \
    flake8==7.4.1 \
    fonttools==4.66.1 \
    hypothesis==6.169.0 \
    iniconfig==2.3.1 \
    ipython==9.17.1 \
    ipython_pygments_lexers==1.1.1 \
    jedi==0.20.0 \
    kiwisolver==1.5.1 \
    matplotlib-inline==0.2.2 \
    matplotlib==3.11.2 \
    mccabe==0.7.0 \
    numpy==2.5.4 \
    packaging==26.3 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    pillow==12.3.0 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    psutil==7.2.2 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    pycodestyle==2.15.0 \
    pyflakes==4.0.3 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pyproject_hooks==1.3.3 \
    pytest-cov==7.1.0 \
    pytest-timeout==2.4.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    six==1.17.0 \
    sortedcontainers==2.4.0 \
    stack-data==0.6.3 \
    traitlets==5.16.1 \
    wcwidth==0.9.2 \
    wheel==0.48.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
