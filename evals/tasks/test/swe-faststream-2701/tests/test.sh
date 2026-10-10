#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/application/test_delayed_broker.py::test_di_reconfigured \
  tests/application/test_delayed_broker.py::test_set_broker \
  tests/application/test_delayed_broker.py::test_set_more_than_once_broker \
  tests/application/test_delayed_broker.py::test_start_not_setup_broker; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
