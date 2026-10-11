# PyCQA__isort-1995（PyCQA/isort @ 4e3ccb1c635b）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/PyCQA/isort/archive/4e3ccb1c635badad59fb0dd95ef8923a95390f21.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.7.0 \
    asttokens==3.0.0 \
    attrs==25.3.0 \
    backcall==0.2.0 \
    beautifulsoup4==4.13.3 \
    bleach==6.2.0 \
    Cerberus==1.3.7 \
    certifi==2025.1.31 \
    charset-normalizer==3.4.1 \
    decorator==5.2.1 \
    defusedxml==0.7.1 \
    distlib==0.3.9 \
    docopt==0.6.2 \
    executing==2.2.0 \
    fastjsonschema==2.21.1 \
    idna==3.10 \
    importlib_metadata==8.6.1 \
    ipython==8.12.3 \
    jedi==0.19.2 \
    Jinja2==3.1.6 \
    jsonschema-specifications==2024.10.1 \
    jsonschema==4.23.0 \
    jupyter_client==8.6.3 \
    jupyter_core==5.7.2 \
    jupyterlab_pygments==0.3.0 \
    MarkupSafe==3.0.2 \
    matplotlib-inline==0.1.7 \
    mistune==3.1.3 \
    nbclient==0.10.2 \
    nbconvert==7.16.6 \
    nbformat==5.10.4 \
    pandocfilters==1.5.1 \
    parso==0.8.4 \
    pep517==0.13.1 \
    pexpect==4.9.0 \
    pickleshare==0.7.5 \
    pip-api==0.0.34 \
    pip-shims==0.7.3 \
    pipreqs==0.5.0 \
    platformdirs==4.3.7 \
    plette==2.1.0 \
    prompt_toolkit==3.0.50 \
    ptyprocess==0.7.0 \
    pure_eval==0.2.3 \
    pydantic==2.11.1 \
    pydantic_core==2.33.0 \
    Pygments==2.19.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    pyzmq==26.3.0 \
    referencing==0.36.2 \
    requests==2.32.3 \
    requirementslib==3.0.0 \
    rpds-py==0.24.0 \
    six==1.17.0 \
    soupsieve==2.6 \
    stack-data==0.6.3 \
    tinycss2==1.4.0 \
    tomlkit==0.13.2 \
    tornado==6.4.2 \
    traitlets==5.14.3 \
    typing-inspection==0.4.0 \
    typing_extensions==4.13.0 \
    urllib3==2.3.0 \
    wcwidth==0.2.13 \
    webencodings==0.5.1 \
    yarg==0.1.9 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
