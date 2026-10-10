# CrossGL__crosstl-257（CrossGL/crosstl @ bf894dbc9046）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1
ADD https://github.com/CrossGL/crosstl/archive/bf894dbc90466d1ed9ae942f44396fbd04f18298.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    exceptiongroup==1.2.2 \
    gast==0.6.0 \
    iniconfig==2.1.0 \
    packaging==24.2 \
    pluggy==1.5.0 \
    pytest==8.3.5 \
    tomli==2.2.1
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
