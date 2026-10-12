"""参数级策略引擎（spec 014 §6，W7-07）：确定性规则优先，分类器兜底，**任何不确定都拒绝**（fail closed）。

输入是一次工具调用 `ToolCall(tool, args, origin)`（args 是工具参数的 JSON；origin = user / agent / delegated / mcp）。
判定顺序：
  1. deny 规则：任何一条命中 → deny；
  2. ask 规则：命中 → ask（交互时交给人，非交互 / 评测时按 deny）；
  3. allow 规则：命中 → allow；
  4. 都没命中：该工具配置了 `classifier: true` 且有分类器 → 分类器 allow / deny；uncertain、出错、超时 → deny；
     否则 → deny（default 永远是 deny，配置里写别的也不认）。
规则的 `match` 是 “参数路径 → 匹配器” 的映射，全部成立才算命中；
**引用的参数不存在 = 不命中**（allow 规则因此不会误放行）。
匹配器：equals / in / not_in / regex / not_regex / glob / path_under / domain_in / max / min / max_items / contains。
评估中任何异常 → deny（reason=engine_error）。声称的“用户已批准”只是参数文本，不会让结果变宽（审批走 HITL 通道）。
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import posixpath
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Effect = Literal["allow", "ask", "deny"]
Origin = Literal["user", "agent", "delegated", "mcp"]
ClassifierOutcome = Literal["allow", "deny", "uncertain"]
Classifier = Callable[["ToolCall"], Awaitable[tuple[ClassifierOutcome, str]]]
_MISSING = object()


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict[str, Any]
    origin: Origin = "agent"

    def key(self) -> str:
        return json.dumps({"t": self.tool, "a": self.args, "o": self.origin}, sort_keys=True, ensure_ascii=False)


@dataclass
class Decision:
    effect: Effect
    reason: str
    rule: str = ""
    by: Literal["rule", "classifier", "default", "error"] = "rule"

    @property
    def allowed(self) -> bool:
        return self.effect == "allow"


@dataclass
class Rule:
    id: str
    tool: str
    effect: Effect
    match: dict[str, dict[str, Any]] = field(default_factory=dict)
    origin: list[str] = field(default_factory=list)
    reason: str = ""

    def applies(self, call: ToolCall) -> bool:
        if not fnmatch.fnmatchcase(call.tool, self.tool):
            return False
        if self.origin and call.origin not in self.origin:
            return False
        return all(_check(get_path(call.args, path), m) for path, m in self.match.items())


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur


def _norm_path(p: str) -> str:
    return posixpath.normpath(p.replace("\\", "/"))


def _host(v: str) -> str:
    s = v.split("://", 1)[-1].split("/", 1)[0].split("@")[-1]
    return s.rsplit(":", 1)[0].strip("[]").lower().rstrip(".") if s.count(":") <= 1 else s.strip("[]").lower()


def _check(value: Any, m: dict[str, Any]) -> bool:
    """单个匹配器。值缺失一律不成立（除了 `absent: true`）。"""
    if "absent" in m:
        return (value is _MISSING) == bool(m["absent"])
    if value is _MISSING:
        return False
    for op, arg in m.items():
        if op == "equals":
            ok = value == arg
        elif op == "in":
            ok = value in arg
        elif op == "not_in":
            ok = value not in arg
        elif op == "regex":
            ok = isinstance(value, str) and re.search(arg, value) is not None
        elif op == "not_regex":
            ok = isinstance(value, str) and re.search(arg, value) is None
        elif op == "glob":
            ok = isinstance(value, str) and fnmatch.fnmatchcase(_norm_path(value), arg)
        elif op == "path_under":
            ok = isinstance(value, str) and not value.startswith("~") and any(
                (n := _norm_path(value if value.startswith("/") else posixpath.join(root, value)))
                == _norm_path(root) or n.startswith(_norm_path(root).rstrip("/") + "/")
                for root in (arg if isinstance(arg, list) else [arg]))  # fmt: skip
        elif op == "domain_in":
            ok = isinstance(value, str) and any(
                (h := _host(value)) == d or (d.startswith("*.") and h.endswith(d[1:])) for d in arg
            )
        elif op == "max":
            ok = isinstance(value, int | float) and not isinstance(value, bool) and value <= arg
        elif op == "min":
            ok = isinstance(value, int | float) and not isinstance(value, bool) and value >= arg
        elif op == "max_items":
            ok = isinstance(value, list) and len(value) <= arg
        elif op == "contains":
            ok = isinstance(value, str | list) and arg in value
        else:
            raise ValueError(f"未知匹配器 {op}")
        if not ok:
            return False
    return True


@dataclass
class PolicyEngine:
    rules: list[Rule]
    classifier_tools: set[str] = field(default_factory=set)
    classifier: Classifier | None = None
    classifier_timeout_s: float = 20.0
    cache: dict[str, tuple[ClassifierOutcome, str]] = field(default_factory=dict)
    cache_path: Path | None = None

    @classmethod
    def from_yaml(
        cls, path: Path, classifier: Classifier | None = None, cache_path: Path | None = None
    ) -> PolicyEngine:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.from_dict(data, classifier=classifier, cache_path=cache_path)

    @classmethod
    def from_dict(cls, data: dict[str, Any], classifier: Classifier | None = None,
                  cache_path: Path | None = None) -> PolicyEngine:  # fmt: skip
        rules = []
        for r in data.get("rules") or []:
            eff = r.get("effect")
            if eff not in ("allow", "ask", "deny"):
                raise ValueError(f"规则 {r.get('id')} 的 effect 无效：{eff}")
            rules.append(Rule(id=str(r["id"]), tool=str(r["tool"]), effect=eff, match=dict(r.get("match") or {}),
                              origin=list(r.get("origin") or []), reason=str(r.get("reason") or "")))  # fmt: skip
        eng = cls(rules=rules, classifier_tools=set(data.get("classifier_tools") or []), classifier=classifier,
                  cache_path=cache_path)  # fmt: skip
        if cache_path is not None and cache_path.is_file():
            eng.cache = {k: (v[0], v[1]) for k, v in json.loads(cache_path.read_text(encoding="utf-8")).items()}
        return eng

    def check_rules(self, call: ToolCall) -> Decision | None:
        """只看确定性规则：deny > ask > allow；都没命中返回 None。"""
        for eff in ("deny", "ask", "allow"):
            for r in self.rules:
                if r.effect == eff and r.applies(call):
                    return Decision(eff, r.reason or f"规则 {r.id}", rule=r.id)  # type: ignore[arg-type]
        return None

    async def decide(self, call: ToolCall) -> Decision:
        try:
            d = self.check_rules(call)
            if d is not None:
                return d
            if self.classifier is not None and any(fnmatch.fnmatchcase(call.tool, t) for t in self.classifier_tools):
                return await self._classify(call)
            return Decision("deny", "没有规则放行（默认拒绝）", by="default")
        except Exception as e:
            return Decision("deny", f"策略引擎出错（{type(e).__name__}），按拒绝处理", by="error")

    def decide_sync(self, call: ToolCall) -> Decision:
        """同步版本（不调分类器）：规则没命中就拒绝。"""
        try:
            return self.check_rules(call) or Decision("deny", "没有规则放行（默认拒绝）", by="default")
        except Exception as e:
            return Decision("deny", f"策略引擎出错（{type(e).__name__}），按拒绝处理", by="error")

    async def _classify(self, call: ToolCall) -> Decision:
        k = call.key()
        if k not in self.cache:
            assert self.classifier is not None
            try:
                out, why = await asyncio.wait_for(self.classifier(call), timeout=self.classifier_timeout_s)
            except Exception as e:
                return Decision("deny", f"分类器不可用（{type(e).__name__}），按拒绝处理", by="classifier")
            self.cache[k] = (out, why)
            if self.cache_path is not None:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        out, why = self.cache[k]
        if out == "allow":
            return Decision("allow", f"分类器：{why}", by="classifier")
        return Decision("deny", f"分类器{'拒绝' if out == 'deny' else '没把握'}：{why}", by="classifier")


def reviewer_classifier(reviewer: Any) -> Classifier:
    """把 permissions.reviewer 的审核者（ModelReviewer = deepseek-flash 非思考 / FakeReviewer）包成分类器。"""
    from triwitness.core.events import ApprovalRequestedPayload

    async def run(call: ToolCall) -> tuple[ClassifierOutcome, str]:
        rid = "gw-" + hashlib.sha256(call.key().encode()).hexdigest()[:12]
        req = ApprovalRequestedPayload(request_id=rid, tool=call.tool,
                                       action=json.dumps(call.args, ensure_ascii=False)[:2000],
                                       reason=f"安全网关：规则未覆盖（origin={call.origin}）", rule=None, risk="L2",
                                       backend="docker")  # fmt: skip
        d = await reviewer.review(req)
        return d.decision, d.reason

    return run


def load_default(classifier: Classifier | None = None) -> PolicyEngine:
    from triwitness.config import config_dir

    return PolicyEngine.from_yaml(config_dir() / "policies" / "tool_policy.yaml", classifier=classifier)


__all__ = ["Decision", "PolicyEngine", "Rule", "ToolCall", "get_path", "load_default", "reviewer_classifier"]
