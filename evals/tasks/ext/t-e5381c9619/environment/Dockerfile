# awdeorio__mailmerge-135（awdeorio/mailmerge @ 930bc506f0f8）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/awdeorio/mailmerge/archive/930bc506f0f8d0c9c057019c399a491c1641909c.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    astroid==3.3.9 \
    attrs==25.3.0 \
    backports.tarfile==1.2.0 \
    build==1.2.2.post1 \
    cachetools==5.5.2 \
    certifi==2025.1.31 \
    cffi==1.17.1 \
    chardet==5.2.0 \
    charset-normalizer==3.4.1 \
    check-manifest==0.50 \
    click==8.1.8 \
    colorama==0.4.6 \
    coverage==7.8.0 \
    cryptography==44.0.2 \
    dill==0.3.9 \
    distlib==0.3.9 \
    docutils==0.21.2 \
    fancycompleter==0.9.1 \
    filelock==3.18.0 \
    freezegun==1.5.1 \
    html5==0.0.9 \
    id==1.5.0 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    isort==6.0.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.0.1 \
    jaraco.functools==4.1.0 \
    jeepney==0.9.0 \
    Jinja2==3.1.6 \
    keyring==25.6.0 \
    markdown-it-py==3.0.0 \
    Markdown==3.7 \
    MarkupSafe==3.0.2 \
    mccabe==0.7.0 \
    mdurl==0.1.2 \
    more-itertools==10.6.0 \
    nh3==0.2.21 \
    pdbpp==0.10.3 \
    platformdirs==4.3.7 \
    pycodestyle==2.13.0 \
    pycparser==2.22 \
    pydocstyle==6.3.0 \
    Pygments==2.19.1 \
    pylint==3.3.6 \
    pyproject-api==1.9.0 \
    pyproject_hooks==1.2.0 \
    pyrepl==0.9.0 \
    pytest-cov==6.0.0 \
    pytest-mock==3.14.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    readme_renderer==44.0 \
    requests-toolbelt==1.0.0 \
    requests==2.32.3 \
    rfc3986==2.0.0 \
    rich==14.0.0 \
    SecretStorage==3.3.3 \
    six==1.17.0 \
    snowballstemmer==2.2.0 \
    tomli==2.2.1 \
    tomlkit==0.13.2 \
    tox==4.25.0 \
    twine==6.1.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    virtualenv==20.29.3 \
    webencodings==0.5.1 \
    wmctrl==0.5 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
