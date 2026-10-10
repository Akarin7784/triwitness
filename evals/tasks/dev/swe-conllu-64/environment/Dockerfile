# EmilStenstrom__conllu-64（EmilStenstrom/conllu @ e9c8f2c6ab39）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.8-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1
ADD https://github.com/EmilStenstrom/conllu/archive/e9c8f2c6ab390c706680c6077d344cecffb71397.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    coverage==7.6.1 \
    flake8==7.1.2 \
    isort==5.13.2 \
    mccabe==0.7.0 \
    pycodestyle==2.12.1 \
    pyflakes==3.2.0 \
    pytest==8.3.5
RUN pip install --no-cache-dir -e /workspace/repo
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
