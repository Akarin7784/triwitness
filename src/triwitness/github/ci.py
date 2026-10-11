"""PR 分支的 CI 回流（W5-06，spec 012 §6）：轮询检查结果，失败时取精简日志交给 Executor 修。

不需要 GitHub App：两种取数方式与开 PR 一致——
- gh：`gh api repos/<o>/<r>/commits/<sha>/check-runs`（兼容老版本 gh，不依赖 `gh pr checks --json`），
  失败日志 `gh run view --job <id> --log-failed`；不读取 gh 的令牌。
- 令牌：环境变量 GITHUB_TOKEN 走 REST（check-runs + jobs/<id>/logs）。

状态归并（`summarize`）：
- 没有任何检查 → none（宽限期过后仍没有，认为仓库没配 CI）；
- 有未完成的 → pending；
- 完成且有 failure / timed_out / startup_failure → failure；
- 其余（success / neutral / skipped / cancelled …）→ success。cancelled / action_required 不当作代码问题。
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx

from triwitness.github.pr import _headers, api_base, redact
from triwitness.harness.context import wrap_untrusted

CiState = Literal["success", "failure", "pending", "none", "timeout"]
FAILING = frozenset({"failure", "timed_out", "startup_failure"})
_JOB = re.compile(r"/actions/runs/(\d+)/job(?:s)?/(\d+)")
_TS = re.compile(r"^\ufeff?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_SIGNAL = re.compile(
    r"(error|failed|failure|traceback|exception|assert|FAILED|ERROR|E\s{2,}|panic|Process completed with exit code)",
    re.I,
)


@dataclass(frozen=True)
class CheckRun:
    name: str
    status: str  # queued / in_progress / completed
    conclusion: str | None  # success / failure / neutral / cancelled / skipped / timed_out / action_required
    url: str = ""
    job_id: int | None = None
    run_id: int | None = None

    @property
    def failing(self) -> bool:
        return self.status == "completed" and (self.conclusion or "") in FAILING


@dataclass
class CiResult:
    state: CiState
    sha: str
    checks: list[CheckRun] = field(default_factory=list)
    logs: dict[str, str] = field(default_factory=dict)  # 失败检查名 → 精简日志
    waited_s: float = 0.0

    @property
    def failed(self) -> list[CheckRun]:
        return [c for c in self.checks if c.failing]

    def display(self) -> str:
        if self.state == "failure":
            names = "、".join(c.name for c in self.failed[:3])
            return f"CI 失败：{names}" + ("…" if len(self.failed) > 3 else "")
        return {"success": "CI 通过", "pending": "CI 仍在运行", "none": "仓库没有配置 CI 检查",
                "timeout": "等待 CI 超时"}.get(self.state, self.state)  # fmt: skip

    def to_json(self) -> dict[str, Any]:
        return {"state": self.state, "sha": self.sha, "waited_s": round(self.waited_s, 1),
                "checks": [c.__dict__ for c in self.checks], "failed": [c.name for c in self.failed]}  # fmt: skip


class CiClient(Protocol):
    def check_runs(self, repo: str, sha: str) -> list[CheckRun]: ...

    def job_log(self, repo: str, check: CheckRun) -> str: ...


def _parse_runs(data: dict[str, Any]) -> list[CheckRun]:
    out: list[CheckRun] = []
    for r in data.get("check_runs") or []:
        url = str(r.get("details_url") or r.get("html_url") or "")
        m = _JOB.search(url)
        out.append(CheckRun(name=str(r.get("name") or "?"), status=str(r.get("status") or "queued"),
                            conclusion=r.get("conclusion"), url=url,
                            job_id=int(m[2]) if m else None, run_id=int(m[1]) if m else None))  # fmt: skip
    return out


Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


class GhCiClient:
    """经本机已登录的 gh 取数（不读 gh 的令牌）。runner 可注入（测试）。"""

    def __init__(self, runner: Runner | None = None) -> None:
        self.runner = runner or _run

    def check_runs(self, repo: str, sha: str) -> list[CheckRun]:
        p = self.runner(["gh", "api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100"])
        if p.returncode != 0:
            raise RuntimeError(f"gh api check-runs 失败：{redact((p.stderr or p.stdout)[-300:])}")
        return _parse_runs(json.loads(p.stdout or "{}"))

    def job_log(self, repo: str, check: CheckRun) -> str:
        if check.job_id is None:
            return ""
        p = self.runner(["gh", "run", "view", "--repo", repo, "--job", str(check.job_id), "--log-failed"])
        if p.returncode != 0 or not p.stdout.strip():  # 有的失败没有“失败步骤”：退回全量日志
            p = self.runner(["gh", "run", "view", "--repo", repo, "--job", str(check.job_id), "--log"])
        return redact(p.stdout or "")


class TokenCiClient:
    """GITHUB_TOKEN 走 REST。令牌只放请求头，不进日志 / 异常。"""

    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self.token = token
        self.client = client

    def _get(self, url: str) -> httpx.Response:
        c = self.client or httpx.Client(timeout=60, follow_redirects=True)
        try:
            return c.get(url, headers=_headers(self.token))
        except httpx.HTTPError as e:
            raise RuntimeError(f"连不上 GitHub：{type(e).__name__}") from None
        finally:
            if self.client is None:
                c.close()

    def check_runs(self, repo: str, sha: str) -> list[CheckRun]:
        r = self._get(f"{api_base()}/repos/{repo}/commits/{sha}/check-runs?per_page=100")
        if r.status_code != 200:
            raise RuntimeError(f"取 CI 状态失败（HTTP {r.status_code}）")
        return _parse_runs(r.json())

    def job_log(self, repo: str, check: CheckRun) -> str:
        if check.job_id is None:
            return ""
        r = self._get(f"{api_base()}/repos/{repo}/actions/jobs/{check.job_id}/logs")
        return redact(r.text, self.token) if r.status_code == 200 else ""


def client_for(env: Mapping[str, str]) -> CiClient:
    token = env.get("GITHUB_TOKEN", "").strip()
    return TokenCiClient(token) if token else GhCiClient()


def summarize(checks: list[CheckRun]) -> CiState:
    if not checks:
        return "none"
    if any(c.status != "completed" for c in checks):
        return "pending"
    return "failure" if any(c.failing for c in checks) else "success"


def condense_log(text: str, max_chars: int = 6000) -> str:
    """去时间戳 / ANSI；保留命中错误信号的行（前后各 2 行）+ 最后 40 行，总长截到 max_chars。"""
    lines = []
    for raw in text.splitlines():
        ln = _ANSI.sub("", raw)
        ln = re.sub(r"^[^\t]*\t[^\t]*\t", "", ln) if ln.count("\t") >= 2 else ln  # gh --log：job\tstep\t内容
        lines.append(_TS.sub("", ln).rstrip())
    keep: set[int] = set()
    for i, ln in enumerate(lines):
        if _SIGNAL.search(ln):
            keep.update(range(max(0, i - 2), min(len(lines), i + 3)))
    keep.update(range(max(0, len(lines) - 40), len(lines)))
    out: list[str] = []
    prev = -2
    for i in sorted(keep):
        if i != prev + 1 and out:
            out.append("…")
        out.append(lines[i])
        prev = i
    s = "\n".join(out).strip()
    if len(s) > max_chars:
        s = "…（前略）\n" + s[-(max_chars - 8) :]
    return s


async def watch(
    client: CiClient,
    repo: str,
    sha: str,
    *,
    timeout_s: float = 1800,
    poll_s: float = 30,
    no_checks_grace_s: float = 120,
    log_max_chars: int = 6000,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> CiResult:
    """等到这个提交的检查全部结束（或超时 / 宽限期内没有检查），失败时取精简日志。"""
    t0 = clock()
    while True:
        checks = await asyncio.to_thread(client.check_runs, repo, sha)
        state = summarize(checks)
        waited = clock() - t0
        if state in ("success", "failure"):
            break
        if state == "none" and waited >= no_checks_grace_s:
            break
        if waited >= timeout_s:
            return CiResult("timeout", sha, checks, waited_s=waited)
        await sleep(poll_s)
    res = CiResult(state, sha, checks, waited_s=clock() - t0)
    per = max(800, log_max_chars // max(1, len(res.failed)))
    for c in res.failed[:4]:
        try:
            log = await asyncio.to_thread(client.job_log, repo, c)
        except Exception as e:  # 拿不到日志也照样返工：至少告诉 Executor 哪个检查挂了
            log = f"（取日志失败：{type(e).__name__}）"
        res.logs[c.name] = condense_log(log, per) if log else "（没有日志）"
    return res


def ci_feedback(res: CiResult) -> str:
    """给 Executor 的返工反馈（日志是不可信数据）。"""
    parts = [f"PR 分支上的 CI 失败了（提交 {res.sha[:10]}）。请根据下面的失败日志修复，只改与失败有关的代码，"
             "然后重新运行相关测试并调用 finish。不要修改 CI 配置来跳过检查，也不要删除或跳过测试。"]  # fmt: skip
    for c in res.failed:
        parts.append(f"### {c.name}（{c.conclusion}）{(' ' + c.url) if c.url else ''}")
        parts.append(wrap_untrusted(f"ci-log:{c.name}", res.logs.get(c.name, "（没有日志）")))
    return "\n\n".join(parts)


__all__ = ["CheckRun", "CiClient", "CiResult", "GhCiClient", "TokenCiClient", "ci_feedback", "client_for",
           "condense_log", "summarize", "watch"]  # fmt: skip
