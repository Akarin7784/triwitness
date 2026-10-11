# iris-hep__func_adl-184（iris-hep/func_adl @ 6f98f02049cc）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/iris-hep/func_adl/archive/6f98f02049ccb7207e35c032c614ec80e70b57e1.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    anyio==4.12.1 \
    astunparse==1.6.3 \
    backports.asyncio.runner==1.2.0 \
    backports.tarfile==1.2.0 \
    black==25.11.0 \
    certifi==2026.7.22 \
    cffi==2.0.0 \
    charset-normalizer==3.5.2 \
    click==8.1.8 \
    coverage==7.10.7 \
    cryptography==50.0.2 \
    distlib==0.4.3 \
    docutils==0.23 \
    exceptiongroup==1.3.1 \
    filelock==3.19.1 \
    flake8==7.3.0 \
    h11==0.16.0 \
    hatch==1.15.1 \
    hatchling==1.27.0 \
    httpcore==1.0.9 \
    httpx==0.28.1 \
    hyperlink==21.0.0 \
    id==1.6.1 \
    idna==3.20 \
    importlib_metadata==8.7.1 \
    iniconfig==2.1.0 \
    isort==6.1.0 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.1.1 \
    jaraco.functools==4.4.0 \
    jeepney==0.9.0 \
    keyring==25.7.0 \
    make-it-sync==2.1.1 \
    markdown-it-py==3.0.0 \
    mccabe==0.7.0 \
    mdurl==0.1.2 \
    more-itertools==10.8.0 \
    mypy_extensions==1.1.0 \
    nh3==0.3.7 \
    numpy==2.0.2 \
    packaging==26.3 \
    pathspec==1.1.1 \
    pexpect==4.9.0 \
    platformdirs==4.4.0 \
    pluggy==1.6.0 \
    ptyprocess==0.7.0 \
    pycodestyle==2.14.0 \
    pycparser==2.23 \
    pyflakes==3.4.0 \
    Pygments==2.21.0 \
    pytest-asyncio==1.2.0 \
    pytest-cov==7.1.0 \
    pytest==8.4.2 \
    python-discovery==1.6.2 \
    pytokens==0.4.1 \
    readme_renderer==44.0 \
    requests-toolbelt==1.0.0 \
    requests==2.32.5 \
    rfc3986==2.0.0 \
    rich==15.0.0 \
    SecretStorage==3.3.3 \
    shellingham==1.5.4 \
    six==1.17.0 \
    tomli==2.5.0 \
    tomli_w==1.2.0 \
    tomlkit==0.15.1 \
    trove-classifiers==2026.9.21.13 \
    twine==6.2.0 \
    typing_extensions==4.16.0 \
    urllib3==2.6.3 \
    userpath==1.9.2 \
    uv==0.13.0 \
    virtualenv==21.14.6 \
    zipp==3.23.1 \
    zstandard==0.25.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
