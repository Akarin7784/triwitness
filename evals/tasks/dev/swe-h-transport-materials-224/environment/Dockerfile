# RemDelaporteMathurin__h-transport-materials-224（RemDelaporteMathurin/h-transport-materials @ 487452db12b4）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.10-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/RemDelaporteMathurin/h-transport-materials/archive/487452db12b4d4efc02cdac4a50799f1ef7e25d2.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    contourpy==1.3.1 \
    coverage==7.8.0 \
    crossrefapi==1.5.0 \
    cycler==0.12.1 \
    exceptiongroup==1.2.2 \
    flexcache==0.3 \
    flexparser==0.4 \
    fonttools==4.56.0 \
    idna==3.10 \
    iniconfig==2.1.0 \
    kiwisolver==1.4.8 \
    latexcodec==3.0.0 \
    matplotlib==3.10.1 \
    numpy==2.2.4 \
    packaging==24.2 \
    pillow==11.1.0 \
    Pint==0.24.4 \
    platformdirs==4.3.7 \
    pluggy==1.5.0 \
    pybtex==0.24.0 \
    pyparsing==3.2.3 \
    pytest-cov==4.0.0 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.2 \
    requests==2.32.3 \
    scipy==1.15.2 \
    six==1.17.0 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
