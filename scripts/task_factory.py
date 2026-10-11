"""任务工厂 · 挖掘与筛选（W2-20）：从 SWE-rebench（含按月新增的 leaderboard 拆分）选出适合本项目的候选。

    uv run python scripts/task_factory.py mine --out evals/factory/candidates.json

规则（每条淘汰都记原因，写进 candidates.json 的 stats）：
- Python + pytest（log_parser=parse_log_pytest），安装命令只用 pip（不需要 apt），Python 3.9–3.13；
- 补丁小：改动源文件 ≤ 3 个、改动行 ≤ 80；测试补丁只改测试文件；
- FAIL_TO_PASS 1–10 条，PASS_TO_PASS 3–400 条（判分要快）；Issue 正文 150–6000 字；
- 仓库许可证宽松（MIT / Apache-2.0 / BSD / ISC / PSF / Unlicense / 0BSD）——隐藏测试与参考解会复制进本仓库；
- 每个仓库至多 2 个（多样性）。
数据集许可证 CC-BY-4.0（nebius/SWE-rebench、nebius/SWE-rebench-leaderboard），
每个任务的 task.toml 里记录来源与仓库许可证。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache" / "triwitness"
ROWS = "https://datasets-server.huggingface.co/rows?dataset={ds}&config=default&split={split}&offset={off}&length=100"
LEADERBOARD = "nebius/SWE-rebench-leaderboard"
FILTERED = "nebius/SWE-rebench"
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PSF-2.0", "Unlicense", "0BSD", "MIT-0"}
# 镜像过大或不是 pip 直装（uv sync / venv / 子模块 / 改 pyproject）：本机构建慢、不可复现，W2 先不收
HEAVY_INSTALL = ("uv sync", "uv venv", "submodule", "sed ", "DEBIAN", "torch", "tensorflow", "jax", "[complete")
HEAVY_REPOS = {"keras-team/keras", "google/flax", "huggingface/transformers", "newton-physics/newton", "pydata/xarray",
               "dask/dask", "spack/spack", "All-Hands-AI/OpenHands"}  # fmt: skip
TEST_PATH = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def fetch_split(ds: str, split: str, size: int) -> list[dict]:
    path = CACHE / "rows" / f"{ds.replace('/', '__')}__{split}.json"
    if path.exists():
        return json.loads(path.read_text())
    out: list[dict] = []
    for off in range(0, size, 100):
        for attempt in range(5):
            try:
                with urllib.request.urlopen(ROWS.format(ds=ds, split=split, off=off), timeout=120) as r:
                    out += [x["row"] for x in json.load(r)["rows"]]
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        else:
            raise SystemExit(f"拉取失败：{ds} {split} offset={off}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def splits(ds: str) -> dict[str, int]:
    with urllib.request.urlopen(f"https://datasets-server.huggingface.co/size?dataset={ds}", timeout=60) as r:
        return {s["split"]: s["num_rows"] for s in json.load(r)["size"]["splits"]}


def license_of(repo: str, cache: dict[str, str]) -> str:
    if repo not in cache:
        r = subprocess.run(["gh", "api", f"repos/{repo}", "--jq", ".license.spdx_id // \"NONE\""],
                           capture_output=True, text=True)  # fmt: skip
        cache[repo] = r.stdout.strip() if r.returncode == 0 else "UNKNOWN"
    return cache[repo]


SPDX = {"MIT License": "MIT", "Apache License 2.0": "Apache-2.0", 'BSD 3-Clause "New" or "Revised" License':
        "BSD-3-Clause", 'BSD 2-Clause "Simplified" License': "BSD-2-Clause", "Expat License": "MIT",
        "3-Clause BSD license": "BSD-3-Clause", "The Unlicense": "Unlicense"}  # fmt: skip


def to_spdx(lic: str) -> str:
    """数据集 / GitHub 的许可证名 → SPDX；task.toml 里的 "X（代码）；SWE-rebench 数据集 CC-BY-4.0" 取代码部分。"""
    lic = lic.split("（")[0].strip()
    return SPDX.get(lic, lic)


def patch_files(patch: str) -> list[str]:
    return re.findall(r"^diff --git a/\S+ b/(\S+)$", patch, re.M)


def changed_lines(patch: str) -> int:
    return sum(1 for ln in patch.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---")))


def as_list(v: object) -> list[str]:
    return v if isinstance(v, list) else json.loads(str(v or "[]"))


def reject_reason(row: dict) -> str | None:
    cfg = row.get("install_config") or {}
    if cfg.get("log_parser") not in (None, "parse_log_pytest"):
        return "非 pytest"
    install = cfg.get("install") or ""
    if "apt" in install or cfg.get("pre_install") or cfg.get("docker_specs") or cfg.get("env_yml_path"):
        return "需要系统包 / conda"
    if install and not re.fullmatch(r"[\w\s.\-=\[\],\"'&/<>:+]*", install):
        return "安装命令复杂"
    if any(k in install for k in HEAVY_INSTALL) or row["repo"] in HEAVY_REPOS:
        return "依赖过重 / 非 pip 安装"
    py = str(cfg.get("python") or "3.11")
    if py not in ("3.9", "3.10", "3.11", "3.12", "3.13"):
        return f"Python {py}"
    src = patch_files(row["patch"])
    if not src or len(src) > 3 or any(not f.endswith(".py") for f in src):
        return "改动文件数 / 非 .py"
    if changed_lines(row["patch"]) > 80:
        return "补丁 > 80 行"
    if any(not TEST_PATH.search(f) for f in patch_files(row["test_patch"])):
        return "测试补丁改了非测试文件"
    f2p, p2p = as_list(row["FAIL_TO_PASS"]), as_list(row["PASS_TO_PASS"])
    if not 1 <= len(f2p) <= 10:
        return "F2P 数量"
    if not 3 <= len(p2p) <= 400:
        return "P2P 数量"
    if any("::" not in t for t in f2p + p2p):
        return "测试 id 非 pytest 节点"
    n = len(row["problem_statement"] or "")
    if not 150 <= n <= 6000:
        return "Issue 长度"
    return None


def mine(out: Path, months: list[str], filtered_pages: int) -> None:
    lic_cache_path = CACHE / "licenses.json"
    lic_cache: dict[str, str] = json.loads(lic_cache_path.read_text()) if lic_cache_path.exists() else {}
    sizes = splits(LEADERBOARD)
    rows: list[tuple[str, dict]] = []
    for m in months:
        rows += [(f"{LEADERBOARD}:{m}", r) for r in fetch_split(LEADERBOARD, m, sizes[m])]
    old = CACHE / "swe-rebench-rows.json"  # W1 导入时缓存的 filtered 拆分（较旧，用于 dev）
    if old.exists():
        rows += [
            (f"{FILTERED}:filtered", r) for r in list(json.loads(old.read_text()).values())[: filtered_pages * 100]
        ]
    stats: Counter[str] = Counter()
    seen_repo: Counter[str] = Counter()
    cands = []
    for src, r in sorted(rows, key=lambda x: str(x[1]["created_at"]), reverse=True):
        why = reject_reason(r)
        spdx = ""
        if why is None:
            lic = r.get("license_name") or license_of(r["repo"], lic_cache)
            spdx = to_spdx(lic)
            if spdx not in PERMISSIVE:
                why = f"许可证 {spdx}"
            elif seen_repo[r["repo"]] >= 2:
                why = "同仓库已有 2 个候选"
        if why:
            stats[why] += 1
            continue
        seen_repo[r["repo"]] += 1
        cands.append({"instance_id": r["instance_id"], "source": src, "repo": r["repo"], "license": spdx,
                      "created_at": str(r["created_at"])[:10], "patch_lines": changed_lines(r["patch"]),
                      "f2p": len(as_list(r["FAIL_TO_PASS"])), "p2p": len(as_list(r["PASS_TO_PASS"]))})  # fmt: skip
    lic_cache_path.write_text(json.dumps(lic_cache, indent=0, sort_keys=True))
    stats["入选"] = len(cands)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"total_rows": len(rows), "stats": dict(stats.most_common()), "candidates": cands},
                              ensure_ascii=False, indent=1) + "\n")  # fmt: skip
    print(f"{len(rows)} 行 → {len(cands)} 个候选；淘汰：{dict(stats.most_common())}")


def all_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for f in sorted((CACHE / "rows").glob("*.json")):
        for r in json.loads(f.read_text()):
            rows[r["instance_id"]] = r
    old = CACHE / "swe-rebench-rows.json"
    if old.exists():
        rows.update(json.loads(old.read_text()))
    return rows


def _sh(cmd: list[str], timeout: int) -> tuple[int, str]:
    # 旧构建器：基础镜像已在本地时不再去 registry 取元数据（BuildKit 在并发构建时会卡在 load metadata），
    # 也与 validate / 评测用 docker SDK 构建的方式一致
    env = {**os.environ, "DOCKER_BUILDKIT": "0"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return r.returncode, (r.stdout + r.stderr)[-1500:]


NOT_FOUND = re.compile(r"ERROR: not found: /workspace/repo/(\S+)")
FREEZE_LINE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*(\[[\w,\-]+\])?==[\w.\-+!]+")


MIN_FREE_GB = 15  # 磁盘守卫：低于此值不再开始新构建（2026-10-10 vfs 驱动把 126G 共享盘写满两次）


def free_gb() -> float:
    return shutil.disk_usage("/var/lib/docker" if Path("/var/lib/docker").exists() else "/").free / 2**30


def build_one(cand: dict, row: dict, staging: str) -> dict:
    t0 = time.monotonic()
    if free_gb() < MIN_FREE_GB:
        rec = {k: cand[k] for k in ("instance_id", "source", "created_at")}
        return rec | {"status": "error", "log": f"disk guard: free {free_gb():.1f}G < {MIN_FREE_GB}G", "seconds": 0}
    rec = _build_one(cand, row, staging)
    # 磁盘：每个任务做完就删镜像（tag 是内容哈希，评测时按需重建；rmi 连带删掉未被共享的父层）。
    # 不能无条件 prune：旧构建器的中间层是悬空镜像，并发 prune 会删掉别的构建正在用的层
    # （2026-10-10 第一次批量构建把共享盘写满：BuildKit 缓存实际占用远大于 `docker system df` 的数字）
    if rec.get("image"):
        _sh(["docker", "rmi", "-f", rec["image"]], 120)
    # 旧构建器（vfs 存储驱动）每层都是全量拷贝：只清 1 小时前的悬空层（单阶段构建超时 25 分钟，不会误删在建的层）
    _sh(["docker", "image", "prune", "-f", "--filter", "until=60m"], 300)
    return rec | {"seconds": round(time.monotonic() - t0)}


def _build_one(cand: dict, row: dict, staging: str) -> dict:
    """两阶段构建 + validate（空 Agent 0 / 参考解 1）+ 各再跑 2 次判 flaky。返回记录（含失败原因）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import docker
    import import_swe_rebench as imp

    from triwitness.eval.task import load_task
    from triwitness.eval.validate import run_phase, validate_sync

    rec = {"instance_id": cand["instance_id"], "source": cand["source"], "created_at": cand["created_at"]}
    row = dict(row, _dataset=cand["source"].split(":")[0], _license=cand["license"], _harden=HARDEN)
    try:
        if not row.get("requirements"):
            install = (row.get("install_config") or {}).get("install") or "pip install -e ."
            d = imp.convert(dict(row, _install=install), staging)
            p1 = f"tw-factory/{d.name}:p1"
            code, log = _sh(["docker", "build", "-q", "--force-rm", "-t", p1, str(d / "environment")], 1500)
            if code != 0:
                return rec | {"status": "build_failed", "log": log, "dir": str(d)}
            code, out = _sh(
                ["docker", "run", "--rm", "--network", "none", p1, "pip", "freeze", "--exclude-editable"], 120
            )
            _sh(["docker", "rmi", "-f", p1], 120)
            pins = sorted({ln.strip() for ln in out.splitlines() if FREEZE_LINE.fullmatch(ln.strip())}, key=str.lower)
            if code != 0 or not pins:
                return rec | {"status": "freeze_failed", "log": out, "dir": str(d)}
            row["_pins"] = pins
        d = imp.convert(row, staging)
        rec["dir"] = str(d)
        task = load_task(d)
        code, log = _sh(["docker", "build", "-q", "--force-rm", "-t", task.image_tag(), str(d / "environment")], 1500)
        if code != 0:
            return rec | {"status": "build_failed", "log": log}
        client = docker.from_env(timeout=180)  # 并发构建时 dockerd 很慢，默认 30s 会 ReadTimeout
        rep = validate_sync(task, client)
        rec["image"] = rep.image
        missing = sorted(set(NOT_FOUND.findall(rep.with_solution.log_tail)))
        p2p = as_list(row["PASS_TO_PASS"])
        if not rep.ok and missing and set(missing) <= set(p2p):
            # 数据集的 PASS_TO_PASS 偶有仓库里不存在的用例（pytest: not found）：去掉这些回归用例后重验一次
            row["PASS_TO_PASS"] = [t for t in p2p if t not in missing]
            rec["dropped_p2p"] = missing
            task = load_task(imp.convert(row, staging))
            rep = validate_sync(task, client)
        if not rep.ok:
            return rec | {
                "status": "validate_failed",
                "log": "; ".join(rep.problems) + "\n" + rep.with_solution.log_tail[-800:],
            }
        rewards = [rep.without_solution.reward, rep.with_solution.reward]
        for _ in range(2):  # F2P / P2P 去抖：未打补丁必须一直 0、参考解必须一直 1
            rewards += [run_phase(task, client, rep.image, apply_solution=False).reward,
                        run_phase(task, client, rep.image, apply_solution=True).reward]  # fmt: skip
        if rewards != [0.0, 1.0] * 3:
            return rec | {"status": "flaky", "log": str(rewards)}
        return rec | {"status": "ok", "image": rep.image}
    except Exception as e:  # 导入 / 打补丁失败等
        return rec | {"status": "error", "log": f"{type(e).__name__}: {e}"[-800:]}


HARDEN = True  # W5：新建任务默认匿名 ID + 清洗 Issue + 禁用 hooks；--no-harden 复现旧格式
RETRY: set[str] = set()  # --retry 指定的状态会重跑（例如修了镜像模板之后）


def build(cands_path: Path, ids: list[str], workers: int, log_path: Path, staging: str) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cands = {c["instance_id"]: c for c in json.loads(cands_path.read_text())["candidates"]}
    rows = all_rows()
    done = json.loads(log_path.read_text()) if log_path.exists() else {}
    todo = [i for i in ids if i not in done or done[i]["status"] in RETRY]
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(build_one, cands[i], rows[i], staging): i for i in todo}
        for f in as_completed(futs):
            if free_gb() < MIN_FREE_GB:  # 已排队的不再开始（正在构建的跑完）；状态记为 error，下次 --retry error 续上
                for other in futs:
                    other.cancel()
                print(f"磁盘守卫：剩余 {free_gb():.1f}G < {MIN_FREE_GB}G，停止排队中的构建", flush=True)
            if f.cancelled():
                continue
            r = f.result()
            done[r["instance_id"]] = r
            log_path.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
            print(f"{r['status']:16} {r['seconds']:5}s {r['instance_id']}", flush=True)


SMOKE = ["csv-blank-line", "slugify-edges", "swe-conllu-64", "swe-pynmea2-124", "swe-pyflakes-765"]


def difficulty(row: dict) -> str:
    """启发式难度（W2-23；人工抽检留给 Eva）：改动行数与文件数。"""
    n, files = changed_lines(row["patch"]), len(patch_files(row["patch"]))
    if n <= 10 and files == 1:
        return "easy"
    if n > 40 or files >= 3:
        return "hard"
    return "medium"


def _set_meta(toml: Path, key: str, value: str) -> None:
    text = toml.read_text(encoding="utf-8")
    text = re.sub(rf'^{key} = ".*"$', f"{key} = {json.dumps(value)}", text, count=1, flags=re.M)
    toml.write_text(text, encoding="utf-8")


def split(log_path: Path, staging: str, n_test: int, n_dev_new: int) -> None:
    """冻结切分：test = 最新的 leaderboard 任务（污染风险最低）；dev = W1 的 10 个 + filtered 拆分里最旧的若干个。"""
    import tomllib

    sys.path.insert(0, str(ROOT / "src"))
    from triwitness.eval.suites import Suite, SuiteTask, digest, dump_suite

    rows = all_rows()
    logs = sorted(log_path.parent.glob("build_log*.json"))  # leaderboard 与 filtered 分开构建、各写一份日志
    ok = [r for p in logs for r in json.loads(p.read_text()).values() if r["status"] == "ok"]
    ok.sort(key=lambda r: (r["created_at"], r["instance_id"]), reverse=True)
    fresh = [r for r in ok if "leaderboard" in r["source"]]
    older = [r for r in ok if "leaderboard" not in r["source"]]
    dev_new = older[-n_dev_new:] if n_dev_new else []  # dev 先拿 filtered 里最旧的（污染风险最高，只用来调参）
    test = fresh[:n_test]
    if len(test) < n_test:  # leaderboard 不够时用较新的 filtered 补齐（报告里注明）
        test += [r for r in older if r not in dev_new][: n_test - len(test)]
    reserve = [r for r in ok if r not in test and r not in dev_new]
    tasks = ROOT / "evals" / "tasks"
    for split_name, picked in (("test", test), ("dev", dev_new)):
        for r in picked:
            src = Path(r["dir"])
            dst = tasks / split_name / src.name
            if src.exists():  # 重跑 split 时已经搬过的直接复用（只重写 yaml）
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(src), dst)
            _set_meta(dst / "task.toml", "difficulty", difficulty(rows[r["instance_id"]]))
            r["dir"] = str(dst)

    def entry(d: Path) -> SuiteTask:
        meta = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))["metadata"]
        src = meta.get("dataset", meta["source"])
        month = next((r["source"].split(":")[1] for r in ok if Path(r["dir"]) == d and ":" in r["source"]), None)
        return SuiteTask(id=d.name, source=f"{src}:{month}" if month else src, created_at=meta["created_at"],
                         difficulty=meta["difficulty"], license=to_spdx(meta["license"]))  # fmt: skip

    def make(name: str, dirs: list[Path], desc: str, parent: str | None = None) -> Suite:
        dirs = sorted(dirs, key=lambda p: p.name)
        return Suite(name=name, description=desc, parent=parent, digest=digest(dirs), tasks=[entry(d) for d in dirs])

    dev_dirs = [p.parent for p in sorted((tasks / "dev").glob("*/task.toml"))]
    for d in dev_dirs:  # W1 导入的 SWE 任务当时一律写了 easy：同样按启发式重标
        iid = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))["metadata"].get("instance_id")
        if iid in rows:
            _set_meta(d / "task.toml", "difficulty", difficulty(rows[iid]))
    test_dirs = [p.parent for p in sorted((tasks / "test").glob("*/task.toml"))]
    for s in (
        make("dev", dev_dirs, "开发集：调 harness / prompt 用（W1 合成 5 + W1 SWE 5 + SWE-rebench filtered 较旧 5）"),
        make("test", test_dirs, "测试集：只出报告（--allow-test）；leaderboard 最新任务，不足用 filtered 较新的补"),
        make("dev-smoke", [tasks / "dev" / i for i in SMOKE], "每周冒烟（防模型漂移）：dev 中固定 5 个", parent="dev"),
    ):
        print(f"{dump_suite(s, ROOT / 'evals' / 'suites').relative_to(ROOT)}：{len(s.tasks)} 个，digest {s.digest}")
    (ROOT / "evals" / "factory" / "reserve.json").write_text(
        json.dumps(
            [{k: r[k] for k in ("instance_id", "source", "created_at")} for r in reserve], ensure_ascii=False, indent=1
        )
        + "\n"
    )
    print(f"备用（通过校验但未入选）：{len(reserve)} 个")


def audit(roots: list[Path], out: Path | None, strict: bool) -> int:
    """防作弊审计（W5-12）：逐个任务检查 ID 匿名、git 历史 / hooks、Issue 里的上游提交链接等。只读。"""
    from collections import Counter

    from triwitness.eval.task_hardening import audit_task

    dirs = [d for r in roots for d in sorted(r.glob("*/*")) if (d / "task.toml").exists()]
    findings = [{"task": f"{d.parent.name}/{d.name}", **f.__dict__} for d in dirs for f in audit_task(d)]
    counts = Counter((f["level"], f["code"]) for f in findings)
    print(f"审计 {len(dirs)} 个任务：{', '.join(str(r) for r in roots)}")
    for (level, code), n in sorted(counts.items()):
        print(f"  {level:5} {code:22} {n}")
    for f in findings:
        if f["level"] == "error":
            print(f"  ERROR {f['task']}: {f['code']} {f['message']}")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(findings, ensure_ascii=False, indent=1) + "\n")
    bad = any(f["level"] == "error" for f in findings) or (strict and bool(findings))
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="任务工厂（W2-20～22）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine")
    m.add_argument("--out", type=Path, default=ROOT / "evals" / "factory" / "candidates.json")
    m.add_argument("--months", nargs="+", default=["2025_10", "2025_11", "2025_12", "2026_01", "2026_02", "2026_03"])
    m.add_argument("--filtered-pages", type=int, default=8)
    b = sub.add_parser("build", help="两阶段构建 + validate + 去抖（需要 docker）")
    b.add_argument("ids", nargs="*")
    b.add_argument("--candidates", type=Path, default=ROOT / "evals" / "factory" / "candidates.json")
    b.add_argument("--from-source", default=None, help="只取 source 以此开头的候选")
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--log", type=Path, default=ROOT / "evals" / "factory" / "build_log.json")
    b.add_argument("--staging", default="_staging")
    b.add_argument("--retry", nargs="*", default=[], help="重跑这些状态的记录，如 validate_failed")
    b.add_argument("--no-harden", action="store_true", help="不做 W5 防作弊加固（复现旧任务格式）")
    au = sub.add_parser("audit", help="防作弊审计（只读）：匿名 ID / git 历史与 hooks / Issue 中的上游链接")
    au.add_argument("--root", type=Path, nargs="+", default=[ROOT / "evals" / "tasks"])
    au.add_argument("--out", type=Path, default=None)
    au.add_argument("--strict", action="store_true", help="有 warn 也返回 1")
    sp = sub.add_parser("split", help="冻结 dev / test / dev-smoke 切分，写 evals/suites/*.yaml")
    sp.add_argument("--log", type=Path, default=ROOT / "evals" / "factory" / "build_log.json")
    sp.add_argument("--staging", default="_staging")
    sp.add_argument("--test", type=int, default=35)
    sp.add_argument("--dev-new", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "split":
        split(a.log, a.staging, a.test, a.dev_new)
    elif a.cmd == "mine":
        mine(a.out, a.months, a.filtered_pages)
    elif a.cmd == "audit":
        sys.exit(audit(a.root, a.out, a.strict))
    elif a.cmd == "build":
        global HARDEN
        HARDEN = not a.no_harden
        RETRY.update(a.retry)
        ids = a.ids
        if not ids:
            cs = json.loads(a.candidates.read_text())["candidates"]
            ids = [c["instance_id"] for c in cs if a.from_source is None or c["source"].startswith(a.from_source)]
        build(a.candidates, ids[: a.limit], a.workers, a.log, a.staging)


if __name__ == "__main__":
    main()
