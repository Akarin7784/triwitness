"""把 SWE-rebench 实例转成 TriWitness / Harbor 任务目录（W1-29，一次性导入；W2 的任务工厂会取代它）。

    uv run python scripts/import_swe_rebench.py PyCQA__pyflakes-765 Knio__pynmea2-124 ... [--suite dev]

做法（不需要 git 历史，镜像里也没有 .git，避免未来提交泄露答案）：
- 源码：GitHub 归档 tarball @ base_commit（构建时 ADD）；依赖按数据集记录的 pip freeze 固定版本，
  构建时装好，运行时断网；
- 隐藏测试：在宿主上把 test_patch 打到 base 源码上，取改动后的测试文件放进 tests/files/<原路径>，test.sh 覆盖后
  只跑 FAIL_TO_PASS + PASS_TO_PASS；
- 参考解：gold patch 打到 base 上后的完整文件，solve.sh 用 heredoc 写回；
- instruction.md = 原 Issue 正文；metadata 记录来源、许可证（仓库许可证 + 数据集 CC-BY-4.0）、created_at = Issue 时间。
国内网络：构建慢时可在 Dockerfile 的 pip 命令加 -i https://mirrors.aliyun.com/pypi/simple（见文件内注释）。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shlex
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

DATASET = "nebius/SWE-rebench"
ROWS_API = (
    "https://datasets-server.huggingface.co/rows?dataset={ds}&config=default&split=filtered&offset={off}&length=100"
)
ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache" / "triwitness" / "swe-rebench-rows.json"
PYTEST = "pytest==8.3.5"


def fetch_rows(ids: set[str], max_pages: int = 30) -> dict[str, dict]:
    cache: dict[str, dict] = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    off = 0
    while not ids <= cache.keys() and off < max_pages * 100:
        with urllib.request.urlopen(ROWS_API.format(ds=DATASET, off=off), timeout=60) as r:
            for row in json.load(r)["rows"]:
                cache[row["row"]["instance_id"]] = row["row"]
        off += 100
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))
    missing = ids - cache.keys()
    if missing:
        raise SystemExit(f"数据集中找不到：{sorted(missing)}")
    return {i: cache[i] for i in ids}


def tarball_url(repo: str, sha: str) -> str:
    return f"https://github.com/{repo}/archive/{sha}.tar.gz"


def extract_source(repo: str, sha: str, dest: Path) -> None:
    with urllib.request.urlopen(tarball_url(repo, sha), timeout=120) as r:
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        for m in tf.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            m.name = parts[1]
            tf.extract(m, dest, filter="data")


def apply(patch: str, cwd: Path) -> list[str]:
    subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], input=patch.encode(), cwd=cwd, check=True)
    return re.findall(r"^diff --git a/\S+ b/(\S+)$", patch, re.M)


def pins(row: dict) -> list[str]:
    out = [t for t in (row.get("requirements") or "").split() if re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[\w.\-+]+", t)]
    if not any(t.lower().startswith("pytest==") for t in out):
        out.append(PYTEST)
    return sorted(out, key=str.lower)


def heredoc(path: str, content: str) -> str:
    tag = "TW_EOF"
    assert f"\n{tag}\n" not in content
    return f"mkdir -p {shlex.quote(str(Path(path).parent))}\ncat > {shlex.quote(path)} <<'{tag}'\n{content}{tag}\n"


def write(p: Path, s: str, mode: int = 0o644) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")
    p.chmod(mode)


def toml_list(xs: list[str]) -> str:
    return "[\n" + "".join(f"  {json.dumps(x)},\n" for x in xs) + "]"


def dockerfile(row: dict, py: str) -> str:
    """三种安装方式：数据集自带 pip freeze（filtered 拆分）→ 固定版本；任务工厂第一阶段（`_install`）→ 按数据集的
    安装命令装（构建时联网）；任务工厂第二阶段（`_pins`，第一阶段镜像里 pip freeze 的结果）→
    固定版本 + 仓库本身 --no-deps。"""
    iid = row["instance_id"]
    head = f"# {iid}（{row['repo']} @ {row['base_commit'][:12]}）；依赖在构建时装好，运行时断网。"
    out = f"""{head}
# 国内网络：pip 命令可加 -i https://mirrors.aliyun.com/pypi/simple
FROM python:{py}-slim
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
RUN for i in 1 2 3 4 5; do \\
      apt-get -o Acquire::Retries=3 update -qq && \\
      apt-get install -y -qq --no-install-recommends git >/dev/null && break; \\
      sleep 10; done; git --version && rm -rf /var/lib/apt/lists/*
ADD {tarball_url(row["repo"], row["base_commit"])} /tmp/src.tar.gz
RUN mkdir -p /workspace/repo && tar xzf /tmp/src.tar.gz -C /workspace/repo --strip-components=1 && rm /tmp/src.tar.gz
"""
    if row.get("_install"):
        out += f"""WORKDIR /workspace/repo
RUN {row["_install"]}
RUN pip install --no-cache-dir -q {PYTEST.split("==")[0]} && (pip install --no-cache-dir -q --no-deps -e . || true)
"""
    elif row.get("_pins"):
        lines = " \\\n    ".join(row["_pins"])
        out += f"""RUN pip install --no-cache-dir \\
    {lines}
RUN pip install --no-cache-dir --no-deps -e /workspace/repo || true
"""
    else:
        lines = " \\\n    ".join(pins(row))
        out += f"""RUN pip install --no-cache-dir \\
    {lines}
RUN pip install --no-cache-dir -e /workspace/repo
"""
    return out + "RUN chown -R 1000:1000 /workspace\nWORKDIR /workspace/repo\n"


def convert(row: dict, suite: str) -> Path:
    iid = row["instance_id"]
    owner_repo, num = iid.rsplit("-", 1)
    name = f"swe-{owner_repo.split('__', 1)[1].lower()}-{num}"
    d = ROOT / "evals" / "tasks" / suite / name
    py = (row.get("install_config") or {}).get("python") or "3.11"
    f2p = row["FAIL_TO_PASS"] if isinstance(row["FAIL_TO_PASS"], list) else json.loads(row["FAIL_TO_PASS"])
    p2p = row["PASS_TO_PASS"] if isinstance(row["PASS_TO_PASS"], list) else json.loads(row["PASS_TO_PASS"])
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "src"
        base.mkdir()
        extract_source(row["repo"], row["base_commit"], base)
        tests = apply(row["test_patch"], base)
        hidden = {t: (base / t).read_text(encoding="utf-8") for t in tests if (base / t).exists()}
        gold = apply(row["patch"], base)
        fixed = {g: (base / g).read_text(encoding="utf-8") for g in gold}
    if d.exists():
        import shutil

        shutil.rmtree(d)
    created = str(row["created_at"])[:10]
    lic = row.get("license_name") or row.get("_license") or "unknown"
    dataset = row.get("_dataset") or DATASET
    write(
        d / "task.toml",
        f'''schema_version = "1.3"

[task]
name = "triwitness/{name}"
description = {json.dumps(f"SWE-rebench {iid}")}
keywords = ["python", "bugfix", "swe-rebench"]

[metadata]
source = "swe-rebench"
repo = "https://github.com/{row["repo"]}"
base_commit = "{row["base_commit"]}"
difficulty = "easy"
tags = ["python", "real-world"]
created_at = "{created}"
license = {json.dumps(f"{lic}（代码）；SWE-rebench 数据集 CC-BY-4.0")}
dataset = "{dataset}"
instance_id = "{iid}"

[agent]
timeout_sec = 1200

[verifier]
timeout_sec = 300

[environment]
network_mode = "no-network"
cpus = 1
memory_mb = 2048
workdir = "/workspace/repo"

[tw]
test_cmd = "python -m pytest -q -x"
fail_to_pass = {toml_list(f2p)}
pass_to_pass = {toml_list(p2p)}
max_cost_cny = 0.5
''',
    )
    write(d / "instruction.md", row["problem_statement"].strip() + "\n")
    write(d / "environment" / "Dockerfile", dockerfile(row, py))
    for rel, content in hidden.items():
        write(d / "tests" / "files" / rel, content)
    ids = " \\\n  ".join(shlex.quote(t) for t in [*f2p, *p2p])
    write(
        d / "tests" / "test.sh",
        f"""#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \\
  {ids}; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
""",
        0o755,
    )
    solve = "#!/usr/bin/env bash\n# gold patch 之后的完整文件\nset -euo pipefail\ncd /workspace/repo\n"
    solve += "".join(heredoc(p, c) for p, c in fixed.items())
    write(d / "solution" / "solve.sh", solve, 0o755)
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description="SWE-rebench → TriWitness 任务目录")
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--suite", default="dev")
    a = ap.parse_args()
    rows = fetch_rows(set(a.ids))
    for i in a.ids:
        print(convert(rows[i], a.suite).relative_to(ROOT))


if __name__ == "__main__":
    main()
