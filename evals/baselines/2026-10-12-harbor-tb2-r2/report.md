# 外部对照：Terminal-Bench 2.0 子集 × TriWitness（Harbor）

生成：2026-10-12 05:51 北京时间；terminal-bench-2@2fd12b88aafd；Agent deepseek-flash（非思考），harness baseline（文件 + bash 工具，无快照 / diff）。

**解决 26/30**（Wilson 95%：70%–95%）；花费 ¥1.8624（Agent 上报，账本类别 harbor-external）。
样本只有 30 次试验，只作外部参照，不和 dev / test 的 SWE 类结果直接比较。

| 任务 | 试次 | 奖励 | TriWitness 状态 | 步数 | ¥ | 命中 | 异常 |
|---|---|---|---|---|---|---|---|
| terminal-bench/cobol-modernization | cobol-modernization__SDgZYWu | 1.0 | budget_exceeded | 100 | 0.237992 | 99% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__bey4hbj | 1.0 | done | 13 | 0.030853 | 95% |  |
| terminal-bench/fix-git | fix-git__GoyWxBL | 1.0 | done | 18 | 0.031498 | 94% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__4YbF5VN | 1.0 | done | 16 | 0.024307 | 95% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__fuZb82U | 1.0 | done | 19 | 0.037665 | 96% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__TF4YT7k | 1.0 | done | 21 | 0.038453 | 96% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__J3JanrA | 1.0 | done | 12 | 0.027338 | 95% |  |
| terminal-bench/overfull-hbox | overfull-hbox__FcV7yv9 | 0.0 | cancelled | — | 0.038312 | 93% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__vqVaZhW | 0.0 | budget_exceeded | 100 | 0.16742 | 99% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__7AbEZNy | 1.0 | done | 13 | 0.01811 | 94% |  |
| terminal-bench/cobol-modernization | cobol-modernization__VzfQrnQ | 0.0 | budget_exceeded | 100 | 0.209879 | 99% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__KWJ8aye | 1.0 | done | 13 | 0.033068 | 94% |  |
| terminal-bench/fix-git | fix-git__gVzLJxq | 1.0 | done | 23 | 0.031941 | 96% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__kj4HnhN | 1.0 | done | 22 | 0.035678 | 96% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__PtnDNjf | 1.0 | done | 12 | 0.022361 | 95% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__hd3bn6d | 1.0 | done | 18 | 0.034419 | 95% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__dEagLjq | 1.0 | done | 15 | 0.033036 | 96% |  |
| terminal-bench/overfull-hbox | overfull-hbox__VFBgGAH | 0.0 | cancelled | — | 0.085398 | 98% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__fvAwg2f | 1.0 | done | 71 | 0.128238 | 99% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__gVVaHff | 1.0 | done | 10 | 0.012487 | 94% |  |
| terminal-bench/cobol-modernization | cobol-modernization__Uofuux5 | 1.0 | done | 43 | 0.116298 | 98% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__wEUkjBx | 1.0 | done | 14 | 0.036319 | 95% |  |
| terminal-bench/fix-git | fix-git__H7GhLd6 | 1.0 | done | 17 | 0.029651 | 94% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__pamwbBz | 1.0 | done | 17 | 0.033242 | 95% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__2wv8PsS | 1.0 | done | 32 | 0.079165 | 97% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__fTWPAsm | 1.0 | done | 19 | 0.033986 | 95% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__AuSrDo6 | 1.0 | done | 16 | 0.035092 | 94% |  |
| terminal-bench/overfull-hbox | overfull-hbox__cjTTvRh | 1.0 | done | 44 | 0.116469 | 98% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__BABbnYU | 1.0 | done | 46 | 0.076325 | 98% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__bHQj8Cy | 1.0 | done | 23 | 0.027394 | 96% |  |

按题（多次重复）：

| 任务 | 解决 / 次数 |
|---|---|
| terminal-bench/cobol-modernization | 2/3 |
| terminal-bench/constraints-scheduling | 3/3 |
| terminal-bench/fix-git | 3/3 |
| terminal-bench/git-leak-recovery | 3/3 |
| terminal-bench/multi-source-data-merger | 3/3 |
| terminal-bench/nginx-request-logging | 3/3 |
| terminal-bench/openssl-selfsigned-cert | 3/3 |
| terminal-bench/overfull-hbox | 1/3 |
| terminal-bench/polyglot-c-py | 2/3 |
| terminal-bench/prove-plus-comm | 3/3 |
