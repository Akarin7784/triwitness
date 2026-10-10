FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.3
WORKDIR /workspace/repo
COPY repo/ /workspace/repo/
RUN git --version >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*)
RUN git init -q && git add -A && git -c user.name=tw -c user.email=tw@local commit -qm base
