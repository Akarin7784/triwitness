#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/tests_shanten.py::test_shanten_for_not_completed_hand \
  tests/tests_shanten.py::test_shanten_number \
  tests/tests_shanten.py::test_shanten_number_and_chiitoitsu \
  tests/tests_shanten.py::test_shanten_number_and_kokushi \
  tests/tests_shanten.py::test_shanten_number_and_open_sets; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
