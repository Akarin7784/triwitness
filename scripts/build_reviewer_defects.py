"""W4-13：Reviewer 注入缺陷集（spec 012-draft §?；04 §6.2“Reviewer 有效发现率”）。

在“已解决任务的正确 diff”（gold：evals/tasks/*/solution/solve.sh 写出的修复后文件 vs 基线提交）里注入有代表性的缺陷，
同时保留不注入的干净对照组。每条都有标注的真值（缺陷的文件 / 行 / 类别 / 说明），Reviewer 消融（W4-14）只在这些
diff 上跑评审，不重跑 Executor。

用法：
  uv run python scripts/build_reviewer_defects.py gold    # 取 gold diff（swe 任务按需下载基线文件，缓存到 .cache/）
  uv run python scripts/build_reviewer_defects.py build   # 读 evals/reviewer/injections.yaml → evals/reviewer/items/
  uv run python scripts/build_reviewer_defects.py check   # 校验：每条 diff 能干净地应用到基线、真值行在 diff 里

不调用任何模型；不改 evals/tasks/ 下的任何文件。
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "evals" / "tasks"
OUT = ROOT / "evals" / "reviewer"
CACHE = ROOT / ".cache" / "reviewer-defects"
HEREDOC = re.compile(r"^cat > (?P<path>\S+) <<'(?P<tag>\w+)'\n(?P<body>.*?)^(?P=tag)\n", re.M | re.S)
TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def task_dir(task: str) -> Path:
    for split in ("dev", "test"):
        d = TASKS / split / task
        if d.is_dir():
            return d
    raise SystemExit(f"找不到任务 {task}")


def post_files(task: str) -> dict[str, str]:
    """solve.sh 里 heredoc 写出的修复后文件（只要非测试文件：评审看的是源码改动）。"""
    text = (task_dir(task) / "solution" / "solve.sh").read_text(encoding="utf-8")
    out = {m["path"]: m["body"] for m in HEREDOC.finditer(text)}
    return {p: b for p, b in out.items() if not TEST_PATH.search(p)}


def base_file(task: str, path: str) -> str | None:
    """基线版本：合成任务读 environment/repo；swe 任务按 base_commit 从 GitHub 取单个文件（缓存）。None = 新文件。"""
    d = task_dir(task)
    meta = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))
    local = d / "environment" / "repo" / path
    if (d / "environment" / "repo").is_dir():
        return local.read_text(encoding="utf-8") if local.is_file() else None
    repo = meta["metadata"]["repo"].removeprefix("https://github.com/").removesuffix(".git")
    commit = meta["metadata"]["base_commit"]
    cached = CACHE / task / (path.replace("/", "__") + ".base")
    missing = cached.with_suffix(".missing")
    if cached.is_file():
        return cached.read_text(encoding="utf-8")
    if missing.is_file():
        return None
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    cached.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            missing.write_text("", encoding="utf-8")
            return None
        raise
    cached.write_text(text, encoding="utf-8")
    return text


def unified(path: str, before: str | None, after: str) -> str:
    a = (before or "").splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    for lines in (a, b):
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n\\ No newline at end of file\n"
    head = f"--- {'a/' + path if before is not None else '/dev/null'}\n+++ b/{path}\n"
    body = "".join(difflib.unified_diff(a, b, n=3))
    body = "".join(body.splitlines(keepends=True)[2:])  # 去掉 difflib 自己的 ---/+++ 行
    if not body:
        return ""
    new = "new file mode 100644\n" if before is None else ""
    return f"diff --git a/{path} b/{path}\n{new}{head}{body}"


def diff_for(task: str, files: dict[str, str]) -> str:
    return "".join(unified(p, base_file(task, p), files[p]) for p in sorted(files))


def added_lines(task: str, files: dict[str, str]) -> dict[str, set[int]]:
    """每个文件在修复后版本里属于改动（新增 / 修改）的行号（1 起）。"""
    out: dict[str, set[int]] = {}
    for p, after in files.items():
        before = (base_file(task, p) or "").splitlines()
        sm = difflib.SequenceMatcher(a=before, b=after.splitlines(), autojunk=False)
        rows: set[int] = set()
        for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "insert"):
                rows.update(range(j1 + 1, j2 + 1))
        out[p] = rows
    return out


def cmd_gold(tasks: list[str]) -> None:
    gold = OUT / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        files = post_files(t)
        d = diff_for(t, files)
        (gold / f"{t}.diff").write_text(d, encoding="utf-8")
        n_add = sum(1 for ln in d.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
        n_del = sum(1 for ln in d.splitlines() if ln.startswith("-") and not ln.startswith("---"))
        print(f"{t}: {len(files)} 个源码文件，+{n_add} -{n_del}")


def inject(text: str, find: str, replace: str, where: str) -> tuple[str, int]:
    """把 find（必须恰好出现一次）替换成 replace；返回新文本与缺陷所在行（替换后第一处变化的行，1 起）。"""
    n = text.count(find)
    if n != 1:
        raise SystemExit(f"{where}：find 出现 {n} 次（必须恰好 1 次）：{find!r}")
    i = text.index(find)
    new = text[:i] + replace + text[i + len(find) :]
    old_lines, new_lines = text.splitlines(), new.splitlines()
    line = next((k + 1 for k, (x, y) in enumerate(zip(old_lines, new_lines, strict=False)) if x != y),
                min(len(old_lines), len(new_lines)) + 1)  # fmt: skip
    return new, line


def cmd_build() -> None:
    spec = yaml.safe_load((OUT / "injections.yaml").read_text(encoding="utf-8"))
    items = OUT / "items"
    if items.exists():
        shutil.rmtree(items)
    items.mkdir(parents=True)
    manifest: list[dict[str, Any]] = []
    for entry in spec["items"]:
        task = entry["task"]
        files = post_files(task)
        issue = (task_dir(task) / "instruction.md").read_text(encoding="utf-8")
        clean = diff_for(task, files)
        # 干净对照：gold 原样
        cid = f"{entry['id']}-clean"
        _write(items / cid, task, issue, clean, None)
        manifest.append({"id": cid, "task": task, "kind": "clean", "defect": None})
        # 缺陷版：在修复后文件里替换一处
        path = entry["file"]
        if path not in files:
            raise SystemExit(f"{entry['id']}：{path} 不在 gold 的源码改动里")
        bad, line = inject(files[path], entry["find"], entry["replace"], entry["id"])
        defect_files = {**files, path: bad}
        in_diff = line in added_lines(task, defect_files)[path]
        if not in_diff and not entry.get("allow_outside_diff"):
            raise SystemExit(f"{entry['id']}：缺陷行 {path}:{line} 不在 diff 的改动行里（评审看不到）")
        truth = {"file": path, "line": line, "category": entry["category"],
                 "severity": entry.get("severity", "blocker"), "description": entry["description"],
                 "in_changed_lines": in_diff}  # fmt: skip
        did = f"{entry['id']}-defect"
        _write(items / did, task, issue, diff_for(task, defect_files), truth)
        manifest.append({"id": did, "task": task, "kind": "defect", "defect": truth})
    blob = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    n_defect = sum(m["kind"] == "defect" for m in manifest)
    doc = {"name": "reviewer-defects", "version": spec.get("version", 1),
           "digest": hashlib.sha256(blob).hexdigest()[:16], "n_defect": n_defect,
           "n_clean": len(manifest) - n_defect, "items": manifest}  # fmt: skip
    (OUT / "manifest.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{doc['n_defect']} 条缺陷 + {doc['n_clean']} 条对照，digest {doc['digest']}")


def _write(d: Path, task: str, issue: str, patch: str, truth: dict[str, Any] | None) -> None:
    d.mkdir(parents=True)
    (d / "patch.diff").write_text(patch, encoding="utf-8")
    (d / "issue.md").write_text(issue, encoding="utf-8")
    (d / "item.json").write_text(json.dumps({"task": task, "kind": "defect" if truth else "clean", "truth": truth},
                                            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # fmt: skip


def cmd_check() -> None:
    """每条 diff：对基线文件逐个打补丁（difflib 反算）能还原出 diff 里的修复后版本；缺陷条目真值行确实被改。"""
    doc = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    bad = 0
    for m in doc["items"]:
        d = OUT / "items" / m["id"]
        patch = (d / "patch.diff").read_text(encoding="utf-8")
        if not patch.strip():
            print(f"✗ {m['id']}：空 diff")
            bad += 1
        if m["kind"] == "defect" and f"+++ b/{m['defect']['file']}" not in patch:
            print(f"✗ {m['id']}：diff 里没有真值文件")
            bad += 1
        with tempfile.TemporaryDirectory() as tmp:  # 基线文件 + git apply --check：diff 能干净地打上去
            for path in re.findall(r"^diff --git a/(\S+) b/", patch, re.M):
                base = base_file(m["task"], path)
                if base is not None:
                    (Path(tmp) / path).parent.mkdir(parents=True, exist_ok=True)
                    (Path(tmp) / path).write_text(base, encoding="utf-8")
            r = subprocess.run(["git", "apply", "--check", "-"], cwd=tmp, input=patch, text=True, capture_output=True)
            if r.returncode != 0:
                print(f"✗ {m['id']}：git apply --check 失败：{r.stderr.strip()[:200]}")
                bad += 1
    print(f"{len(doc['items'])} 条，问题 {bad} 个")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "gold":
        cmd_gold(sys.argv[2:])
    elif cmd == "build":
        cmd_build()
    elif cmd == "check":
        cmd_check()
    else:
        raise SystemExit(__doc__)
