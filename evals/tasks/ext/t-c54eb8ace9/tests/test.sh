#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_bugbear.py::BugbearTestCase::test_b9_flake8_next_default_options \
  tests/test_bugbear.py::BugbearTestCase::test_b001 \
  tests/test_bugbear.py::BugbearTestCase::test_b002 \
  tests/test_bugbear.py::BugbearTestCase::test_b003 \
  tests/test_bugbear.py::BugbearTestCase::test_b004 \
  tests/test_bugbear.py::BugbearTestCase::test_b005 \
  tests/test_bugbear.py::BugbearTestCase::test_b006_b008 \
  tests/test_bugbear.py::BugbearTestCase::test_b007 \
  tests/test_bugbear.py::BugbearTestCase::test_b008_extended \
  tests/test_bugbear.py::BugbearTestCase::test_b009_b010 \
  tests/test_bugbear.py::BugbearTestCase::test_b011 \
  tests/test_bugbear.py::BugbearTestCase::test_b012 \
  tests/test_bugbear.py::BugbearTestCase::test_b013 \
  tests/test_bugbear.py::BugbearTestCase::test_b014 \
  tests/test_bugbear.py::BugbearTestCase::test_b015 \
  tests/test_bugbear.py::BugbearTestCase::test_b016 \
  tests/test_bugbear.py::BugbearTestCase::test_b017 \
  tests/test_bugbear.py::BugbearTestCase::test_b018_classes \
  tests/test_bugbear.py::BugbearTestCase::test_b018_functions \
  tests/test_bugbear.py::BugbearTestCase::test_b019 \
  tests/test_bugbear.py::BugbearTestCase::test_b020 \
  tests/test_bugbear.py::BugbearTestCase::test_b021_classes \
  tests/test_bugbear.py::BugbearTestCase::test_b022 \
  tests/test_bugbear.py::BugbearTestCase::test_b901 \
  tests/test_bugbear.py::BugbearTestCase::test_b902 \
  tests/test_bugbear.py::BugbearTestCase::test_b902_py38 \
  tests/test_bugbear.py::BugbearTestCase::test_b903 \
  tests/test_bugbear.py::BugbearTestCase::test_b904 \
  tests/test_bugbear.py::BugbearTestCase::test_b950 \
  tests/test_bugbear.py::BugbearTestCase::test_b9_extend_select \
  tests/test_bugbear.py::BugbearTestCase::test_b9_select \
  tests/test_bugbear.py::BugbearTestCase::test_selfclean_test_bugbear \
  tests/test_bugbear.py::TestFuzz::test_does_not_crash_on_any_valid_code \
  tests/test_bugbear.py::TestFuzz::test_does_not_crash_on_call_in_except_statement \
  tests/test_bugbear.py::TestFuzz::test_does_not_crash_on_site_code \
  tests/test_bugbear.py::TestFuzz::test_does_not_crash_on_tuple_expansion_in_except_statement; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
