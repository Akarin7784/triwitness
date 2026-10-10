运行任务配置的测试命令。mode：full（默认，全部）、related（只跑与改动文件相关的测试，找不到则全部）、selected（只跑 selector，如 tests/test_x.py::test_y 或 -k 表达式）；rerun_failed=true 只重跑上一次失败的用例。
返回通过 / 失败统计；失败时只给出失败用例的断言与栈。声明完成前必须用 full 跑一次。
