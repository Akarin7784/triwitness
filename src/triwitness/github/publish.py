"""编排器收尾时开 PR + 盯 CI（W5-04 / W5-05 / W5-06，spec 012 §4–§6）。不需要 GitHub App：用 gh 或细粒度令牌。

- `pr_action(risk, cfg)`：按风险等级决定 auto / confirm / draft / none（`HarnessConfig.github.pr_policy`）。
- `GitHubPublisher`：把沙箱当前改动提交到 `tw/<run_id>` 分支 → 推送 → 开 PR（幂等键 `<run_id>:open_pr:0`），
  CI 返工后再提交 + 推送（幂等键 `<run_id>:push:<n>`），并按提交 sha 盯 CI。
- 只在 `tw run --open-pr` 时由 run_local 构造；评测永远不开 PR。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from triwitness.core.models import RiskLevel
from triwitness.github.ci import CiClient, CiResult, client_for, watch
from triwitness.github.pr import (
    PrError,
    PrPlan,
    _git,
    _title,
    detect_auth,
    open_pr,
    parse_remote,
    push_branch,
    record_pr,
)
from triwitness.harness.config import CiWatchConfig, GithubConfig, PrAction
from triwitness.store.idempotency import SideEffectLog, side_effect_key


def pr_action(risk: RiskLevel | None, cfg: GithubConfig) -> PrAction:
    level = risk or cfg.unknown_risk
    return cfg.pr_policy.get(level, "none")  # type: ignore[arg-type]


@dataclass(frozen=True)
class PrRef:
    url: str
    number: int | None
    repo: str  # owner/name
    head: str
    sha: str
    draft: bool
    created: bool
    reused: bool


class Publisher(Protocol):
    async def open(self, *, title: str, body: str, draft: bool) -> PrRef: ...

    async def push(self, n: int) -> str: ...

    async def ci(self, sha: str, cfg: CiWatchConfig) -> CiResult: ...


class CommitsBranch(Protocol):
    branch: str

    async def commit_branch(self, message: str) -> str | None: ...


class GitHubPublisher:
    def __init__(
        self,
        *,
        sandbox: CommitsBranch,
        repo_path: Path,
        run_id: str,
        home: Path,
        remote: str = "origin",
        base: str | None = None,
        env: Mapping[str, str] | None = None,
        ci_client: CiClient | None = None,
        push_url: str | None = None,
        http_client: Any = None,  # 测试：httpx.Client(MockTransport)
    ) -> None:
        self.sb = sandbox
        self.repo_path = repo_path
        self.run_id = run_id
        self.home = home
        self.remote = remote
        self.base = base
        self.env = dict(os.environ if env is None else env)
        self.ci_client = ci_client
        self.push_url = push_url
        self.http_client = http_client
        self.plan: PrPlan | None = None

    def _plan(self, title: str, body: str) -> PrPlan:
        repo = self.repo_path
        url = _git(repo, "remote", "get-url", self.remote, check=False)
        if not url:
            raise PrError(f"仓库没有名为 {self.remote} 的远端，没法开 PR")
        owner, name = parse_remote(url)
        base = self.base
        if base is None:
            cur = _git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False)
            base = cur if cur and cur != "HEAD" and not cur.startswith("tw/") else "main"
        head = self.sb.branch
        mb = _git(repo, "merge-base", base, head, check=False) or base
        commits = int(_git(repo, "rev-list", "--count", f"{mb}..{head}", check=False) or 0)
        files = [f for f in _git(repo, "diff", "--name-only", f"{mb}..{head}", check=False).splitlines() if f]
        auth = detect_auth(self.env)
        if auth is None:
            raise PrError("没有 GitHub 授权：设置 GITHUB_TOKEN（细粒度令牌），或在本机 `gh auth login`")
        return PrPlan(run_id=self.run_id, repo_path=str(repo), remote=self.remote, owner=owner, repo=name, head=head,
                      base=base, title=title.strip()[:200] or _title(self.home / "runs" / self.run_id), body=body,
                      commits=commits, files=files[:200], auth=auth)  # fmt: skip

    async def open(self, *, title: str, body: str, draft: bool) -> PrRef:
        sha = await self.sb.commit_branch(f"tw: run {self.run_id}")
        if not sha:
            raise PrError("没有可提交的改动")
        plan = await asyncio.to_thread(self._plan, title, body)
        self.plan = plan

        def do() -> dict[str, Any]:
            res = open_pr(plan, env=self.env, draft=draft, push_url=self.push_url, client=self.http_client)
            record_pr(self.home, plan, res)
            return {"url": res.url, "number": res.number, "created": res.created}

        def find() -> dict[str, Any] | None:
            f = self.home / "runs" / self.run_id / "pr.json"
            if f.is_file():
                import json

                d = json.loads(f.read_text(encoding="utf-8"))
                return {"url": d.get("url"), "number": d.get("number"), "created": False}
            return None

        def go() -> Any:
            with SideEffectLog(self.home / "tw.db") as log_:
                return log_.run(side_effect_key(self.run_id, "open_pr"), do, find=find)

        out = await asyncio.to_thread(go)
        r = out.result
        return PrRef(url=str(r.get("url")), number=r.get("number"), repo=plan.full_name, head=plan.head, sha=sha,
                     draft=draft, created=bool(r.get("created")) and not out.reused, reused=out.reused)  # fmt: skip

    async def push(self, n: int) -> str:
        """CI 返工后：提交新改动并推送同一分支（不强推）。幂等键 `<run_id>:push:<n>`。"""
        plan = self.plan
        if plan is None:
            raise PrError("还没开 PR")
        sha = await self.sb.commit_branch(f"tw: fix CI (round {n})") or ""

        def do() -> dict[str, Any]:
            token = self.env.get("GITHUB_TOKEN", "").strip() or None
            push_branch(plan, token=token if plan.auth == "token" else None, push_url=self.push_url)
            return {"sha": sha}

        def go() -> Any:
            with SideEffectLog(self.home / "tw.db") as log_:
                return log_.run(side_effect_key(self.run_id, "push", n), do)

        await asyncio.to_thread(go)
        return sha

    async def ci(self, sha: str, cfg: CiWatchConfig) -> CiResult:
        plan = self.plan
        if plan is None:
            raise PrError("还没开 PR")
        client = self.ci_client or client_for(self.env)
        return await watch(client, plan.full_name, sha, timeout_s=cfg.timeout_s, poll_s=cfg.poll_s,
                           no_checks_grace_s=cfg.no_checks_grace_s, log_max_chars=cfg.log_max_chars)  # fmt: skip


__all__ = ["CommitsBranch", "GitHubPublisher", "PrRef", "Publisher", "pr_action"]
