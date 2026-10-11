"""HarborSandbox：用“本地 bash 当容器”的假 Harbor 环境测 exec / 读写文件 / 截断 / 超时 / 不支持 diff。"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from triwitness.core.errors import SandboxError
from triwitness.integrations.harbor_sandbox import HarborSandbox

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("timeout") or not shutil.which("base64"),
    reason="假环境需要 POSIX bash / coreutils",
)


class LocalEnv:
    """Harbor BaseEnvironment 的最小替身：exec 在本机 bash 里跑，upload_file 拷文件。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[dict[str, object]] = []

    async def exec(self, command: str, cwd: str | None = None, env: dict[str, str] | None = None,
                   timeout_sec: int | None = None) -> SimpleNamespace:  # fmt: skip
        self.calls.append({"command": command, "cwd": cwd, "env": env, "timeout_sec": timeout_sec})
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", command, cwd=cwd or str(self.root), env={"PATH": "/usr/bin:/bin", **(env or {})},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        out, err = await proc.communicate()
        return SimpleNamespace(stdout=out.decode(), stderr=err.decode(), return_code=proc.returncode)

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        shutil.copyfile(source_path, target_path)


@pytest.fixture
def env(tmp_path: Path) -> LocalEnv:
    return LocalEnv(tmp_path)


async def test_attach_uses_container_cwd(env: LocalEnv, tmp_path: Path) -> None:
    sb = await HarborSandbox.attach(env)
    assert sb.spec.workdir == str(tmp_path)
    assert sb.backend == "remote"


async def test_attach_falls_back_to_app() -> None:
    class Odd:
        async def exec(self, command: str, cwd: str | None = None, env: dict[str, str] | None = None,
                       timeout_sec: int | None = None) -> SimpleNamespace:  # fmt: skip
            return SimpleNamespace(stdout="", stderr="", return_code=1)

        async def upload_file(self, source_path: Path | str, target_path: str) -> None: ...

    sb = await HarborSandbox.attach(Odd())
    assert sb.spec.workdir == "/app"


async def test_exec_runs_in_workdir_with_timeout_wrapper(env: LocalEnv, tmp_path: Path) -> None:
    sb = HarborSandbox(env, workdir=str(tmp_path))
    r = await sb.exec("echo hi && pwd && echo oops >&2 && exit 3", env={"X": "1"})
    assert r.exit_code == 3
    assert r.stdout.splitlines() == ["hi", str(tmp_path)]
    assert r.stderr.strip() == "oops"
    call = env.calls[-1]
    assert str(call["command"]).startswith("timeout -k 5 120 bash -c ")
    assert call["cwd"] == str(tmp_path) and call["env"] == {"X": "1"} and call["timeout_sec"] == 150


async def test_exec_relative_cwd_and_timeout(env: LocalEnv, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    sb = HarborSandbox(env, workdir=str(tmp_path))
    r = await sb.exec("pwd", cwd="sub")
    assert r.stdout.strip() == str(tmp_path / "sub")
    slow = await sb.exec("sleep 5", timeout_s=1)
    assert slow.timed_out and slow.exit_code == 124


async def test_exec_harbor_timeout_maps_to_124(tmp_path: Path) -> None:
    class Hangs:
        async def exec(self, command: str, cwd: str | None = None, env: dict[str, str] | None = None,
                       timeout_sec: int | None = None) -> SimpleNamespace:  # fmt: skip
            raise TimeoutError

        async def upload_file(self, source_path: Path | str, target_path: str) -> None: ...

    r = await HarborSandbox(Hangs(), workdir="/app").exec("sleep 999", timeout_s=1)
    assert r.timed_out and r.exit_code == 124


async def test_output_is_capped(env: LocalEnv, tmp_path: Path) -> None:
    sb = HarborSandbox(env, workdir=str(tmp_path), max_output_bytes=1000)
    r = await sb.exec("head -c 5000 /dev/zero | tr '\\0' a")
    assert r.truncated
    assert "已截断" in r.stdout and len(r.stdout.encode()) < 1200


async def test_write_then_read_roundtrip(env: LocalEnv, tmp_path: Path) -> None:
    sb = HarborSandbox(env, workdir=str(tmp_path))
    data = "第一行\n二\x00binary\n".encode()
    await sb.write_file("deep/dir/f.bin", data, mode=0o755)
    target = tmp_path / "deep/dir/f.bin"
    assert target.read_bytes() == data
    assert target.stat().st_mode & 0o777 == 0o755
    assert await sb.read_file("deep/dir/f.bin") == data
    assert await sb.read_file(str(target)) == data


async def test_read_missing_raises(env: LocalEnv, tmp_path: Path) -> None:
    sb = HarborSandbox(env, workdir=str(tmp_path))
    with pytest.raises(SandboxError):
        await sb.read_file("nope.txt")


async def test_snapshot_and_diff_unsupported(env: LocalEnv, tmp_path: Path) -> None:
    sb = HarborSandbox(env, workdir=str(tmp_path))
    for coro in (sb.snapshot("x"), sb.restore("x"), sb.diff("x")):
        with pytest.raises(SandboxError):
            await coro
    await sb.close()


def test_agent_module_needs_harbor() -> None:
    """Agent 模块只在装了 harbor 时可导入（harbor 不是依赖）。"""
    pytest.importorskip("harbor")
    from triwitness.integrations.harbor_agent import TriWitnessAgent

    assert TriWitnessAgent.name() == "triwitness"


# —— W5-13 第二轮：外部任务的复现产物（polyglot-c-py 因 tests/tw_repro 残留判 0）——


async def test_cleanup_removes_only_new_repro_artifacts(tmp_path: Path) -> None:
    from triwitness.tools.repro import cleanup_repro_artifacts, snapshot_repro_dirs

    app = tmp_path / "app"
    (app / "proj" / "tests").mkdir(parents=True)  # 任务自带的 tests：保留
    (app / "proj" / "tests" / "test_x.py").write_text("x\n")
    (app / "old" / "__pycache__").mkdir(parents=True)  # 运行前就有的缓存：保留
    sb = HarborSandbox(LocalEnv(tmp_path), workdir=str(app))
    before = await snapshot_repro_dirs(sb, str(app))
    # Agent 运行期间：
    (app / "polyglot" / "tests" / "tw_repro").mkdir(parents=True)
    (app / "polyglot" / "tests" / "tw_repro" / "test_issue_1.py").write_text("t\n")
    (app / "polyglot" / "main.py.c").write_text("c\n")
    (app / "proj" / "tests" / "tw_repro").mkdir()
    (app / "proj" / "tests" / "tw_repro" / "test_issue_2.py").write_text("t\n")
    (app / "proj" / ".pytest_cache").mkdir()
    (app / "out" / "tests").mkdir(parents=True)  # Agent 新建、且是产物的一部分（非空）：保留
    (app / "out" / "tests" / "result.txt").write_text("r\n")
    removed = await cleanup_repro_artifacts(sb, str(app), before)
    assert sorted(p.removeprefix(str(app)) for p in removed) == sorted(
        ["/polyglot/tests/tw_repro", "/polyglot/tests", "/proj/tests/tw_repro", "/proj/.pytest_cache"]
    )
    assert sorted(x.name for x in (app / "polyglot").iterdir()) == ["main.py.c"]  # verifier 要的样子
    assert (app / "proj" / "tests" / "test_x.py").is_file() and (app / "old" / "__pycache__").is_dir()
    assert (app / "out" / "tests" / "result.txt").is_file()


async def test_cleanup_noop_when_nothing_new(tmp_path: Path) -> None:
    from triwitness.tools.repro import cleanup_repro_artifacts, snapshot_repro_dirs

    (tmp_path / "app" / "tests").mkdir(parents=True)
    sb = HarborSandbox(LocalEnv(tmp_path), workdir=str(tmp_path / "app"))
    before = await snapshot_repro_dirs(sb, str(tmp_path / "app"))
    assert await cleanup_repro_artifacts(sb, str(tmp_path / "app"), before) == []
    assert (tmp_path / "app" / "tests").is_dir()  # 原有的空 tests 不删
