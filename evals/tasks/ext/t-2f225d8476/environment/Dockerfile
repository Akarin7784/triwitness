# matthewwithanm__python-markdownify-230（matthewwithanm/python-markdownify @ 9b1412aa5b5b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.11-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/matthewwithanm/python-markdownify/archive/9b1412aa5b5bca345806068b66d35086cbc88b25.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    beautifulsoup4==4.15.0 \
    iniconfig==2.3.1 \
    packaging==26.3 \
    pluggy==1.6.0 \
    Pygments==2.21.0 \
    pytest==9.1.1 \
    six==1.17.0 \
    soupsieve==3.0.1 \
    typing_extensions==4.16.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
