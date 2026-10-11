# craffel__mir_eval-249（craffel/mir_eval @ 6f8ee58f437d）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/craffel/mir_eval/archive/6f8ee58f437dd9b8f54b3c9700e7b4dc3879853f.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    contourpy==1.3.0 \
    cov-core==1.15.0 \
    coverage==7.8.0 \
    cycler==0.12.1 \
    exceptiongroup==1.2.2 \
    fonttools==4.56.0 \
    future==1.0.0 \
    importlib_resources==6.5.2 \
    iniconfig==2.1.0 \
    kiwisolver==1.4.7 \
    matplotlib==3.9.4 \
    nose-cov==1.6 \
    nose==1.3.7 \
    numpy==2.0.2 \
    packaging==24.2 \
    pillow==11.1.0 \
    pluggy==1.5.0 \
    pyparsing==3.2.3 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    scipy==1.13.1 \
    six==1.17.0 \
    tomli==2.2.1 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
