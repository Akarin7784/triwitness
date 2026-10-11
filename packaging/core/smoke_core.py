"""打包后核心的冒烟测试（¥0，不含演示模式）：`tw --version`、`tw permissions …`、`tw budget --json`，
再把核心指向本机 OpenAI 兼容模拟服务（packaging/mock_llm.py，TW_LLM_BASE_URL_OVERRIDE），走真实的
DeepSeek 适配器 → SSE 流式 → 对话轮 → Executor 全链路：

1. 「你好」（未选仓库）→ 直接回复：result.kind=chat，没有 task_started / tool_call / 补丁；
2. 「我刚才说了什么」+ --parent-run → 复述上一轮（多轮历史）；
3. 「帮我修一下 bug」（未选仓库）→ 请用户先选仓库；
4. 小任务（verses 仓库，询问模式 + 自动批准）→ result.kind=task，done / pass；
5. 正式版拒绝 `--demo`。

用法：python packaging/core/smoke_core.py <tw 可执行文件路径> [--py "<跑测试的 python 命令>"] [--allow-demo]
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mock_llm", ROOT / "packaging" / "mock_llm.py")
assert _spec and _spec.loader
mock_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mock_llm)

TASK_TEXT = "line_count 把空行也算进去了：「床前明月光\\n\\n疑是地上霜\\n」应为 2 行，实际返回 4。帮我修一下。"


def make_repo(path: Path) -> Path:
    for name, text in mock_llm.VERSES_FILES.items():
        f = path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    git = ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run([*git, *args], cwd=path, check=True, stdin=subprocess.DEVNULL, timeout=60)
    return path


def turn(
    tw: str, env: dict[str, str], tmp: Path, name: str, args: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errf = (tmp / f"stderr-{name}.log").open("w+", encoding="utf-8")
    p = subprocess.Popen(
        [tw, "run", "--jsonl", "--live", "--allow-peak", *args],
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
    seen: list[dict[str, Any]] = []
    for raw in p.stdout:
        obj = json.loads(raw)
        seen.append(obj)
        if obj.get("kind") == "approval_requested":
            rid = obj["payload"]["request_id"]
            msg = {"cmd": "approve", "request_id": rid, "decision": "allow", "scope": "once"}
            p.stdin.write(json.dumps(msg) + "\n")
            p.stdin.flush()
        if obj.get("kind") in ("approval_requested", "turn_finished") or obj.get("bridge"):
            brief = json.dumps(obj.get("payload") or obj, ensure_ascii=False)[:140]
            print("  ·", obj.get("bridge") or obj.get("kind"), brief, flush=True)
        if obj.get("bridge") in ("result", "error"):
            break
    p.stdin.close()
    code = p.wait(timeout=120)
    watchdog.cancel()
    errf.seek(0)
    err = errf.read()[-4000:]
    errf.close()
    res = seen[-1] if seen else {}
    assert code == 0 and res.get("bridge") == "result", (res, err)
    assert "TW_LLM_BASE_URL_OVERRIDE" in err, "缺少测试 base_url 告警"
    return res, seen


def kinds(seen: list[dict[str, Any]]) -> set[str]:
    return {x["kind"] for x in seen if "kind" in x and "v" in x}


def run_mock(tw: str, tmp: Path, py: str) -> dict[str, Any]:
    server = mock_llm.MockServer(py=py).start()
    home = tmp / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8",
           "PYTHONUTF8": "1", "TW_HANG_DUMP_S": "60", "TW_LLM_BASE_URL_OVERRIDE": server.url,
           "DEEPSEEK_API_KEY": "sk-smoke-not-a-real-key"}  # fmt: skip
    for k in ("TW_HOME", "TW_LLM_MODE"):
        env.pop(k, None)
    try:
        res, seen = turn(tw, env, tmp, "hello", ["--issue", "你好"])
        assert res["kind"] == "chat" and res["status"] == "replied" and "你好" in res["reply"], res
        k = kinds(seen)
        assert "user_message" in k and "turn_finished" in k, k
        assert not k & {"task_started", "tool_call", "verification", "task_finished"}, k
        assert "reasoning_delta" in k and "model_delta" in k, k  # 真实 SSE 流式
        run_dir = Path(res["run_dir"])
        assert (run_dir / "turn.json").is_file() and not (run_dir / "patch.diff").exists()
        first = res["run_id"]
        print("你好 → 直接回复：", res["reply"])

        res, _ = turn(tw, env, tmp, "recall", ["--issue", "我刚才说了什么？", "--parent-run", first])
        assert res["kind"] == "chat" and "「你好」" in res["reply"], res
        print("多轮历史：", res["reply"])

        res, seen = turn(tw, env, tmp, "norepo", ["--issue", "帮我修一下 bug"])
        assert res["kind"] == "chat" and "仓库" in res["reply"] and "task_started" not in kinds(seen), res
        print("未选仓库 → ", res["reply"])

        repo = make_repo(tmp / "verses")
        test_cmd = f"{py} -m unittest discover -s tests -t ."
        res, seen = turn(tw, env, tmp, "task", ["--repo", str(repo), "--issue", TASK_TEXT, "--parent-run", first,
                                               "--permission-mode", "ask", "--backend", "none",
                                               "--test-cmd", test_cmd])  # fmt: skip
        assert res["kind"] == "task" and res["status"] == "done" and res["verdict"] == "pass", res
        k = kinds(seen)
        assert {"user_message", "task_started", "approval_requested", "verification", "turn_finished"} <= k, k
        print("小任务：", {"status": res["status"], "verdict": res["verdict"], "risk": res["risk_level"]})
        stats = server.requests
        assert stats and all(r["auth"] and r["stream"] for r in stats), stats
        stages = [r["stage"] for r in stats]
        assert stages.count("chat") == 4 and "executor" in stages, stages
        assert (home / ".triwitness" / "ledger.sqlite").is_file(), "账本没有记录"
        return {"requests": len(stats), "executor_calls": stages.count("executor")}
    finally:
        server.stop()


def main() -> None:
    args = sys.argv[1:]
    tw = args[0]
    py = args[args.index("--py") + 1] if "--py" in args else f'"{Path(tw).resolve().as_posix()}"'
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
        if "--allow-demo" not in args:
            dm = subprocess.run([tw, "run", "--jsonl", "--demo", "--repo", str(tmp / "x")], capture_output=True,
                                text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)  # fmt: skip
            assert dm.returncode != 0 and "正式版不含演示模式" in dm.stderr, (dm.returncode, dm.stdout, dm.stderr)
            print("--demo → 已拒绝（正式版不含演示模式）")
        print("mock 全链路：", run_mock(tw, tmp, py))
    print("SMOKE OK")


if __name__ == "__main__":
    main()
