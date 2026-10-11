"""打包后核心的冒烟测试（¥0）：`tw --version`、`tw permissions …`、`tw budget --json`、
`tw run --demo --jsonl` 往返（默认模型自动审批 + 询问模式批准）。

用法：python packaging/core/smoke_core.py <tw 可执行文件路径>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def run_demo(tw: str, tmp: Path, extra: list[str]) -> dict:  # type: ignore[type-arg]
    home = tmp / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "TW_DEMO_DELAY_S": "0",
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "TW_HANG_DUMP_S": "60"}  # fmt: skip
    env.pop("TW_HOME", None)
    repo = tmp / f"verses{len(extra)}"
    errf = (tmp / f"stderr{len(extra)}.log").open("w+", encoding="utf-8")
    p = subprocess.Popen(
        [tw, "run", "--repo", str(repo), "--demo", "--jsonl", *extra],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=errf,  # 写文件而不是管道：不读的 stderr 管道写满会把子进程卡死
        env=env,
        text=True,
        encoding="utf-8",
    )
    assert p.stdin and p.stdout
    watchdog = threading.Timer(240, p.kill)  # 卡住就杀掉，让 CI 失败而不是挂到超时
    watchdog.start()
    seen = []
    for raw in p.stdout:
        obj = json.loads(raw)
        seen.append(obj)
        if obj.get("kind") == "approval_requested":
            rid = obj["payload"]["request_id"]
            msg = {"cmd": "approve", "request_id": rid, "decision": "allow", "scope": "once"}
            p.stdin.write(json.dumps(msg) + "\n")
            p.stdin.flush()
        if obj.get("kind") in ("approval_requested", "state_changed", "verdict") or obj.get("bridge"):
            brief = json.dumps(obj.get("payload", {}), ensure_ascii=False)[:120]
            print("  ·", obj.get("bridge") or obj.get("kind"), brief, flush=True)
        if obj.get("bridge") in ("result", "error"):
            break
    p.stdin.close()
    code = p.wait(timeout=120)
    watchdog.cancel()
    errf.seek(0)
    err = errf.read()[-4000:]
    errf.close()
    if not seen or seen[-1].get("bridge") != "result":
        print(err, file=sys.stderr)
    assert code == 0, err
    res = seen[-1]
    assert res.get("bridge") == "result" and res.get("status") == "done" and res.get("verdict") == "pass", (res, err)
    return {"events": len(seen), "verdict": res["verdict"], "risk": res.get("risk")}


def main() -> None:
    tw = sys.argv[1]
    t0 = time.perf_counter()
    v = subprocess.run([tw, "--version"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert v.returncode == 0, v.stderr
    print(f"tw --version → {v.stdout.strip()}  ({time.perf_counter() - t0:.2f}s)")
    r = subprocess.run([tw, "permissions", "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    b = subprocess.run([tw, "budget", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert b.returncode == 0, b.stderr
    json.loads(b.stdout)
    print("tw budget --json → ok")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        print("demo (auto_review):", run_demo(tw, tmp, []))
        print("demo (ask + approve):", run_demo(tw, tmp, ["--permission-mode", "ask", "--backend", "none"]))
    print("SMOKE OK")


if __name__ == "__main__":
    main()
