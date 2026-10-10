#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/test_send_pull_request.py::test_send_pull_request[branch]' \
  'tests/test_send_pull_request.py::test_send_pull_request[draft]' \
  'tests/test_send_pull_request.py::test_send_pull_request[ready]' \
  tests/test_send_pull_request.py::test_send_pull_request_branch_naming \
  tests/test_send_pull_request.py::test_load_single_resolver_output \
  tests/test_send_pull_request.py::test_apply_patch \
  tests/test_send_pull_request.py::test_apply_patch_preserves_line_endings \
  tests/test_send_pull_request.py::test_apply_patch_create_new_file \
  tests/test_send_pull_request.py::test_apply_patch_delete_file \
  tests/test_send_pull_request.py::test_initialize_repo \
  tests/test_send_pull_request.py::test_send_pull_request_git_push_failure \
  tests/test_send_pull_request.py::test_send_pull_request_permission_error \
  tests/test_send_pull_request.py::test_process_single_issue \
  tests/test_send_pull_request.py::test_process_all_successful_issues \
  tests/test_send_pull_request.py::test_main; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
