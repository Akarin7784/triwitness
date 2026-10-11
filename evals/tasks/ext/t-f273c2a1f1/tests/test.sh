#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test_mccabe.py::McCabeTestCase::test_expr_as_statement \
  test_mccabe.py::McCabeTestCase::test_async_keywords \
  test_mccabe.py::McCabeTestCase::test_for_else_snippet \
  test_mccabe.py::McCabeTestCase::test_for_loop_snippet \
  test_mccabe.py::McCabeTestCase::test_if_elif_else_dead_path_snippet \
  test_mccabe.py::McCabeTestCase::test_nested_functions_snippet \
  test_mccabe.py::McCabeTestCase::test_print_message \
  test_mccabe.py::McCabeTestCase::test_recursive_snippet \
  test_mccabe.py::McCabeTestCase::test_sequential_snippet \
  test_mccabe.py::McCabeTestCase::test_sequential_unencapsulated_snippet \
  test_mccabe.py::McCabeTestCase::test_trivial \
  test_mccabe.py::McCabeTestCase::test_try_else \
  test_mccabe.py::RegressionTests::test_max_complexity_is_always_an_int; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
