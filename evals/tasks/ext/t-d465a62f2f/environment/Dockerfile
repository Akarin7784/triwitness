# dstl__Stone-Soup-1167（dstl/Stone-Soup @ 6231f58db37b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/dstl/Stone-Soup/archive/6231f58db37ba76d93024600a26aca4dccbc16e8.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    absl-py==2.3.1 \
    alabaster==0.7.16 \
    babel==2.18.0 \
    branca==0.8.2 \
    certifi==2026.7.22 \
    charset-normalizer==3.5.2 \
    confluent-kafka==2.16.0 \
    contourpy==1.3.0 \
    coverage==7.10.7 \
    cycler==0.12.1 \
    docutils==0.21.2 \
    exceptiongroup==1.3.1 \
    flake8==7.3.0 \
    folium==0.20.0 \
    fonttools==4.60.2 \
    h5py==3.14.0 \
    idna==3.20 \
    imagesize==1.5.0 \
    immutabledict==4.3.1 \
    importlib_metadata==8.7.1 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    Jinja2==3.1.6 \
    kiwisolver==1.4.7 \
    MarkupSafe==3.0.4 \
    matplotlib==3.9.4 \
    mccabe==0.7.0 \
    mergedeep==1.3.4 \
    narwhals==2.21.0 \
    numpy==2.0.2 \
    ordered-set==4.1.0 \
    ortools==9.15.6755 \
    packaging==26.3 \
    pandas==2.3.3 \
    pillow==11.3.0 \
    plotly==7.1.0 \
    pluggy==1.6.0 \
    protobuf==6.33.6 \
    pycodestyle==2.14.0 \
    pyflakes==3.4.0 \
    Pygments==2.21.0 \
    pymap3d==3.2.0 \
    pyparsing==3.3.3 \
    pytest-cov==7.1.0 \
    pytest-remotedata==0.4.2 \
    pytest-skip-slow==1.1.0 \
    pytest==8.4.2 \
    python-dateutil==2.9.0.post0 \
    pytz==2026.5 \
    requests==2.32.5 \
    rtree==1.4.1 \
    ruamel.yaml==0.19.1 \
    scipy==1.13.1 \
    six==1.17.0 \
    snowballstemmer==3.1.1 \
    sphinx-gallery==0.19.0 \
    Sphinx==7.4.7 \
    sphinx_rtd_theme==3.1.0 \
    sphinxcontrib-applehelp==2.0.0 \
    sphinxcontrib-devhelp==2.0.0 \
    sphinxcontrib-htmlhelp==2.1.0 \
    sphinxcontrib-jquery==4.1 \
    sphinxcontrib-jsmath==1.0.1 \
    sphinxcontrib-qthelp==2.0.0 \
    sphinxcontrib-serializinghtml==2.0.0 \
    tomli==2.5.0 \
    typing_extensions==4.16.0 \
    tzdata==2026.5 \
    urllib3==2.6.3 \
    utm==0.8.1 \
    xyzservices==2026.9.1 \
    zipp==3.23.1
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
