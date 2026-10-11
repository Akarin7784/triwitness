# 评审者注入缺陷集（W4-13）与消融（W4-14）

用来回答一个问题：**评审者（Reviewer）到底能不能抓住“看起来修好了、其实有错”的补丁，误报又有多少？**

## 数据集（W4-13）

- 来源：20 个已有评测任务（5 个合成 + 15 个真实 SWE 任务）的**金标准修复**（`solution/solve.sh` 里写出的源码文件，与基线版本做 diff；测试文件不进补丁）。
- 每个任务出两道题，共 40 题：
  - `dNN-clean`：原样的金标准补丁（正确，评审应 approve，用来量误报）；
  - `dNN-defect`：在金标准补丁的**改动行内**注入一个缺陷（用来量检出）。
- 注入定义在 `injections.yaml`：`find`（必须恰好匹配一次）→ `replace`，并标注文件、类别、严重级别和一句话说明。
- 缺陷类别（11 类）：missing_edge_case、wrong_constant、wrong_argument、off_by_one、incomplete_fix、wrong_regex、wrong_condition、wrong_index、spec_violation、exception_handling、wrong_variable；严重级别全部是 blocker 或 major。
- 产物：`items/<id>/{patch.diff,issue.md,item.json}`，`manifest.json`（含 digest）。`item.json` 的 `truth` 是标准答案：`{file, line, category, severity, description, in_changed_lines}`，`line` 是补丁新版本里的行号。

重建 / 校验（需要联网取 SWE 任务基线文件，缓存在 `.cache/`）：

```bash
uv run python scripts/build_reviewer_defects.py gold    # 从 solve.sh 抽金标准补丁
uv run python scripts/build_reviewer_defects.py build   # 按 injections.yaml 生成 40 题 + manifest
uv run python scripts/build_reviewer_defects.py check   # 每个补丁对基线 git apply --check
```

注意：题目里的 Issue 文本与任务一致，评审者看到的是 Issue + diff + 只读仓库，**看不到** `truth`。

## 消融（W4-14）

脚本：`scripts/reviewer_ablation.py`（prepare / run / score / bundle）。只用 deepseek-flash，所有调用记进账本（类别 `reviewer-ablation`），北京时间工作日 9–12、14–18 默认不跑。

| 臂 | 提示 | 模型配置 |
|---|---|---|
| none | — | 不评审（计算得出，零调用） |
| same | `reviewer-plain`（普通评审） | flash 思考 effort=high（与执行者同配置） |
| adversarial | `reviewer`（对抗式，当前默认） | flash 思考 effort=max |
| checklist_t03 | `reviewer-checklist` | flash 非思考，temperature 0.3 |
| checklist_t10 | `reviewer-checklist` | flash 非思考，temperature 1.0 |
| consensus_t03 / _t10 | 事后计算 | adversarial 与对应 checklist 都判阻断才阻断 |

判定：缺陷题“检出”= blocker/major 发现落在注入文件、行号差 ≤ 3；干净题“误报”= 出现 blocker（verdict 退回）。区间为 Wilson 95%。`findings.csv` 列出全部发现，供人工复核。

配对比较（W5，`triwitness.eval.ablation`）：各臂与 adversarial 在同一批题上配对——缺陷题比“检出”、干净题比“放行”（= 不误报），给出 McNemar 精确检验、Holm 校正和配对 bootstrap 95% 区间；只有 Holm p < 0.05 且区间不含 0 才写“更好 / 更差”。

### 在 Windows 上一键运行（Eva）

```powershell
# 先在“系统环境变量”里设置 DEEPSEEK_API_KEY，重开终端
powershell -ExecutionPolicy Bypass -File scripts\windows\run-reviewer-ablation.ps1 -Smoke   # 冒烟，约 ¥0.1
powershell -ExecutionPolicy Bypass -File scripts\windows\run-reviewer-ablation.ps1          # 全量 160 次
```

第二轮（Eva 2026-10-12 定）：只跑 adversarial 与 checklist_t10，补两次重复（与第一轮 r0 合计 3 次），约 ¥10：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\run-reviewer-ablation.ps1 -Arms adversarial,checklist_t10 -Repeats 3
```

`-Repeats N` 是每题每臂一共 N 次（r0..r{N-1}），已有结果按文件名跳过；`-OutDir` 里找不到第一轮 r0 会拒绝运行（加 `-Force` 才重跑 r0）。
消融里关掉了编排器默认的“最后一次强制提交”，与第一轮协议一致；结果 JSON 多了 `task_id`（对账）与 `verdict_on_last_call`。
结果包默认只带没下结论 / 出错那几次的轨迹（`bundle --all-runs` 带全部）。

第二轮已跑（2026-10-12 01:32–02:16 UTC+8，¥10.2728），与第一轮合并后的结果与判定（ADR-0007 确认）见 `evals/baselines/2026-10-12-reviewer-ablation/README.md`。

脚本会克隆 / 更新仓库 → 构建 `evals/reviewer/Dockerfile` 镜像（构建时下载基线源码）→ 在容器里并发跑 → 评分 → 把结果、轨迹和账本打成 `%USERPROFILE%\tw-ablation-out\reviewer-ablation-<时间>.zip`。密钥只经 `docker run -e DEEPSEEK_API_KEY` 透传，不进镜像和结果包。中断后重跑同一命令会跳过已完成的题。

### 在 Linux / box 上

```bash
uv run python scripts/reviewer_ablation.py prepare --out out/ablation
TW_LLM_MODE=live uv run python scripts/reviewer_ablation.py run --out out/ablation --parallel 4
uv run python scripts/reviewer_ablation.py score --out out/ablation
uv run python scripts/reviewer_ablation.py bundle --out out/ablation
```
