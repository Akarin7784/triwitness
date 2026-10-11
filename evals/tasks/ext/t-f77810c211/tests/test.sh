#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/client/test_session.py::test_port_set \
  tests/client/test_session.py::test_get_session_types \
  tests/client/test_session.py::test_get_session \
  tests/client/test_session.py::test_get_session_default \
  tests/client/test_session.py::test_get_session_bad \
  tests/client/test_session.py::test_session_api_key \
  tests/client/test_session.py::test_auto_complete_invalid_max_suggestions \
  tests/client/test_session.py::test_default_port \
  tests/client/test_session.py::test_port_v2_set; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
