在工作区执行 shell 命令（非交互；vim、less、top 等会被拒绝）。timeout_s 默认 120，最大 600。
返回退出码与（可能截断的）输出。跑测试优先用 run_tests；读改文件优先用专用工具。
