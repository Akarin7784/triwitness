# EmilStenstrom__django-components-489（EmilStenstrom/django-components @ 085c60a8c964）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/EmilStenstrom/django-components/archive/085c60a8c96442d9fd4f72d66a7eb295e7cfb2d9.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asgiref==3.7.2 \
    black==24.4.2 \
    cachetools==5.3.2 \
    cfgv==3.4.0 \
    chardet==5.2.0 \
    click==8.1.7 \
    colorama==0.4.6 \
    distlib==0.3.8 \
    Django==4.2.20 \
    djc_core_html_parser==1.0.2 \
    exceptiongroup==1.2.2 \
    filelock==3.13.1 \
    Flake8-pyproject==1.2.3 \
    flake8==7.0.0 \
    identify==2.5.33 \
    iniconfig==2.0.0 \
    isort==5.13.2 \
    mccabe==0.7.0 \
    mypy-extensions==1.0.0 \
    mypy==1.10.0 \
    nodeenv==1.8.0 \
    packaging==23.2 \
    pathspec==0.12.1 \
    platformdirs==4.1.0 \
    pluggy==1.5.0 \
    pre-commit==3.7.0 \
    pycodestyle==2.11.1 \
    pyflakes==3.2.0 \
    pyproject-api==1.6.1 \
    pytest==8.2.0 \
    PyYAML==6.0.1 \
    sqlparse==0.5.0 \
    tomli==2.2.1 \
    tox==4.15.0 \
    typing_extensions==4.10.0 \
    virtualenv==20.25.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
