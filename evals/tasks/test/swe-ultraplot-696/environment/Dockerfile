# ultraplot__ultraplot-696（Ultraplot/UltraPlot @ 1567aa35dc56）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.13-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/Ultraplot/UltraPlot/archive/1567aa35dc5669b67babe76a929452e1c6d85fdb.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    biopython==1.88 \
    contourpy==1.4.0 \
    cycler==0.12.1 \
    fonttools==4.66.1 \
    iniconfig==2.3.1 \
    Jinja2==3.1.6 \
    kiwisolver==1.5.1 \
    MarkupSafe==3.0.4 \
    matplotlib==3.10.9 \
    numpy==2.5.3 \
    packaging==26.3 \
    pandas==3.0.6 \
    pillow==12.3.0 \
    pluggy==1.6.0 \
    pyCirclize==1.10.1 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest-mpl==0.19.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    six==1.17.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
