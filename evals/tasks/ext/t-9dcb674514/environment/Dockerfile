# Shopify__shopify_python_api-177（Shopify/shopify_python_api @ c29e0ecbed9d）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Shopify/shopify_python_api/archive/c29e0ecbed9de67dd923f980a3ac053922dab75e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    exceptiongroup==1.2.2 \
    flake8-docstrings==1.7.0 \
    flake8==7.2.0 \
    iniconfig==2.1.0 \
    mccabe==0.7.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pyactiveresource==2.2.2 \
    pycodestyle==2.13.0 \
    pydocstyle==6.3.0 \
    pyflakes==3.3.1 \
    pytest==8.3.5 \
    PyYAML==6.0.2 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    tomli==2.2.1
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
