# scipp__plopp-422（scipp/plopp @ 239103c412e2）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.10-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/scipp/plopp/archive/239103c412e27e47867033ade0c2aaf07574ef6e.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    asttokens==3.0.2 \
    comm==0.2.3 \
    contourpy==1.3.2 \
    cycler==0.12.1 \
    decorator==5.3.1 \
    exceptiongroup==1.3.1 \
    executing==2.3.0 \
    fonttools==4.65.0 \
    graphviz==0.21 \
    iniconfig==2.3.1 \
    ipydatawidgets==4.3.5 \
    ipympl==0.10.0 \
    ipython==8.39.0 \
    ipywidgets==8.1.9 \
    jedi==0.20.0 \
    jupyterlab_widgets==3.0.17 \
    kiwisolver==1.5.1 \
    lazy-loader==0.6 \
    matplotlib-inline==0.2.2 \
    matplotlib==3.10.9 \
    mpltoolbox==25.5.0 \
    numpy==2.2.6 \
    packaging==26.3 \
    parso==0.8.7 \
    pexpect==4.9.0 \
    pillow==12.3.0 \
    pluggy==1.6.0 \
    prompt_toolkit==3.0.53 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.4 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    pythreejs==2.4.2 \
    scipp==25.5.1 \
    six==1.17.0 \
    stack-data==0.6.3 \
    tomli==2.5.0 \
    traitlets==5.16.1 \
    traittypes==0.2.3 \
    typing_extensions==4.16.0 \
    wcwidth==0.9.2 \
    widgetsnbextension==4.0.16
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
