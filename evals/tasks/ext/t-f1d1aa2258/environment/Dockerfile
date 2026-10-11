# SmileyChris__django-countries-394（SmileyChris/django-countries @ 1c9255af3be3）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/SmileyChris/django-countries/archive/1c9255af3be37f7158296e660f3bbe76812c37ff.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asgiref==3.8.1 \
    black==25.1.0 \
    cachetools==5.5.2 \
    chardet==5.2.0 \
    click==8.1.8 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    distlib==0.3.9 \
    Django==4.2.20 \
    djangorestframework==3.16.0 \
    exceptiongroup==1.2.2 \
    filelock==3.18.0 \
    graphene-django==3.2.3 \
    graphene==3.4.3 \
    graphql-core==3.2.6 \
    graphql-relay==3.2.0 \
    iniconfig==2.1.0 \
    mypy-extensions==1.0.0 \
    packaging==24.2 \
    pathspec==0.12.1 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    promise==2.3 \
    pyproject-api==1.9.0 \
    pytest-django==4.10.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pyuca==1.2 \
    six==1.17.0 \
    sqlparse==0.5.3 \
    text-unidecode==1.3 \
    tomli==2.2.1 \
    tox==4.25.0 \
    typing_extensions==4.13.0 \
    virtualenv==20.29.3
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
