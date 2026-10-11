#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_outbound_session.py::TestWhileConnectedMethod::test_raising_OutboundSessionHasGoneAway_in_session_stop_will_pass \
  tests/test_outbound_session.py::TestOutboundSession::test_outbound_connected_is_updated_during_on_disconnected_event \
  tests/test_outbound_session.py::TestOutboundSession::test_outbound_connected_is_updated_during_on_hangup_event \
  tests/test_outbound_session.py::TestWhileConnectedMethod::test_context_manager \
  tests/test_outbound_session.py::TestWhileConnectedMethod::test_decorator \
  tests/test_outbound_session.py::TestWhileConnectedMethod::test_raise_value_error_while_the_call_is_active \
  tests/test_outbound_session.py::TestWhileConnectedMethod::test_skip_code_execution_if_the_outbound_session_is_disconnected; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
