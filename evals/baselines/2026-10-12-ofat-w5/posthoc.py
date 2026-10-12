"""W5-09/10/11 OFAT 事后分析（一次性）。

输入 summary.json + run.log + ledger.sqlite + 可用的 result.json / 轨迹，输出 analysis.json、runs.csv。
用法：uv run python evals/baselines/2026-10-12-ofat-w5/posthoc.py <解压后的 bundle 目录> [输出目录]
账本按 run.log 里每个配置的开始时间切窗口归属（配置是串行跑的）。"""

import collections
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))
from triwitness.eval import ablation as A


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


B = sys.argv[1]  # 解压后的 bundle 目录（含 ledger.sqlite 与 ofat/）
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
OFAT = B + "/ofat"
R = OFAT + "/results"
BJ = timezone(timedelta(hours=8))
summ = _json(OFAT + "/summary.json")
results = summ["results"]
CFGS = list(results)
with open(OFAT + "/run.log", encoding="utf-8") as fh:
    log = fh.read().splitlines()
# windows: first full-run start per config (skip smoke block before line 75)
starts = {}
for i, ln in enumerate(log):
    m = re.match(r"==> (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (\S+)$", ln)
    if m and i >= 74:
        t = datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=BJ)
        starts.setdefault(m[2], t)
smoke_end = starts[CFGS[0]]
order = sorted(starts.items(), key=lambda x: x[1])


def cfg_of(ts):
    t = datetime.fromisoformat(ts)
    if t < smoke_end:
        return CFGS[0]  # 冒烟那 1 题被全量基线“跳过已完成”沿用，算基线
    c = None
    for n, s in order:
        if t >= s:
            c = n
    return c


db = sqlite3.connect(B + "/ledger.sqlite")
calls = db.execute(
    "select ts, task_id, input_tokens, cache_hit_tokens, output_tokens, cost_cny, peak from calls"
).fetchall()
L = collections.defaultdict(lambda: dict(calls=0, cost=0.0, inp=0, hit=0, out=0, max_in=0, peak=0))
LT = collections.defaultdict(float)
for ts, task, i, h, o, c, p in calls:
    k = cfg_of(ts)
    d = L[k]
    d["calls"] += 1
    d["cost"] += c
    d["inp"] += i
    d["hit"] += h
    d["out"] += o
    d["max_in"] = max(d["max_in"], i)
    d["peak"] += p
    LT[(k, task)] += c
# report rows from run.log (last occurrence)
rep = {}
fails = {}
ROW_RE = re.compile(
    r"\| (w5-round1\S*) \| llm \| .*?\| (\d+)/(\d+) \| ¥([\d.]+) \| ¥([\d.]+) \| ¥([\d.]+) \| "
    r"([\d.]+) \| ([\d.]+)s \| (\d+) \| (\d+) \| (\d+)% \|"
)
for ln in log:
    m = ROW_RE.match(ln)
    if m:
        rep[m[1]] = dict(
            solved=int(m[2]),
            n=int(m[3]),
            cost=float(m[4]),
            steps=float(m[7]),
            wall=float(m[8]),
            false_success=int(m[9]),
            tamper=int(m[10]),
            cache=int(m[11]) / 100,
        )
    m = re.match(r"\| (w5-round1\S*) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", ln)
    if m:
        fails[m[1]] = dict(
            zip(
                ["resolved", "infra_error", "patch_not_applied", "false_success", "agent_error", "unresolved"],
                map(int, m.groups()[1:]),
                strict=True,
            )
        )
# trajectories / result.json
T = collections.defaultdict(
    lambda: dict(
        traj=0,
        result=0,
        clear=0,
        compact=0,
        loop_warn=0,
        budget_exceeded=[],
        max_ctx=0,
        tools=collections.Counter(),
        steps=[],
        wall=[],
    )
)
runs = []
for c in CFGS:
    for task in sorted(results[c]):
        t = task.split("#")[0]
        d = f"{R}/{c}/{c}/{t}/1"
        row = dict(config=c, task=t, resolved=results[c][task], ledger_cny=round(LT[(c, t)], 5))
        if os.path.exists(d + "/result.json"):
            r = _json(d + "/result.json")
            T[c]["result"] += 1
            row.update(
                steps=r["steps"],
                wall_s=r["wall_s"],
                agent_status=r["agent_status"],
                claimed=r["agent_claimed_success"],
                false_success=r["false_success"],
                result_cny=r["cost_cny"],
                risk=r.get("risk_level"),
            )
            T[c]["steps"].append(r["steps"])
            T[c]["wall"].append(r["wall_s"])
        if os.path.exists(d + "/trajectory.jsonl"):
            T[c]["traj"] += 1
            with open(d + "/trajectory.jsonl", encoding="utf-8") as fh:
                events = [json.loads(x) for x in fh]
            for e in events:
                k = e["kind"]
                p = e["payload"]
                if k == "context_event":
                    T[c][p["action"]] += 1
                elif k == "loop_warning":
                    T[c]["loop_warn"] += 1
                elif k == "error" and p.get("type") == "BudgetExceeded":
                    T[c]["budget_exceeded"].append(t + ": " + p["message"])
                elif k == "model_call":
                    T[c]["max_ctx"] = max(T[c]["max_ctx"], p["usage"]["input_tokens"])
                elif k == "tool_call":
                    T[c]["tools"][p.get("tool") or p.get("name") or "?"] += 1
        runs.append(row)
# stats
rows = A.compare(results, CFGS[0], costs={c: rep[c]["cost"] for c in CFGS})
base_cost = [LT[(CFGS[0], t.split("#")[0])] for t in sorted(results[CFGS[0]])]
out = {
    "bundle": os.path.basename(os.path.normpath(B)),
    "git_sha": _json(OFAT + "/env.json")["git_sha"],
    "env": _json(OFAT + "/env.json"),
    "repeats": 1,
    "n_tasks": 15,
    "mde_paired_20pct_discordant": A.mde_paired(15),
    "mde_independent": A.mde_independent(15, p=0.8),
    "ledger_total_cny": round(sum(d["cost"] for d in L.values()), 5),
    "ledger_calls": len(calls),
    "ledger_window_utc": [calls[0][0], calls[-1][0]],
    "ledger_by_config": {
        k: {**v, "cost": round(v["cost"], 5), "cache_hit": round(v["hit"] / v["inp"], 4) if v["inp"] else None}
        for k, v in L.items()
    },
    "configs": {},
}
for r in rows:
    c = r.config
    tt = T[c]
    lc = L[c]
    pc = [LT[(c, t.split("#")[0])] for t in sorted(results[c])]
    dci = (
        A.bootstrap_ci([a - b for a, b in zip(pc, base_cost, strict=True)], stat=lambda xs: sum(xs) / len(xs))
        if c != CFGS[0]
        else None
    )
    out["configs"][c] = dict(
        solved=r.solved,
        n=r.n,
        rate=r.rate,
        wilson=r.wilson,
        diff=r.diff,
        diff_ci=r.diff_ci,
        mcnemar=(dict(b=r.test.b, c=r.test.c, p=r.test.p_exact) if r.test else None),
        p_holm=r.p_holm,
        verdict=r.verdict(),
        unsolved=sorted(t.split("#")[0] for t, v in results[c].items() if not v),
        report=rep.get(c),
        failures=fails.get(c),
        ledger=dict(
            cost=round(lc["cost"], 4),
            calls=lc["calls"],
            tokens_in=lc["inp"],
            tokens_out=lc["out"],
            cache_hit=round(lc["hit"] / lc["inp"], 4),
            max_input_per_call=lc["max_in"],
            peak_calls=lc["peak"],
        ),
        paired_cost_diff_per_task=dict(mean=round((sum(pc) - sum(base_cost)) / 15, 5), ci=dci) if dci else None,
        coverage=dict(result_json=tt["result"], trajectories=tt["traj"]),
        context_events_in_available_traj=dict(clear=tt["clear"], compact=tt["compact"]),
        loop_warnings=tt["loop_warn"],
        budget_exceeded=tt["budget_exceeded"],
        max_input_in_traj=tt["max_ctx"],
        tool_calls_top=dict(tt["tools"].most_common(12)),
    )
with open(os.path.join(OUT, "analysis.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1, default=str)

keys = [
    "config",
    "task",
    "resolved",
    "ledger_cny",
    "result_cny",
    "steps",
    "wall_s",
    "agent_status",
    "claimed",
    "false_success",
    "risk",
]
with open(os.path.join(OUT, "runs.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, keys)
    w.writeheader()
    for row in runs:
        w.writerow({k: row.get(k, "") for k in keys})
for c, v in out["configs"].items():
    print(c, f"{v['solved']}/{v['n']}", v["verdict"], f"¥{v['ledger']['cost']}", v["paired_cost_diff_per_task"])
