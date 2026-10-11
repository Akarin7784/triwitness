#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_utils.py::test_parse_params \
  tests/test_utils.py::test_comments \
  tests/test_utils.py::test_parse_code \
  tests/test_utils.py::test_parse_name \
  tests/test_utils.py::test_has_model \
  tests/test_utils.py::test_parse_resp \
  tests/test_utils.py::test_parse_request; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
