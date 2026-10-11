"""仓库级密钥扫描（CI 在 pytest 之前跑；本地提交前也可以跑）。

对 `git ls-files` 里的每个文本文件用 `triwitness.eval.task_hardening.redact_secrets` 的同一套规则查：
预签名链接（S3 / GCS / Azure SAS / CloudFront / token=）、AWS 访问密钥 ID、GitHub / Slack / OpenAI 风格令牌、私钥块。
命中且不在白名单里 → 退出码 1，只打印 文件:行号 + 种类，不打印密钥原文。

白名单 `scripts/secret_scan_allow.txt`：每行 `<glob>  <种类|*>`，只放测试夹具里故意写的假密钥。
起因：2026-10-12 GitHub secret scanning 告警 #1
（上游公开 Issue 里 CircleCI 产物的 S3 预签名链接带了第三方临时 AWS 密钥 ID）。

用法：uv run python scripts/secret_scan.py [--paths 路径 ...]
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from triwitness.eval.task_hardening import redact_secrets  # noqa: E402

ALLOW = ROOT / "scripts" / "secret_scan_allow.txt"
MAX_BYTES = 5 * 1024 * 1024


def load_allow(path: Path = ALLOW) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if path.is_file():
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                glob, _, kind = ln.partition(" ")
                out.append((glob, kind.strip() or "*"))
    return out


def allowed(rel: str, kind: str, allow: list[tuple[str, str]]) -> bool:
    return any(fnmatch.fnmatch(rel, g) and k in ("*", kind) for g, k in allow)


def scan_text(text: str) -> list[tuple[int, str]]:
    """返回 [(行号, 种类)]；按行查，私钥块再按全文查一次（跨行）。"""
    hits: list[tuple[int, str]] = []
    for i, ln in enumerate(text.splitlines(), 1):
        _, kinds = redact_secrets(ln)
        hits += [(i, k) for k in kinds]
    if "PRIVATE KEY" in text and not any(k == "private_key" for _, k in hits):
        _, kinds = redact_secrets(text)
        if "private_key" in kinds:
            line = text[: text.index("PRIVATE KEY")].count("\n") + 1
            hits.append((line, "private_key"))
    return hits


def tracked(root: Path = ROOT) -> list[str]:
    res = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return [p for p in res.stdout.decode().split("\0") if p]


def scan(paths: list[str], *, root: Path = ROOT, allow: list[tuple[str, str]] | None = None) -> list[str]:
    allow = load_allow() if allow is None else allow
    problems: list[str] = []
    for rel in paths:
        f = root / rel
        if not f.is_file() or f.stat().st_size > MAX_BYTES:
            continue
        data = f.read_bytes()
        if b"\0" in data[:8192]:
            continue  # 二进制
        text = data.decode("utf-8", errors="replace")
        for line, kind in scan_text(text):
            if not allowed(rel, kind, allow):
                problems.append(f"{rel}:{line}: {kind}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", nargs="*", help="只查这些文件（默认：git ls-files 全部）")
    a = ap.parse_args(argv)
    paths = a.paths if a.paths else tracked()
    problems = scan(paths)
    for p in problems:
        print(f"疑似凭据：{p}")
    print(f"密钥扫描：{len(paths)} 个文件，{len(problems)} 处命中" + ("" if problems else "，通过"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
