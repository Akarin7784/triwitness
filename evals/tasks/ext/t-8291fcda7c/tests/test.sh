#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_on_heartbeat_unknown_state \
  test/test_nmt.py::TestNmtBase::test_send_command \
  test/test_nmt.py::TestNmtBase::test_state_getset \
  test/test_nmt.py::TestNmtBase::test_state_set_invalid \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_add_heartbeat_callback \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_no_heartbeat \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_node_guarding \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_on_heartbeat \
  test/test_nmt.py::TestNmtMaster::test_nmt_master_on_heartbeat_initialising \
  test/test_nmt.py::TestNmtSlave::test_heartbeat \
  test/test_nmt.py::TestNmtSlave::test_start_two_remote_nodes \
  test/test_nmt.py::TestNmtSlave::test_stop_two_remote_nodes_using_broadcast; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
