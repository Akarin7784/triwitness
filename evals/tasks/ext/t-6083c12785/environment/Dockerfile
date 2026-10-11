# cytomining__pycytominer-246（cytomining/pycytominer @ ea9873ddd3b7）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.9-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/cytomining/pycytominer/archive/ea9873ddd3b7d9b7072cf7fc55d582012cf6d315.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    agate-dbf==0.2.3 \
    agate-excel==0.4.1 \
    agate-sql==0.7.2 \
    agate==1.13.0 \
    babel==2.17.0 \
    backports.tempfile==1.0 \
    backports.weakref==1.0.post1 \
    click==8.1.8 \
    configparser==7.2.0 \
    csvkit==2.1.0 \
    cytominer-database==0.3.4 \
    dbfread==2.0.7 \
    et_xmlfile==2.0.0 \
    exceptiongroup==1.2.2 \
    greenlet==3.1.1 \
    importlib_metadata==8.6.1 \
    iniconfig==2.1.0 \
    isodate==0.7.2 \
    joblib==1.4.2 \
    leather==0.4.0 \
    numpy==2.0.2 \
    olefile==0.47 \
    openpyxl==3.1.5 \
    packaging==24.2 \
    pandas==2.2.3 \
    parsedatetime==2.6 \
    pluggy==1.5.0 \
    pyarrow==19.0.1 \
    pytest==8.3.5 \
    python-dateutil==2.9.0.post0 \
    python-slugify==8.0.4 \
    pytimeparse==1.1.8 \
    pytz==2025.2 \
    scikit-learn==1.6.1 \
    scipy==1.13.1 \
    six==1.17.0 \
    SQLAlchemy==2.0.40 \
    text-unidecode==1.3 \
    threadpoolctl==3.6.0 \
    tomli==2.2.1 \
    typing_extensions==4.13.0 \
    tzdata==2025.2 \
    xlrd==2.0.1 \
    zipp==3.21.0
RUN pip install --no-cache-dir -e /workspace/repo
RUN git config --system core.hooksPath /dev/null && rm -rf /workspace/repo/.git
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
