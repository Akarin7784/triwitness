#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests.py::TestSLPP::test_comments \
  tests.py::TestUtilityFunctions::test_differ \
  tests.py::TestUtilityFunctions::test_is_iterator \
  tests.py::TestSLPP::test_basic \
  tests.py::TestSLPP::test_bool \
  tests.py::TestSLPP::test_consistency \
  tests.py::TestSLPP::test_nil \
  tests.py::TestSLPP::test_numbers \
  tests.py::TestSLPP::test_string \
  tests.py::TestSLPP::test_table \
  tests.py::TestSLPP::test_unicode; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
