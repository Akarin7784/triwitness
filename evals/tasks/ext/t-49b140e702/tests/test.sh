#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/string_test.py::TestString::test_regex \
  tests/string_test.py::TestString::test_string \
  tests/string_test.py::TestString::test_boolean \
  tests/string_test.py::TestString::test_number \
  tests/string_test.py::TestString::test_array \
  tests/string_test.py::TestString::test_map \
  tests/string_test.py::TestString::test_map2 \
  tests/string_test.py::TestString::test_escape \
  tests/string_test.py::TestString::test_replace \
  tests/string_test.py::TestString::test_split \
  tests/string_test.py::TestString::test_trim; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
