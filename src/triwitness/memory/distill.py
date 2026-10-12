"""蒸馏（spec 013 §5.2，W6-05）：从一次已验证通过的 run 里提炼候选（事实 / 经验片段 / Skill）。

- 只接受 summary.json 里 verdict == "pass" 的 run（没被独立验证过的轨迹不当经验）。
- reflector 角色（deepseek-flash 非思考）读一份压缩转录（工具调用摘要 + 结束报告 + 补丁统计），只输出 JSON。
- 每个候选都带来源 `tw://run/<run_id>` 并过静态检查（密钥 / 绕过 / 外传 / 任务答案 / 长度）；
  通过的进候选区（事实与经验进 candidates.jsonl，Skill 进 pool 的 candidate 版本），
  没通过的也记下来（status=rejected + 原因）。
- 蒸馏**不直接改记忆**：事实 / 经验要 `tw memory accept`，Skill 要过 A/B 门禁才合入。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triwitness.core.errors import TriWitnessError
from triwitness.harness.context import head_tail, wrap_untrusted
from triwitness.llm.types import LLMRequest, Message
from triwitness.memory.checks import check_candidate
from triwitness.memory.format import entry_id
from triwitness.memory.skills import Skill, SkillError, SkillPool
from triwitness.memory.store import FACT_KINDS, MemoryStore, today
from triwitness.prompts import load_prompt

TRANSCRIPT_MAX_CHARS = 24_000
MAX_FACTS = 5
MAX_SKILLS = 1


class DistillError(TriWitnessError):
    pass


@dataclass
class RunDigest:
    run_id: str
    repo: str
    issue: str
    verdict: str
    transcript: str
    patch: str = ""
    tests: list[str] = field(default_factory=list)

    @property
    def source(self) -> str:
        return f"tw://run/{self.run_id}"


def _events(run_dir: Path) -> list[dict[str, Any]]:
    p = run_dir / "trajectory.jsonl"
    if not p.is_file():
        raise DistillError(f"{run_dir} 没有 trajectory.jsonl")
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _patch_stat(patch: str) -> str:
    files = re.findall(r"^\+\+\+ b/(.+)$", patch, re.M)
    add = sum(1 for ln in patch.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    rem = sum(1 for ln in patch.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    return f"改动文件：{', '.join(files) or '无'}（+{add} / -{rem}）"


def load_run(run_dir: Path, *, require_pass: bool = True) -> RunDigest:
    """读 run 目录，生成给 reflector 的压缩转录（只有工具调用摘要，不含完整输出与补丁正文）。"""
    summary = (
        json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        if (run_dir / "summary.json").is_file()
        else {}
    )
    verdict = str(summary.get("verdict") or "")
    if require_pass and verdict != "pass":
        raise DistillError(f"{run_dir.name} 的验证结论是 {verdict or '无'}，只蒸馏验证通过的 run")
    events = _events(run_dir)
    run_id = next((e.get("run_id") for e in events if e.get("run_id")), run_dir.name)
    issue, lines, finish = "", [], ""
    for e in events:
        k, p = e.get("kind"), e.get("payload") or {}
        if k == "task_started":
            issue = str(p.get("issue_title") or p.get("display") or "")
        elif k == "tool_call":
            mark = "✓" if p.get("ok") else "✗"
            out = " ".join(str(p.get("output_preview") or "").split())[:200]
            lines.append(f"{mark} [{e.get('role') or p.get('role_hint') or '?'}] {p.get('display', '')[:200]}"
                         + (f"\n    → {out}" if out and not p.get("ok") else ""))  # fmt: skip
        elif k == "verification":
            lines.append(f"[verifier] {p.get('display', '')}")
        elif k == "task_finished":
            fr = p.get("finish_report") or {}
            finish = str(fr.get("summary") or p.get("display") or "")
    patch = (
        (run_dir / "patch.diff").read_text(encoding="utf-8", errors="replace")
        if (run_dir / "patch.diff").is_file()
        else ""
    )
    tests: list[str] = []
    ev = run_dir / "evidence.json"
    if ev.is_file():
        try:
            d = json.loads(ev.read_text(encoding="utf-8"))
            if d.get("repro_path"):
                tests.append(str(d["repro_path"]))
        except (json.JSONDecodeError, AttributeError):
            pass
    body = "\n".join([f"# 任务\n{issue}", "", "# 工具调用（按时间）", *lines, "", f"# 结束报告\n{finish}",
                      "", f"# 补丁\n{_patch_stat(patch)}"])  # fmt: skip
    return RunDigest(run_id=str(run_id), repo=str(summary.get("repo") or ""), issue=issue, verdict=verdict,
                     transcript=head_tail(body, TRANSCRIPT_MAX_CHARS)[0], patch=patch, tests=tests)  # fmt: skip


def parse_reflection(text: str) -> dict[str, Any]:
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.S)
    if m:
        s = m.group(1)
    else:
        a, b = s.find("{"), s.rfind("}")
        if a < 0 or b < a:
            raise DistillError("reflector 没有输出 JSON")
        s = s[a : b + 1]
    try:
        d = json.loads(s)
    except json.JSONDecodeError as e:
        raise DistillError(f"reflector 输出不是合法 JSON：{e}") from e
    if not isinstance(d, dict):
        raise DistillError("reflector 输出不是 JSON 对象")
    return d


@dataclass
class DistillResult:
    run_id: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    cost_cny: float = 0.0

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for it in self.candidates:
            k = f"{it['type']}:{it['status']}"
            c[k] = c.get(k, 0) + 1
        return c


def build_candidates(
    d: dict[str, Any], dg: RunDigest, store: MemoryStore, *, added: str | None = None
) -> list[dict[str, Any]]:
    """把 reflector 的输出变成候选；逐个静态检查。Skill 候选通过检查后写进 pool（candidate 版本）。"""
    added = added or today()
    out: list[dict[str, Any]] = []
    base = {"source": dg.source, "added": added}

    def rec(typ: str, payload: dict[str, Any], text: str, reasons: list[str]) -> dict[str, Any]:
        it = {"id": entry_id(f"{typ}:{text}", "c"), "type": typ, **base, **payload,
              "status": "rejected" if reasons else "pending", **({"reasons": reasons} if reasons else {})}  # fmt: skip
        out.append(it)
        return it

    for f in (d.get("facts") or [])[:MAX_FACTS]:
        if not isinstance(f, dict) or not str(f.get("text") or "").strip():
            continue
        text = " ".join(str(f["text"]).split())
        kind = str(f.get("kind") or "other")
        kind = kind if kind in FACT_KINDS else "other"
        res = check_candidate(text, "fact", patch=dg.patch, tests=dg.tests)
        rec("fact", {"kind": kind, "text": text}, text, res.reasons())
    ep = d.get("episode")
    if isinstance(ep, dict) and ep.get("root_cause") and ep.get("worked"):
        from triwitness.memory.store import Episode

        e = Episode(*(str(ep.get(k) or "").strip() for k in ("problem_type", "root_cause", "worked", "failed")))
        e.problem_type = e.problem_type or "其他"
        text = e.text()
        res = check_candidate(text, "episode", patch=dg.patch, tests=dg.tests)
        fields = {"problem_type": e.problem_type, "root_cause": e.root_cause, "worked": e.worked, "failed": e.failed}
        rec("episode", {"episode": fields, "text": text, "task": dg.run_id}, text, res.reasons())
    pool = SkillPool(store.root)
    for s in (d.get("skills") or [])[:MAX_SKILLS]:
        if not isinstance(s, dict):
            continue
        name, desc, body = (str(s.get(k) or "").strip() for k in ("name", "description", "body"))
        scope = "global" if s.get("scope") == "global" else "repo"
        res = check_candidate(body, "skill", name=name, description=desc, patch=dg.patch, tests=dg.tests)
        reasons = res.reasons()
        payload: dict[str, Any] = {"name": name, "description": desc, "scope": scope}
        if not reasons:
            try:
                sk = pool.add_candidate(Skill(name, desc, body, {"tw-scope": scope}), source=dg.source, added=added)
                payload["version"] = sk.version
            except SkillError as e:
                reasons = [str(e)]
        if reasons:
            payload["body"] = body[:2000]
        rec("skill", payload, f"{name}:{desc}", reasons)
    return out


async def distill_run(run_dir: Path, router: Any, store: MemoryStore, *, guard: Any = None, category: str = "memory",
                      added: str | None = None) -> DistillResult:  # fmt: skip
    """一次 reflector 调用（经路由 → 客户端 → 全局账本）；结果写进候选区（不直接进记忆）。"""
    dg = load_run(run_dir)
    prompt = load_prompt("reflector")
    req = LLMRequest(role="reflector", thinking=False, max_output_tokens=8192, temperature=0.0, messages=[
        Message(role="system", content=prompt.text),
        Message(role="user", content=wrap_untrusted("trajectory", dg.transcript)),
    ])  # fmt: skip
    resp = await router.complete(req, guard=guard, category=category, task_id=dg.run_id)
    d = parse_reflection(resp.message.content or "")
    items = build_candidates(d, dg, store, added=added)
    store.add_candidates(items)
    return DistillResult(run_id=dg.run_id, candidates=items, cost_cny=float(resp.cost_cny or 0.0))


def accept_candidate(store: MemoryStore, cid: str) -> str:
    """接受一个待定的事实 / 经验候选：写进记忆（再过一次检查），候选标 accepted。Skill 候选走门禁，不在这里。"""
    from triwitness.memory.store import Episode

    it = next((c for c in store.candidates() if c.get("id") == cid), None)
    if it is None:
        raise DistillError(f"没有候选 {cid}")
    if it.get("status") != "pending":
        raise DistillError(f"候选 {cid} 的状态是 {it.get('status')}，只能接受 pending")
    if it["type"] == "fact":
        e = store.add_fact(it["text"], kind=it.get("kind", "other"), source=it["source"], added=it.get("added"))
    elif it["type"] == "episode":
        e = store.add_episode(Episode(**it["episode"]), source=it["source"], task=it.get("task", ""),
                              added=it.get("added"))  # fmt: skip
    else:
        raise DistillError("Skill 候选要过 A/B 门禁（tw memory gate），不能直接接受")
    store.set_candidate_status(cid, "accepted", note=e.id)
    return e.id


__all__ = [
    "DistillError",
    "DistillResult",
    "RunDigest",
    "accept_candidate",
    "build_candidates",
    "distill_run",
    "load_run",
    "parse_reflection",
]
