"""run_tests 的辅助（W2-10）：解析 pytest junit XML、只保留失败用例的断言与栈、按改动文件推断相关测试。"""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_XML_BYTES = 4_000_000
PER_FAILURE_CHARS = 1500
MAX_FAILURES_SHOWN = 10
_DIFF_PATH = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)
_TEST_FILE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.py$")


@dataclass
class Failure:
    nodeid: str
    kind: str  # failure | error
    message: str
    detail: str


@dataclass
class JunitReport:
    tests: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[Failure] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return max(0, self.tests - self.failed - self.errors - self.skipped)

    def summary(self) -> str:
        parts = [f"{self.passed} passed"]
        for n, label in ((self.failed, "failed"), (self.errors, "errors"), (self.skipped, "skipped")):
            if n:
                parts.append(f"{n} {label}")
        return ", ".join(parts)


def nodeid(classname: str, name: str, file: str | None) -> str:
    """junit 的 classname（a.b.test_x.TestC）+ name → pytest 节点 id（a/b/test_x.py::TestC::name）。"""
    parts = classname.split(".") if classname else []
    if file:
        mod = file[:-3].replace("/", ".") if file.endswith(".py") else file
        rest = classname[len(mod) + 1 :].split(".") if classname.startswith(mod + ".") else []
        return "::".join([file, *[p for p in rest if p], name])
    # 没有 file 属性：从左边找最长的模块路径（以 test 开头的那段之前都算目录）
    for i in range(len(parts), 0, -1):
        if parts[i - 1].startswith("test") or parts[i - 1].endswith("_test"):
            return "::".join(["/".join(parts[:i]) + ".py", *parts[i:], name])
    return "::".join([*parts, name]) if parts else name


def _trim(text: str, limit: int = PER_FAILURE_CHARS) -> str:
    """只留断言与栈的关键部分：头 1/3 + 尾 2/3（结论在末尾）。"""
    text = text.strip()
    if len(text) <= limit:
        return text
    head = limit // 3
    return text[:head] + f"\n…（省略 {len(text) - limit} 字符）…\n" + text[-(limit - head) :]


def parse_junit(data: bytes) -> JunitReport | None:
    if not data or len(data) > MAX_XML_BYTES or b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return None  # 不信任沙箱里的 XML：拒绝 DTD / 实体（防实体膨胀）
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    rep = JunitReport()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    for s in suites:
        for tc in s.iter("testcase"):
            rep.tests += 1
            nid = nodeid(tc.get("classname", ""), tc.get("name", ""), tc.get("file"))
            if tc.find("skipped") is not None:
                rep.skipped += 1
                continue
            for kind in ("failure", "error"):
                el = tc.find(kind)
                if el is not None:
                    if kind == "failure":
                        rep.failed += 1
                    else:
                        rep.errors += 1
                    rep.failures.append(Failure(nid, kind, (el.get("message") or "").strip(), _trim(el.text or "")))
                    break
    return rep


def render_failures(rep: JunitReport) -> str:
    out = []
    for f in rep.failures[:MAX_FAILURES_SHOWN]:
        msg = f.message.splitlines()[0][:300] if f.message else ""
        out.append(f"── {'ERROR' if f.kind == 'error' else 'FAILED'} {f.nodeid}" + (f"\n{msg}" if msg else ""))
        if f.detail:
            out.append(f.detail)
    if len(rep.failures) > MAX_FAILURES_SHOWN:
        out.append(f"…另有 {len(rep.failures) - MAX_FAILURES_SHOWN} 个失败未展开（可用 selected / rerun_failed 单独跑）")
    return "\n".join(out)


def changed_paths(diff: str) -> list[str]:
    return sorted({b for _, b in _DIFF_PATH.findall(diff)})


def related_tests(changed: list[str], files: list[str]) -> list[str]:
    """改动的测试文件本身 + 按命名约定匹配的测试（foo.py → test_foo.py / foo_test.py；包名 → tests/<包>/）。"""
    tests = [f for f in files if _TEST_FILE.search(f)]
    out = {c for c in changed if _TEST_FILE.search(c) and c in files}
    for c in changed:
        if not c.endswith(".py") or _TEST_FILE.search(c):
            continue
        stem = posixpath.splitext(posixpath.basename(c))[0]
        if stem == "__init__":
            stem = posixpath.basename(posixpath.dirname(c))
        names = {f"test_{stem}.py", f"{stem}_test.py"}
        out.update(t for t in tests if posixpath.basename(t) in names)
    return sorted(out)
