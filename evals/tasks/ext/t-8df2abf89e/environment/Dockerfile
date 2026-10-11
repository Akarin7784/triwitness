# CybOXProject__mixbox-35（CybOXProject/mixbox @ bab51cfd2075）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/CybOXProject/mixbox/archive/bab51cfd20757f9a64a61571631203dbbc3644f8.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    alabaster==0.7.16 \
    babel==2.17.0 \
    bump2version==1.0.1 \
    bumpversion==0.6.0 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    lxml==5.3.1 \
    MarkupSafe==3.0.2 \
    nose==1.3.0 \
    ordered-set==4.1.0 \
    packaging==24.2 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    py==1.11.0 \
    Pygments==2.19.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    sphinx-rtd-theme==0.1.8 \
    Sphinx==1.3.1 \
    tomli==2.2.1 \
    tox==1.6.1 \
    virtualenv==20.30.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
