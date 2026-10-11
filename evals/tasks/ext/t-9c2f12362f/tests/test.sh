#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_error_filepath \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_complexity_error \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_error1 \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_error1_and_error2 \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_error_filepath_with_prefix \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_logging_errro \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_no_errors \
  tests/test_formatter.py::TestGitlabCodeClimateFormatter::test_security_error; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
