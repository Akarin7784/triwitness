# W2-25 DeepSeek 基线（2026-10-10）

- `test/`：test 35 × baseline-deepseek（flash 思考 high）× 1；`dev/`：dev 15 × baseline-deepseek-nothink（flash 非思考）× 1。
- 每个 attempt 留 `result.json`（复核后）、`result.orig.json`（如有改动，原始版本）和 `patch.diff`；
  dymos-1021（4.6 MB，含 openmdao 运行产物）与 h-transport-224 的补丁太大，只留 `patch.files.txt` 文件清单。原始轨迹在 `evals/results/`（gitignore）。
- `analysis.md` / `analysis.json`：分子集 CI、失败模式、篡改复核、infra 判定、档位决定。
- 复核改了什么：①篡改分类按 63e1233 的新规则重算（只影响标记，不影响判分）；②ultraplot-696、xcp_d-1433 标为 infra（reward=null），原因与修复见 analysis.md §2；
  `test/errors.orig.json` 是 runner 残留的旧条目（opensandbox-816 首次 BuildError，续跑已成功）。
