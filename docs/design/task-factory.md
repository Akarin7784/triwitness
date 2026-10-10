# 任务工厂（W2-20～23）

实现：`scripts/task_factory.py`（mine / build / split）、`scripts/import_swe_rebench.py`（转换 + Dockerfile 模板）、`src/triwitness/eval/suites.py`（冻结套件）。

## 1. 流程

1. **mine**：SWE-rebench leaderboard（2025-10～2026-03 月度拆分，污染风险最低）+ filtered 拆分（较旧）。过滤：pytest、无系统包 / conda、Python 3.9–3.13、改动 ≤3 个 .py 且 ≤80 行、测试补丁只改测试、F2P 1–10、P2P 3–400、Issue 150–6000 字、宽松许可证（MIT / Apache-2.0 / BSD / ISC / PSF / Unlicense…）、同仓库最多 2 个。结果：`evals/factory/candidates.json`（1161 行 → 138 个候选）。
2. **build**：两阶段构建——先按数据集的安装命令装一遍，`pip freeze` 得到钉死版本，再用钉死版本构建最终镜像（可复现）；validate：空 Agent reward 0、参考解 reward 1，各再跑 2 次去抖（6 次全对才算 ok）；数据集里仓库已不存在的 P2P 用例（pytest `not found`）自动剔除后重验。日志：`evals/factory/build_log*.json`。
3. **split**：test = 最新的 leaderboard 任务（`--allow-test` 才能跑，只出报告）；dev = W1 的 10 个 + filtered 较新 5 个；dev-smoke = dev 中固定 5 个。`evals/suites/*.yaml` 记录内容 digest，任务内容一变 `check_suite` 就报错（冻结）。

## 2. 磁盘与 Docker（2026-10-10 两次写满 126G 共享盘的教训）

- **存储驱动**：box 的根文件系统是 overlayfs，dockerd 原先退回到 `vfs`（每层全量拷贝，`docker system df` 显示 4.4G、实际占 37G）。已改为 **fuse-overlayfs**：`apt install fuse-overlayfs` + `/etc/docker/daemon.json` = `{"storage-driver": "fuse-overlayfs"}`，重启 dockerd（`sudo dockerd >> /tmp/dockerd.log`）。overlay2 不能叠在 overlayfs 上，所以用 FUSE 版本。验证：`tw task validate`、`pytest -m "integration and not live"` 17 项全过。切换后旧 vfs 镜像不可见，已删 `/var/lib/docker/vfs`（基础镜像重新 pull、任务镜像按需重建）。回滚：删 daemon.json 后重启 dockerd。
- **守卫**：剩余空间 < 15G 时不再开始新构建（`MIN_FREE_GB`），已排队的记为 `error`，之后 `--retry error` 续跑。
- **清理**：每个任务做完 `docker rmi` 自己的镜像（tag 是内容哈希，评测时按需重建）+ 清 1 小时前的悬空层（不会误删在建的层）；批量构建结束后再 `docker image prune -f`。目标：磁盘占用 < 70%。
- **Langfuse**：自托管栈（6 个容器、3–4G 内存）只在需要看 trace 时起，用完 `docker compose ... down`；平时用 OTLP 导出到任意后端或不开。
