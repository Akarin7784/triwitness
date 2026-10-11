# getmoto__moto-9727（getmoto/moto @ 205025bdfc30）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/getmoto/moto/archive/205025bdfc302aec5e2f2eed20f1b58830b24914.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    boto3==1.43.111 \
    botocore==1.43.111 \
    certifi==2026.7.22 \
    cffi==2.1.1 \
    charset-normalizer==3.5.2 \
    coverage==7.16.2 \
    cryptography==50.0.2 \
    envs==1.4 \
    execnet==2.1.2 \
    freezegun==1.5.5 \
    idna==3.20 \
    iniconfig==2.3.1 \
    Jinja2==3.1.6 \
    jmespath==1.1.0 \
    MarkupSafe==3.0.4 \
    packaging==26.3 \
    pluggy==1.6.0 \
    pycognito==2024.5.1 \
    pycparser==3.11 \
    Pygments==2.21.0 \
    PyJWT==2.15.1 \
    PyOTP==2.10.0 \
    pytest-cov==7.1.0 \
    pytest-order==1.5.0 \
    pytest-xdist==3.8.0 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.3 \
    requests==2.34.2 \
    responses==0.26.3 \
    s3transfer==0.19.2 \
    six==1.17.0 \
    urllib3==2.8.0 \
    Werkzeug==3.1.9 \
    xmltodict==1.0.4
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
