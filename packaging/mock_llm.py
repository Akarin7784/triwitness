"""本机 OpenAI 兼容模拟服务（仅测试用，¥0）：CI / 打包冒烟 / 界面 e2e 通过 TW_LLM_BASE_URL_OVERRIDE 指向它，
让真实的 DeepSeek 适配器 → HTTP → SSE 流式 → 对话轮 / Executor 全链路跑起来，但不碰真实模型。

- 对话阶段（请求里带 `start_repo_work` 工具）：问候 / 感谢 / 问题 → 直接回复（带一段推理）；
  明确要修改仓库 → 有仓库就调用 `start_repo_work`，没仓库就请用户先选仓库；
  「我刚才说了什么」→ 复述上一轮（验证多轮历史）。
- Executor 阶段（带 `finish` 工具）：按已有 assistant 消息数，走一遍 verses 仓库的修复脚本（同 bridge/demo.py）。
- 其他角色：回一句 ok。

用法：python packaging/mock_llm.py [--port 0] [--py "<python 命令>"] [--delay 0]
启动后在 stdout 打印一行 `MOCK_LLM_URL=http://127.0.0.1:<port>`；GET /stats 返回收到的请求摘要。
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

TASK_RE = re.compile(r"修|改|实现|添加|加上|排查|bug|fix|空行|报错|失败", re.I)
RECALL_RE = re.compile(r"刚才|上一句|之前说")
THANKS_RE = re.compile(r"谢|thank", re.I)

ISSUE_FILES = ("verses.py", "tests/test_verses.py")
REPRO = "tests/tw_repro/test_issue_demo.py"
OLD = '    return len(text.split("\\n"))\n'
NEW = "    return sum(1 for line in text.splitlines() if line.strip())\n"
REPRO_TEST = (
    "import unittest\n\nfrom verses import line_count\n\n\n"
    "class IssueDemoTest(unittest.TestCase):\n"
    "    def test_blank_lines_not_counted(self):\n"
    '        self.assertEqual(line_count("床前明月光\\n\\n疑是地上霜\\n"), 2)\n'
)
VERSES_FILES: dict[str, str] = {
    "verses.py": '"""小诗集工具。"""\n\n\ndef line_count(text: str) -> int:\n'
    '    """数一首诗有几行（空行不算）。"""\n' + OLD,
    "tests/__init__.py": "",
    "tests/test_verses.py": "import unittest\n\nfrom verses import line_count\n\n\n"
    "class LineCountTest(unittest.TestCase):\n    def test_single_line(self):\n"
    '        self.assertEqual(line_count("举头望明月"), 1)\n',
    "README.md": "# verses\n\n一个小诗集工具。\n",
}


def _text(m: dict[str, Any]) -> str:
    c = m.get("content")
    if isinstance(c, list):
        return "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


def chat_turn(messages: list[dict[str, Any]]) -> dict[str, Any]:
    system = next((_text(m) for m in messages if m.get("role") == "system"), "")
    users = [_text(m) for m in messages if m.get("role") == "user"]
    text = users[-1] if users else ""
    no_repo = "当前未选择仓库" in system
    if RECALL_RE.search(text) and len(users) > 1:
        return {"reasoning": "用户问上一轮说了什么，从对话历史里找。", "content": f"你刚才说的是：「{users[-2]}」。"}
    if TASK_RE.search(text):
        if no_repo:
            return {"reasoning": "用户要改代码，但还没选仓库。",
                    "content": "要在仓库里动手，需要先在输入框下方选一个本地仓库，选好后把要求再发一次。"}  # fmt: skip
        return {"reasoning": "用户明确要修仓库里的问题，开始仓库任务。", "content": "好的，我来看看这个问题。",
                "tool": ("start_repo_work", {"goal": text})}  # fmt: skip
    if THANKS_RE.search(text):
        return {"reasoning": "用户在道谢，简短回应。", "content": "不客气！还有别的需要随时说。"}
    if re.search(r"[?？吗么]$", text.strip()):
        return {"reasoning": "一般问题，直接回答。",
                "content": "我是 TriWitness 的编码助手：选一个本地仓库、描述要修的问题，我会先复现、再修改、"
                "再用测试验证，每一步都要你批准。"}  # fmt: skip
    return {"reasoning": "用户在打招呼，直接简短回应，不需要动代码。",
            "content": "你好！我是 TriWitness 的编码助手。选好本地仓库后，告诉我要修的问题就行；"
            "也可以先随便问我。"}  # fmt: skip


def executor_step(messages: list[dict[str, Any]], py: str) -> dict[str, Any]:
    step = sum(1 for m in messages if m.get("role") == "assistant")
    finish = {"summary": "line_count 改为只数非空行；复现测试在原代码上失败、修复后通过，原有测试仍通过。",
              "changes": [{"path": "verses.py", "kind": "modified"}], "tests_run": ["unittest discover"],
              "tests_passed": True, "confidence": 0.86,
              "open_risks": ["只按 str.strip() 判空，全角空格行也会被当成空行"]}  # fmt: skip
    script = [
        ("先读 `verses.py`。", "read_file", {"path": "verses.py"}),
        ("`split('\\n')` 把空行和末尾换行都算进去了。看看已有测试。", "read_file", {"path": "tests/test_verses.py"}),
        ("先写一个复现。", "write_file", {"path": REPRO, "content": REPRO_TEST}),
        ("提交复现。", "submit_repro", {"path": REPRO, "cmd": f"{py} -m unittest {REPRO}"}),
        ("复现成立，改成只数非空行。", "edit_file", {"path": "verses.py", "old_str": OLD, "new_str": NEW}),
        ("跑一遍全部测试。", "run_tests", {}),
        ("都通过了，收尾。", "finish", finish),
    ]
    if step >= len(script):
        return {"content": "（模拟脚本已结束）"}
    content, name, args = script[step]
    return {"reasoning": f"第 {step + 1} 步。", "content": content, "tool": (name, args)}


def respond(payload: dict[str, Any], py: str = "python") -> dict[str, Any]:
    """按请求决定这一次的回复（纯函数，单测直接调）。返回 {stage, reasoning?, content?, tool?}。"""
    tools = {t.get("function", {}).get("name") for t in payload.get("tools") or []}
    messages = payload.get("messages") or []
    if "start_repo_work" in tools:
        return {"stage": "chat", **chat_turn(messages)}
    if "finish" in tools:
        return {"stage": "executor", **executor_step(messages, py)}
    return {"stage": "other", "content": "ok"}


def chunks(model: str, r: dict[str, Any]) -> list[dict[str, Any]]:
    base = {"id": "mock-1", "object": "chat.completion.chunk", "created": int(time.time()), "model": model}

    def ch(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}

    out = [ch({"role": "assistant"})]
    for key, field in (("reasoning", "reasoning_content"), ("content", "content")):
        text = r.get(key) or ""
        out += [ch({field: text[i : i + 8]}) for i in range(0, len(text), 8)]
    finish = "stop"
    if r.get("tool"):
        name, args = r["tool"]
        call = {"index": 0, "id": f"call_mock_{abs(hash(name)) % 10000}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}  # fmt: skip
        out.append(ch({"tool_calls": [call]}))
        finish = "tool_calls"
    out.append(ch({}, finish))
    usage = {"prompt_tokens": 120, "completion_tokens": 30, "prompt_cache_hit_tokens": 0,
             "prompt_cache_miss_tokens": 120, "total_tokens": 150}  # fmt: skip
    out.append({**base, "choices": [], "usage": usage})
    return out


def full_response(model: str, r: dict[str, Any]) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": r.get("content")}
    if r.get("reasoning"):
        msg["reasoning_content"] = r["reasoning"]
    if r.get("tool"):
        name, args = r["tool"]
        fn = {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}
        msg["tool_calls"] = [{"id": "call_mock", "type": "function", "function": fn}]
    return {"id": "mock-1", "object": "chat.completion", "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if r.get("tool") else "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "prompt_cache_hit_tokens": 0,
                      "prompt_cache_miss_tokens": 120}}  # fmt: skip


class MockServer:
    def __init__(self, port: int = 0, py: str = "python", delay: float = 0.0) -> None:
        self.py, self.delay = py, delay
        self.requests: list[dict[str, Any]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a: Any) -> None:
                pass

            def do_GET(self) -> None:
                body = json.dumps({"requests": server.requests}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n) or b"{}")
                auth = (self.headers.get("Authorization") or "").startswith("Bearer ")
                r = respond(payload, server.py)
                model = str(payload.get("model") or "deepseek-chat")
                server.requests.append({"path": self.path, "stage": r["stage"], "auth": auth,
                                        "stream": bool(payload.get("stream")), "tool": (r.get("tool") or [None])[0],
                                        "messages": len(payload.get("messages") or [])})  # fmt: skip
                if not self.path.endswith("/chat/completions") or not auth:
                    self.send_response(401 if not auth else 404)
                    self.end_headers()
                    return
                if not payload.get("stream"):
                    body = json.dumps(full_response(model, r), ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                for c in chunks(model, r):
                    self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    if server.delay:
                        time.sleep(server.delay)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.httpd.daemon_threads = True

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def start(self) -> MockServer:
        threading.Thread(target=self.httpd.serve_forever, name="mock-llm", daemon=True).start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--py", default="python")
    ap.add_argument("--delay", type=float, default=0.0)
    a = ap.parse_args()
    s = MockServer(a.port, a.py, a.delay)
    print(f"MOCK_LLM_URL={s.url}", flush=True)
    s.httpd.serve_forever()


if __name__ == "__main__":
    main()
