# cherrypy__cherrypy-1578（cherrypy/cherrypy @ 8c635f55c363）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/cherrypy/cherrypy/archive/8c635f55c3634b722260fef501ee49fb440be3ac.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    backports.unittest-mock==1.5.1 \
    cheroot==10.0.1 \
    coverage==7.8.0 \
    exceptiongroup==1.2.2 \
    iniconfig==2.1.0 \
    jaraco.functools==4.1.0 \
    more-itertools==10.6.0 \
    nose-testconfig==0.10 \
    nose==1.3.7 \
    objgraph==3.6.2 \
    packaging==24.2 \
    pluggy==1.5.0 \
    portend==3.2.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    six==1.17.0 \
    tempora==5.8.0 \
    tomli==2.2.1
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
