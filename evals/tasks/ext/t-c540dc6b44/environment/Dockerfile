# 0b01001001__spectree-64（0b01001001/spectree @ a091fab020ac）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/0b01001001/spectree/archive/a091fab020ac26548250c907bae0855273a98778.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.7.0 \
    anyio==4.9.0 \
    blinker==1.9.0 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    click==8.1.8 \
    exceptiongroup==1.2.2 \
    falcon==4.0.2 \
    Flask==3.1.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    itsdangerous==2.2.0 \
    Jinja2==3.1.6 \
    MarkupSafe==3.0.2 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pydantic==2.11.1 \
    pydantic_core==2.33.0 \
    pytest==8.3.5 \
    requests==2.32.3 \
    sniffio==1.3.1 \
    starlette==0.46.1 \
    tomli==2.2.1 \
    typing-inspection==0.4.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    Werkzeug==3.1.3 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
