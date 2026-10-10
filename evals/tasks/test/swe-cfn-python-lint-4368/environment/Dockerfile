# aws-cloudformation__cfn-python-lint-4368（aws-cloudformation/cfn-python-lint @ e52850cf757a）；依赖在构建时装好，运行时断网。
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \
      apt-get -o Acquire::Retries=3 update -qq && \
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD https://github.com/aws-cloudformation/cfn-python-lint/archive/e52850cf757a93a58d0535e775810a9e3f752792.tar.gz /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
RUN pip install --no-cache-dir \
    annotated-types==0.8.0 \
    attrs==26.1.0 \
    aws-sam-translator==1.114.0 \
    boto3==1.43.111 \
    botocore==1.43.111 \
    coverage==7.16.2 \
    defusedxml==0.7.1 \
    iniconfig==2.3.1 \
    jmespath==1.1.0 \
    jschema-to-python==1.2.3 \
    jsonpatch==1.34 \
    jsonpickle==4.1.3 \
    jsonpointer==3.2.0 \
    jsonschema-specifications==2025.9.1 \
    jsonschema==4.26.0 \
    junit-xml==1.9 \
    mpmath==1.3.0 \
    networkx==3.7 \
    packaging==26.3 \
    pbr==7.1.3 \
    pluggy==1.6.0 \
    pydantic==2.13.5 \
    pydantic_core==2.46.5 \
    pydot==4.0.1 \
    Pygments==2.21.0 \
    pyparsing==3.3.3 \
    pytest==9.1.1 \
    python-dateutil==2.9.0.post0 \
    PyYAML==6.0.3 \
    referencing==0.37.0 \
    regex==2026.9.29 \
    rpds-py==2026.9.1 \
    s3transfer==0.19.2 \
    sarif-om==1.0.4 \
    setuptools==84.0.0 \
    six==1.17.0 \
    sympy==1.14.0 \
    typing-inspection==0.4.4 \
    typing_extensions==4.16.0 \
    urllib3==2.8.0
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
