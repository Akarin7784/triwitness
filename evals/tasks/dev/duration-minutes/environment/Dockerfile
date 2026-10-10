# 依赖在构建时装好；运行时断网（network_mode = "no-network"）。国内网络可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.3
COPY repo/ /workspace/repo/
# 沙箱以 uid 1000 运行，仓库需可写
RUN chown -R 1000:1000 /workspace
WORKDIR /workspace/repo
