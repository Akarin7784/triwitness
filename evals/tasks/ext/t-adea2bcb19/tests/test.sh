#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_rules.py::test_string_condition \
  tests/test_rules.py::test_category_rule \
  tests/test_rules.py::test_datetime_rule \
  tests/test_rules.py::test_numeric_condition \
  tests/test_rules.py::test_complex_rule \
  tests/test_rules.py::test_invalid_inputs \
  tests/test_rules.py::test_value_type_condition_validation \
  tests/test_rules.py::test_value_type_value_validation \
  tests/test_rules.py::test_value_type_from_field; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
