# 外部对照：Terminal-Bench 2.0 子集 × TriWitness（Harbor）

生成：2026-10-12 14:31 北京时间；terminal-bench-2@2fd12b88aafd；Agent deepseek-flash（非思考），harness baseline（文件 + bash 工具，无快照 / diff）。

**解决 28/30**（Wilson 95%：79%–98%）；花费 ¥3.0144（Agent 上报，账本类别 harbor-external）。
样本只有 30 次试验，只作外部参照，不和 dev / test 的 SWE 类结果直接比较。

| 任务 | 试次 | 奖励 | TriWitness 状态 | 步数 | ¥ | 命中 | 异常 |
|---|---|---|---|---|---|---|---|
| terminal-bench/cobol-modernization | cobol-modernization__Lp5nXZL | 1.0 | done | 47 | 0.111889 | 98% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__fYt3ok2 | 1.0 | done | 14 | 0.040421 | 96% |  |
| terminal-bench/fix-git | fix-git__BotHpDi | 1.0 | done | 23 | 0.032017 | 96% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__bZHSEkA | 1.0 | done | 14 | 0.026493 | 95% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__pc57SyC | 1.0 | done | 11 | 0.025468 | 95% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__DdRTpAm | 1.0 | done | 19 | 0.034837 | 95% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__aAXDsgN | 1.0 | done | 12 | 0.024607 | 95% |  |
| terminal-bench/overfull-hbox | overfull-hbox__XPPZy55 | 1.0 | done | 53 | 0.100827 | 98% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__TjBLbvY | 1.0 | done | 38 | 0.201647 | 98% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__rD6thdU | 1.0 | done | 13 | 0.018065 | 94% |  |
| terminal-bench/cobol-modernization | cobol-modernization__iySfj3R | 1.0 | done | 88 | 0.237518 | 99% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__LmduUPQ | 1.0 | done | 9 | 0.027853 | 94% |  |
| terminal-bench/fix-git | fix-git__hr755j7 | 0.0 | done | 18 | 0.026619 | 95% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__mqRhPPA | 1.0 | done | 19 | 0.03769 | 95% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__genq553 | 1.0 | done | 13 | 0.026534 | 95% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__v3EE9Zy | 1.0 | done | 14 | 0.049777 | 94% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__vMcPpkF | 1.0 | done | 18 | 0.060966 | 96% |  |
| terminal-bench/overfull-hbox | overfull-hbox__BHAzPo5 | 1.0 | done | 24 | 0.072475 | 96% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__aiWcm94 | 1.0 | done | 120 | 0.52225 | 99% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__gVnmucF | 1.0 | done | 17 | 0.04692 | 96% |  |
| terminal-bench/cobol-modernization | cobol-modernization__uBFVgDd | 1.0 | done | 82 | 0.354327 | 99% |  |
| terminal-bench/constraints-scheduling | constraints-scheduling__HBLiEp5 | 1.0 | done | 14 | 0.056243 | 95% |  |
| terminal-bench/fix-git | fix-git__MA6xDR9 | 0.0 | done | 20 | 0.062362 | 95% |  |
| terminal-bench/git-leak-recovery | git-leak-recovery__PZ282ZX | 1.0 | done | 18 | 0.064375 | 96% |  |
| terminal-bench/multi-source-data-merger | multi-source-data-merger__G9njdZs | 1.0 | done | 15 | 0.063585 | 96% |  |
| terminal-bench/nginx-request-logging | nginx-request-logging__bs4namP | 1.0 | done | 19 | 0.070892 | 96% |  |
| terminal-bench/openssl-selfsigned-cert | openssl-selfsigned-cert__CfeXS9f | 1.0 | done | 11 | 0.050052 | 95% |  |
| terminal-bench/overfull-hbox | overfull-hbox__EM2skfY | 1.0 | done | 32 | 0.145589 | 96% |  |
| terminal-bench/polyglot-c-py | polyglot-c-py__zPi2XxU | 1.0 | done | 80 | 0.382815 | 99% |  |
| terminal-bench/prove-plus-comm | prove-plus-comm__UtGezHV | 1.0 | done | 15 | 0.039332 | 95% |  |

按题（多次重复）：

| 任务 | 解决 / 次数 |
|---|---|
| terminal-bench/cobol-modernization | 3/3 |
| terminal-bench/constraints-scheduling | 3/3 |
| terminal-bench/fix-git | 1/3 |
| terminal-bench/git-leak-recovery | 3/3 |
| terminal-bench/multi-source-data-merger | 3/3 |
| terminal-bench/nginx-request-logging | 3/3 |
| terminal-bench/openssl-selfsigned-cert | 3/3 |
| terminal-bench/overfull-hbox | 3/3 |
| terminal-bench/polyglot-c-py | 3/3 |
| terminal-bench/prove-plus-comm | 3/3 |
