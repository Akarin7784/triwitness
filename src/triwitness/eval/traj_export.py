"""轨迹导出（W8-03 / architecture §6.4）。

四种格式（均从已有 run 目录的 trajectory.jsonl + artifacts + 可选 result.json 生成，不调模型、不拉镜像）：

1. ``openai`` —— OpenAI Chat Completions 风格 messages（SFT）
2. ``rlvr`` —— 逐步轨迹 + 0/1 奖励（隐藏测试 / result.json.reward）
3. ``harbor`` —— Harbor 风格单 trial 目录（result.json + verifier/reward.txt + agent/）
4. ``html`` —— 单文件 HTML 回放（事件时间线，可附博客）

CLI：``tw traj export <run_dir> --format … --out …``
"""

from __future__ import annotations

import html as html_mod
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FormatName = Literal["openai", "rlvr", "harbor", "html", "all"]
FORMATS: tuple[str, ...] = ("openai", "rlvr", "harbor", "html")


@dataclass(frozen=True)
class ExportResult:
    format: str
    path: Path
    bytes: int


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _events(run_dir: Path) -> list[dict[str, Any]]:
    traj = run_dir / "trajectory.jsonl"
    if not traj.is_file():
        raise FileNotFoundError(f"没有 trajectory.jsonl：{run_dir}")
    out: list[dict[str, Any]] = []
    for line in traj.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _result(run_dir: Path) -> dict[str, Any] | None:
    p = run_dir / "result.json"
    return _load_json(p) if p.is_file() else None


def _reward(run_dir: Path, result: dict[str, Any] | None) -> float:
    if result is not None:
        if "reward" in result and result["reward"] is not None:
            return float(result["reward"])
        if "resolved" in result:
            return 1.0 if result["resolved"] else 0.0
    # Harbor 风格
    rt = run_dir / "verifier" / "reward.txt"
    if rt.is_file():
        try:
            return float(rt.read_text(encoding="utf-8").strip().split()[0])
        except (ValueError, IndexError):
            pass
    return 0.0


def _read_ref(run_dir: Path, ref: str | None) -> Any | None:
    if not ref:
        return None
    p = run_dir / ref
    if not p.is_file():
        return None
    if p.suffix == ".json":
        return _load_json(p)
    return p.read_text(encoding="utf-8", errors="replace")


def _openai_message(msg: dict[str, Any]) -> dict[str, Any]:
    """规范化为常见 OpenAI chat message（去掉 reasoning_content 等扩展，保留 tool_calls）。"""
    role = msg.get("role") or "assistant"
    out: dict[str, Any] = {"role": role}
    content = msg.get("content")
    if content is None:
        content = ""
    out["content"] = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if role == "assistant" and msg.get("tool_calls"):
        tcs = []
        for tc in msg["tool_calls"]:
            # 已是 OpenAI 风格或内部 ToolCallSpec
            if "function" in tc:
                tcs.append(tc)
            else:
                args = tc.get("arguments", {})
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                tcs.append(
                    {
                        "id": tc.get("id") or "call_0",
                        "type": "function",
                        "function": {"name": tc.get("name") or "", "arguments": args},
                    }
                )
        out["tool_calls"] = tcs
        if not out["content"]:
            out["content"] = None  # type: ignore[assignment]
    if role == "tool":
        if msg.get("tool_call_id"):
            out["tool_call_id"] = msg["tool_call_id"]
        if msg.get("name"):
            out["name"] = msg["name"]
    return out


def export_openai(run_dir: Path) -> dict[str, Any]:
    """取最后一次 model_call 的完整 messages + 该次 assistant 回复，作为一条 SFT 样本。"""
    events = _events(run_dir)
    result = _result(run_dir)
    last_req: dict[str, Any] | None = None
    last_resp: dict[str, Any] | None = None
    meta: dict[str, Any] = {"task_id": None, "run_id": None, "model": None}
    for ev in events:
        meta["task_id"] = meta["task_id"] or ev.get("task_id")
        meta["run_id"] = meta["run_id"] or ev.get("run_id")
        if ev.get("kind") != "model_call":
            continue
        p = ev.get("payload") or {}
        meta["model"] = p.get("served_model") or p.get("model") or meta["model"]
        req = _read_ref(run_dir, p.get("request_ref"))
        resp = _read_ref(run_dir, p.get("response_ref"))
        if isinstance(req, dict) and "messages" in req:
            last_req, last_resp = req, resp if isinstance(resp, dict) else None
    if last_req is None:
        raise ValueError(f"轨迹里没有带 request_ref 的 model_call：{run_dir}")
    messages = [_openai_message(m) for m in last_req["messages"]]
    if last_resp and isinstance(last_resp.get("message"), dict):
        messages.append(_openai_message(last_resp["message"]))
    return {
        "format": "openai-messages/v1",
        "task_id": meta["task_id"],
        "run_id": meta["run_id"],
        "model": meta["model"],
        "reward": _reward(run_dir, result),
        "messages": messages,
    }


def export_rlvr(run_dir: Path) -> dict[str, Any]:
    """逐步轨迹 + 标量奖励（RLVR / 拒绝采样）。"""
    events = _events(run_dir)
    result = _result(run_dir)
    steps: list[dict[str, Any]] = []
    task_id = run_id = None
    for ev in events:
        task_id = task_id or ev.get("task_id")
        run_id = run_id or ev.get("run_id")
        kind = ev.get("kind")
        p = ev.get("payload") or {}
        if kind == "model_call":
            steps.append(
                {
                    "seq": ev.get("seq"),
                    "ts": ev.get("ts"),
                    "type": "model_call",
                    "role": ev.get("role"),
                    "model": p.get("served_model") or p.get("model"),
                    "display": p.get("display"),
                    "usage": p.get("usage"),
                    "cost_cny": p.get("cost_cny"),
                    "finish_reason": p.get("finish_reason"),
                    "request_ref": p.get("request_ref"),
                    "response_ref": p.get("response_ref"),
                }
            )
        elif kind == "tool_call":
            steps.append(
                {
                    "seq": ev.get("seq"),
                    "ts": ev.get("ts"),
                    "type": "tool_call",
                    "role": ev.get("role"),
                    "tool": p.get("tool"),
                    "ok": p.get("ok"),
                    "display": p.get("display"),
                    "exit_code": p.get("exit_code"),
                    "message_ref": p.get("message_ref"),
                    "output_ref": p.get("output_ref"),
                }
            )
        elif kind == "task_finished":
            steps.append(
                {
                    "seq": ev.get("seq"),
                    "ts": ev.get("ts"),
                    "type": "task_finished",
                    "status": p.get("status"),
                }
            )
    reward = _reward(run_dir, result)
    return {
        "format": "trajectory-reward/v1",
        "task_id": task_id,
        "run_id": run_id,
        "reward": reward,
        "resolved": bool(result.get("resolved")) if result else reward >= 1.0,
        "cost_cny": (result or {}).get("cost_cny"),
        "steps": steps,
        "result": {k: result[k] for k in ("agent_status", "false_success", "steps", "wall_s") if result and k in result}
        if result
        else {},
    }


def export_harbor(run_dir: Path, out_dir: Path) -> Path:
    """写出 Harbor 风格 trial 目录：result.json、verifier/reward.txt、agent/trajectory.jsonl。"""
    events = _events(run_dir)
    result = _result(run_dir) or {}
    reward = _reward(run_dir, result if result else None)
    task_id = result.get("task_id") or (events[0].get("task_id") if events else run_dir.name)
    run_id = result.get("trajectory_id") or (events[0].get("run_id") if events else run_dir.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verifier").mkdir(exist_ok=True)
    (out_dir / "agent").mkdir(exist_ok=True)
    (out_dir / "verifier" / "reward.txt").write_text(f"{reward}\n", encoding="utf-8")
    # 复制轨迹（已脱敏）
    src_traj = run_dir / "trajectory.jsonl"
    (out_dir / "agent" / "trajectory.jsonl").write_text(src_traj.read_text(encoding="utf-8"), encoding="utf-8")
    trial = {
        "id": str(run_id),
        "task_name": str(task_id),
        "trial_name": run_dir.name,
        "source_run_dir": str(run_dir.resolve()),
        "verifier_result": {"rewards": {"reward": reward}},
        "agent_result": {
            "n_input_tokens": result.get("tokens_in"),
            "n_cache_tokens": result.get("tokens_cached"),
            "n_output_tokens": result.get("tokens_out"),
            "cost_cny": result.get("cost_cny"),
            "steps": result.get("steps"),
            "wall_s": result.get("wall_s"),
            "agent_status": result.get("agent_status"),
        },
        "exception_info": result.get("error"),
        "triwitness_result": result or None,
    }
    (out_dir / "result.json").write_text(json.dumps(trial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_dir


def export_html(run_dir: Path) -> str:
    """单文件 HTML 回放（无外部依赖）。"""
    events = _events(run_dir)
    result = _result(run_dir)
    reward = _reward(run_dir, result)
    task_id = (result or {}).get("task_id") or (events[0].get("task_id") if events else "?")
    run_id = events[0].get("run_id") if events else "?"
    rows = []
    for ev in events:
        p = ev.get("payload") or {}
        kind = ev.get("kind") or ""
        display = p.get("display") or ""
        role = ev.get("role") or p.get("role_hint") or ""
        extra = ""
        if kind == "model_call":
            extra = f"{p.get('model', '')} · ¥{p.get('cost_cny', 0):.4f}"
        elif kind == "tool_call":
            extra = f"{p.get('tool', '')} · {'ok' if p.get('ok') else 'fail'}"
        elif kind == "task_finished":
            extra = str(p.get("status") or "")
        rows.append(
            "<tr>"
            f"<td class='seq'>{ev.get('seq', '')}</td>"
            f"<td class='ts'>{html_mod.escape(str(ev.get('ts') or ''))}</td>"
            f"<td class='kind'>{html_mod.escape(kind)}</td>"
            f"<td class='role'>{html_mod.escape(str(role))}</td>"
            f"<td class='disp'>{html_mod.escape(str(display))}</td>"
            f"<td class='extra'>{html_mod.escape(extra)}</td>"
            "</tr>"
        )
    resolved = "resolved" if reward >= 1.0 else "failed"
    title = f"TriWitness replay · {task_id} · {resolved}"
    rid_esc = html_mod.escape(str(run_id))
    src_esc = html_mod.escape(str(run_dir))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html_mod.escape(title)}</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; background: #fafafa; }}
h1 {{ font-size: 1.25rem; margin: 0 0 .5rem; }}
.meta {{ color: #555; font-size: .9rem; margin-bottom: 1rem; }}
.badge {{ display: inline-block; padding: .15rem .5rem; border-radius: 999px; font-size: .8rem;
  background: {"#d1fae5" if reward >= 1.0 else "#fee2e2"}; color: {"#065f46" if reward >= 1.0 else "#991b1b"}; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; font-size: .85rem; }}
th, td {{ border-bottom: 1px solid #eee; padding: .4rem .5rem; text-align: left; vertical-align: top; }}
th {{ background: #f3f4f6; position: sticky; top: 0; }}
.seq {{ width: 3rem; color: #888; }}
.kind {{ font-family: ui-monospace, monospace; }}
.disp {{ max-width: 36rem; }}
footer {{ margin-top: 1.5rem; color: #888; font-size: .75rem; }}
</style>
</head>
<body>
<h1>{html_mod.escape(str(task_id))} <span class="badge">{resolved} · reward={reward}</span></h1>
<p class="meta">run_id={rid_esc} · events={len(events)} · source={src_esc}</p>
<table>
<thead><tr><th>#</th><th>时间 (UTC)</th><th>kind</th><th>role</th><th>display</th><th>细节</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<footer>TriWitness traj export · format html/v1 · 脱敏轨迹回放</footer>
</body>
</html>
"""


def export_run(
    run_dir: Path,
    out: Path,
    *,
    formats: list[str] | None = None,
) -> list[ExportResult]:
    """导出到 ``out`` 目录。``formats`` 默认四种全出。"""
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"不是目录：{run_dir}")
    wanted = list(formats or FORMATS)
    if "all" in wanted:
        wanted = list(FORMATS)
    for f in wanted:
        if f not in FORMATS:
            raise ValueError(f"未知格式 {f!r}；可选：{', '.join(FORMATS)}、all")
    out.mkdir(parents=True, exist_ok=True)
    results: list[ExportResult] = []
    if "openai" in wanted:
        data = export_openai(run_dir)
        path = out / "openai-messages.json"
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        results.append(ExportResult("openai", path, len(text.encode())))
    if "rlvr" in wanted:
        data = export_rlvr(run_dir)
        path = out / "trajectory-reward.json"
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        results.append(ExportResult("rlvr", path, len(text.encode())))
    if "harbor" in wanted:
        hdir = out / "harbor-trial"
        export_harbor(run_dir, hdir)
        size = sum(p.stat().st_size for p in hdir.rglob("*") if p.is_file())
        results.append(ExportResult("harbor", hdir, size))
    if "html" in wanted:
        text = export_html(run_dir)
        path = out / "replay.html"
        path.write_text(text, encoding="utf-8")
        results.append(ExportResult("html", path, len(text.encode())))
    return results


__all__ = [
    "FORMATS",
    "ExportResult",
    "export_harbor",
    "export_html",
    "export_openai",
    "export_rlvr",
    "export_run",
]
