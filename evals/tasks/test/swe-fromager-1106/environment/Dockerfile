# python-wheel-build__fromager-1106（python-wheel-build/fromager @ f82c1e64a027）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do apt-get -o Acquire::Retries=3 update -qq && apt-get install -y -qq --no-install-recommends git >/dev/null && break; sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/python-wheel-build/fromager/archive/f82c1e64a027060c3e25090f6a4a4d7f4e3d985d.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.8.0 \
    anyio==4.15.1 \
    attrs==26.1.0 \
    beartype==0.22.9 \
    beautifulsoup4==4.15.0 \
    boolean.py==5.0 \
    certifi==2026.7.22 \
    cffi==2.1.1 \
    charset-normalizer==3.5.2 \
    click==8.5.0 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    docutils==0.23 \
    elfdeps==0.4.0 \
    h11==0.16.0 \
    hatch-vcs==0.5.0 \
    hatchling==1.32.4 \
    id==1.6.1 \
    idna==3.20 \
    iniconfig==2.3.1 \
    jaraco.classes==3.4.0 \
    jaraco.context==6.1.2 \
    jaraco.functools==4.6.0 \
    jeepney==0.9.0 \
    keyring==25.7.0 \
    license-expression==30.4.4 \
    mailbits==0.2.3 \
    markdown-it-py==4.2.0 \
    mdurl==0.1.2 \
    more-itertools==11.1.0 \
    nh3==0.3.7 \
    packageurl-python==0.17.6 \
    packaging==26.3 \
    pathspec==1.1.1 \
    pluggy==1.6.0 \
    ply==3.11 \
    psutil==7.2.2 \
    pycparser==3.11 \
    pydantic==2.14.0 \
    pydantic_core==2.50.0 \
    pyelftools==0.33 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pypi-simple==1.8.0 \
    pyproject_hooks==1.3.3 \
    pytest==9.1.1 \
    PyYAML==6.0.3 \
    rdflib==7.6.0 \
    readme_renderer==46.0 \
    requests-mock==1.12.1 \
    requests-toolbelt==1.0.0 \
    requests==2.34.2 \
    resolvelib==1.2.1 \
    rfc3986==2.0.0 \
    rich==15.0.0 \
    SecretStorage==3.5.0 \
    semantic-version==2.10.0 \
    setuptools-scm==10.3.4 \
    setuptools==84.0.0 \
    soupsieve==2.10 \
    spdx-tools==0.8.5 \
    starlette==1.7.0 \
    stevedore==5.9.1 \
    tomlkit==0.15.1 \
    tqdm==4.70.1 \
    trove-classifiers==2026.9.21.13 \
    twine==7.0.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    uritools==6.1.3 \
    urllib3==2.8.0 \
    uv==0.13.0 \
    uvicorn==0.54.0 \
    vcs-versioning==2.6.0 \
    wheel==0.48.0 \
    xmltodict==1.0.4
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
