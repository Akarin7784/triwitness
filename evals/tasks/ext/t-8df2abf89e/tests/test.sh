#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/dates_tests.py::DatesTests::test_serialize_datetime_as_date \
  tests/dates_tests.py::DatesTests::test_now \
  tests/dates_tests.py::DatesTests::test_parse_date \
  tests/dates_tests.py::DatesTests::test_parse_date_none \
  tests/dates_tests.py::DatesTests::test_parse_datetime \
  tests/dates_tests.py::DatesTests::test_parse_datetime_none \
  tests/dates_tests.py::DatesTests::test_serialize_date \
  tests/dates_tests.py::DatesTests::test_serialize_datetime; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
