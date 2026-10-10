# copier-org__copier-2646（copier-org/copier @ e05ddfec08bc）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do apt-get -o Acquire::Retries=3 update -qq && apt-get install -y -qq --no-install-recommends git >/dev/null && break; sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/copier-org/copier/archive/e05ddfec08bc580d3e7b6a2a3e7cb18b6c761ba5.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.8.0 \
    asttokens==3.0.2 \
    colorama==0.4.6 \
    coverage==7.16.2 \
    dunamai==1.26.2 \
    execnet==2.1.2 \
    executing==2.2.1 \
    funcy==2.1 \
    iniconfig==2.3.1 \
    inline-snapshot==0.36.0 \
    jinja2-ansible-filters==1.3.2 \
    Jinja2==3.1.6 \
    markdown-it-py==4.2.0 \
    MarkupSafe==3.0.4 \
    mdurl==0.1.2 \
    packaging==26.3 \
    pastel==0.2.1 \
    pathspec==1.1.1 \
    pexpect==4.9.0 \
    platformdirs==4.12.4 \
    pluggy==1.6.0 \
    plumbum==2.0.2 \
    poethepoet==0.48.0 \
    prompt_toolkit==3.0.53 \
    ptyprocess==0.7.0 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    Pygments==2.21.0 \
    pytest-cov==7.1.0 \
    pytest-gitconfig==0.9.0 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    PyYAML==6.0.3 \
    questionary==2.1.1 \
    rich==15.0.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    wcwidth==0.9.2
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
